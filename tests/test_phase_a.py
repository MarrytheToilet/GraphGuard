"""Smoke tests for query interface, E1, E3, E4, reports."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

import pytest

from graphguard.db.database import open_db
from graphguard.db import repositories as repo
from graphguard import queries as Q
from graphguard.experiments.e1_known_cause import (
    derive_cause_labels, evaluate_cause_ranking,
)
from graphguard.experiments.e3_schema_debug import evaluate_schema
from graphguard.experiments.e4_cost_quality import evaluate as e4_eval
from graphguard.scoring.risk import compute_for_edge
from graphguard.reports.build import collect_case_studies, summarize_db


@pytest.fixture
def conn(tmp_path):
    db_path = tmp_path / "t.db"
    c = open_db(str(db_path))
    # minimal seed
    c.execute("INSERT INTO documents VALUES('d1','t','Doc1','text','dev')")
    c.execute("INSERT INTO sentences VALUES('d1::s0','d1',0,'s0')")
    c.execute("INSERT INTO sentences VALUES('d1::s1','d1',1,'s1')")
    c.execute("INSERT INTO entities VALUES('d1::e0','d1','Alice','[]','PER')")
    c.execute("INSERT INTO entities VALUES('d1::e1','d1','Beijing','[]','LOC')")
    c.execute("INSERT INTO schemas(schema_id,name,description,relation_types_json,parent_schema_id) "
              "VALUES('sch','sch','d','[]',NULL)")
    c.execute("INSERT INTO prompts(prompt_id,name,full_prompt,clause_ids_json) "
              "VALUES('p','p','x','[]')")
    c.execute("INSERT INTO extraction_events(event_id,document_id,prompt_id,schema_id,model_id,"
              "temperature,seed,input_sentence_ids_json,input_entity_ids_json,created_at,"
              "token_input,token_output,latency_ms) VALUES "
              "('ev','d1','p','sch','m',0.0,7,'[]','[]','t',0,0,0)")
    # base edges
    c.execute("INSERT INTO extracted_edges VALUES('eA','ev','d1','d1::e0','Alice','P19',"
              "'d1::e1','Beijing','[0]',0.9,'{}')")
    c.execute("INSERT INTO extracted_edges VALUES('eB','ev','d1','d1::e0','Alice','P17',"
              "'d1::e1','Beijing','[1]',0.7,'{}')")
    # gold: only Alice -P19-> Beijing is gold
    c.execute("INSERT INTO gold_edges VALUES('g1','d1','d1::e0','d1::e1','Alice','Beijing',"
              "'P19','[0]','docred')")
    # candidates + cf runs + outcomes
    c.execute(
        "INSERT INTO intervention_candidates"
        "(intervention_id,document_id,target_type,target_id,operator,description,"
        "estimated_cost,group_id,semantic_class,cause_family) VALUES"
        "('iv-s0','d1','sentence','d1::s0','remove','remove s0',1.0,NULL,"
        "'semantic','evidence')"
    )
    c.execute(
        "INSERT INTO intervention_candidates"
        "(intervention_id,document_id,target_type,target_id,operator,description,"
        "estimated_cost,group_id,semantic_class,cause_family) VALUES"
        "('iv-pc','d1','prompt_clause','C2_infer_implicit','remove','drop C2',1.0,NULL,"
        "'semantic','prompt')"
    )
    c.execute(
        "INSERT INTO intervention_candidates"
        "(intervention_id,document_id,target_type,target_id,operator,description,"
        "estimated_cost,group_id,semantic_class,cause_family) VALUES"
        "('iv-sw','d1','schema','with_other','switch_schema','sch+other',1.0,NULL,"
        "'semantic','schema')"
    )
    run_columns = (
        "run_id,base_event_id,intervention_id,document_id,prompt_id,schema_id,"
        "model_id,temperature,seed,token_input,token_output,latency_ms,status,created_at"
    )
    c.execute(
        f"INSERT INTO counterfactual_runs({run_columns}) VALUES"
        "('r1','ev','iv-s0','d1','p','sch','m',0.0,7,0,0,0,'OK','t')"
    )
    c.execute(
        f"INSERT INTO counterfactual_runs({run_columns}) VALUES"
        "('r2','ev','iv-pc','d1','p','sch','m',0.0,7,0,0,0,'OK','t')"
    )
    c.execute(
        f"INSERT INTO counterfactual_runs({run_columns}) VALUES"
        "('r3','ev','iv-sw','d1','p','sch','m',0.0,7,0,0,0,'OK','t')"
    )
    # Outcomes:
    # eA disappears when s0 removed (text-caused), exact same elsewhere.
    c.execute("INSERT INTO edge_outcomes VALUES('o1','r1','eA','DISAPPEARED',NULL,NULL,NULL,1.0)")
    c.execute("INSERT INTO edge_outcomes VALUES('o2','r2','eA','EXACT_SAME','eA','P19',0.9,1.0)")
    c.execute("INSERT INTO edge_outcomes VALUES('o3','r3','eA','EXACT_SAME','eA','P19',0.9,1.0)")
    # eB disappears when prompt clause removed (prompt-caused), schema flips it.
    c.execute("INSERT INTO edge_outcomes VALUES('o4','r1','eB','EXACT_SAME','eB','P17',0.7,1.0)")
    c.execute("INSERT INTO edge_outcomes VALUES('o5','r2','eB','DISAPPEARED',NULL,NULL,NULL,1.0)")
    c.execute("INSERT INTO edge_outcomes VALUES('o6','r3','eB','TYPE_FLIP','eB2','P131',0.6,1.0)")
    c.commit()
    return c


def test_compute_preserves_stochastic_variance(conn):
    # pre-write an existing E0 stochastic_variance for eA
    conn.execute("INSERT INTO edge_reliability_scores(edge_id, stochastic_variance, computed_at) "
                 "VALUES('eA', 0.42, 't')")
    conn.commit()
    s = compute_for_edge(conn, "eA")
    assert s["stochastic_variance"] == pytest.approx(0.42)


def test_why_edge_top_is_sentence_for_text_caused(conn):
    causes = Q.why_edge(conn, "eA", top_k=3)
    assert causes, "expected at least one cause"
    assert causes[0].variable_type == "sentence"
    assert causes[0].effect == pytest.approx(1.0)


def test_why_edge_top_is_prompt_for_prompt_caused(conn):
    causes = Q.why_edge(conn, "eB", top_k=3)
    assert causes
    # eB disappears under prompt clause removal; effect=1.0 there, schema flip is via why_type
    assert causes[0].variable_type == "prompt_clause"


def test_why_type_picks_schema_for_eB(conn):
    causes = Q.why_type(conn, "eB", top_k=3)
    assert causes
    assert causes[0].variable_type == "schema"
    assert causes[0].effect == pytest.approx(1.0)


def test_find_fragile_and_audit(conn):
    from graphguard.scoring.risk import compute_all
    compute_all(conn)
    # eA: change in 1/3 -> stab=0.667; eB: change in 2/3 -> stab=0.333. fragile threshold=0.5 => stab<=0.5 => only eB
    fragile = Q.find_fragile_edges(conn, threshold=0.5)
    fids = {e.edge_id for e in fragile}
    assert "eB" in fids
    audit = Q.rank_edges_for_audit(conn, k=2)
    assert audit and audit[0].edge_id == "eB"  # higher risk


def test_e3_schema_confusion(conn):
    out = evaluate_schema(conn)
    assert "with_other" in out["flip_rates"]
    rates = out["flip_rates"]["with_other"]
    assert rates["type_flip_rate"] == pytest.approx(0.5)  # 1 of 2 is TYPE_FLIP


def test_e4_cost_quality_runs(conn):
    # need candidate registry; use existing 3
    pts = e4_eval(conn, planners=["random", "exhaustive"], budgets=[1, 3], top_k=2)
    by = {(p.planner, p.budget): p for p in pts}
    assert by[("exhaustive", 3)].cause_recall_at_k == pytest.approx(1.0)


def test_e1_derive_and_evaluate(conn):
    from graphguard.scoring.risk import compute_all
    compute_all(conn)
    # need edge_correctness rows; eA correct vs gold, eB unmatched (P17 ≠ gold P19)
    conn.execute("INSERT INTO edge_correctness VALUES('eA','d1','correct','g1','t')")
    conn.execute("INSERT INTO edge_correctness VALUES('eB','d1','wrong',NULL,'t')")
    conn.commit()
    labels = derive_cause_labels(conn)
    assert labels, "should derive at least one cause label"
    res = evaluate_cause_ranking(conn, labels, top_k=3)
    assert res["n"] == len(labels)
    assert 0.0 <= res["top1_acc"] <= 1.0


def test_reports_summary_and_cases(conn):
    from graphguard.scoring.risk import compute_all
    compute_all(conn)
    s = summarize_db(conn)
    assert s["documents"] == 1 and s["extracted_edges"] == 2
    cases = collect_case_studies(conn, k=2)
    assert len(cases) >= 1
    assert "edge" in cases[0] and "why_edge_top" in cases[0]
