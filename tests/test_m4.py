"""Unit tests for M4 (E0/E2) and M5/M6 (planners + repair).

These are deterministic and do not call any LLM.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from graphguard.db.database import open_db
from graphguard.db import repositories as repo
from graphguard.experiments import e0_stability as e0
from graphguard.experiments import e2_error_detection as e2
from graphguard.experiments.e6_repair import evaluate_repair
from graphguard.planning.planners import (
    get_planner, ExhaustivePlanner, RandomPlanner,
    SpanOnlyPlanner, PromptOnlyPlanner, SchemaOnlyPlanner, GraphGuardPlanner,
)


def _fresh_db(tmp_path):
    return open_db(tmp_path / "t.db")


def _seed_basic(conn, doc="d1"):
    repo.upsert_document(conn, repo.Document(doc, "docred", "T", "x", "validation"))
    repo.upsert_sentences(conn, [repo.Sentence(f"{doc}::s0", doc, 0, "Obama born Honolulu.")])
    repo.upsert_entities(conn, [
        repo.Entity(f"{doc}::e0", doc, "Obama", ["Obama"], "PER"),
        repo.Entity(f"{doc}::e1", doc, "Honolulu", ["Honolulu"], "LOC"),
    ])
    repo.upsert_prompt(conn, repo.PromptRow("base_v1", "base", "t", []))
    repo.upsert_schema(conn, repo.SchemaRow("docred_full", "S", "", []))
    conn.commit()
    return doc


def _ev(conn, doc, eid, edges):
    repo.insert_event(conn, repo.ExtractionEvent(
        event_id=eid, document_id=doc,
        prompt_id="base_v1", schema_id="docred_full", model_id="m",
        temperature=0.0, seed=1,
        input_sentence_ids=[], input_entity_ids=[],
    ))
    rows = []
    for i, (s, r, o) in enumerate(edges):
        rows.append(repo.ExtractedEdge(
            edge_id=f"{eid}::e{i}", event_id=eid, document_id=doc,
            subject_entity_id=None, subject_name=s, relation=r,
            object_entity_id=None, object_name=o,
            evidence_sentence_ids=[], confidence=0.9, raw_json="{}",
        ))
    repo.insert_edges(conn, rows)
    conn.commit()
    return rows


# ---------- E0 ----------

def test_e0_metrics_identical_runs(tmp_path):
    conn = _fresh_db(tmp_path)
    doc = _seed_basic(conn)
    _ev(conn, doc, "ev1", [("Obama", "P19", "Honolulu"), ("Obama", "P39", "USA")])
    _ev(conn, doc, "ev2", [("Obama", "P19", "Honolulu"), ("Obama", "P39", "USA")])
    res = e0.compute_metrics(conn, doc, ["ev1", "ev2"])
    assert res.avg_edge_overlap == 1.0
    assert res.disappearance_rate == 0.0
    assert res.type_flip_rate == 0.0
    assert res.type_agreement == 1.0


def test_e0_metrics_different_runs(tmp_path):
    conn = _fresh_db(tmp_path)
    doc = _seed_basic(conn)
    _ev(conn, doc, "ev1", [("Obama", "P19", "Honolulu"), ("Obama", "P39", "USA")])
    _ev(conn, doc, "ev2", [("Obama", "P20", "Honolulu")])  # type-flip + disappear
    res = e0.compute_metrics(conn, doc, ["ev1", "ev2"])
    assert res.avg_edge_overlap == 0.0  # no triples overlap
    assert res.disappearance_rate > 0  # P19 and P39 disappear from ev1
    assert res.type_flip_rate == 1.0   # the only common (Obama,Honolulu) pair flipped
    assert res.type_agreement == 0.0


def test_e0_stochastic_variance(tmp_path):
    conn = _fresh_db(tmp_path)
    doc = _seed_basic(conn)
    base = _ev(conn, doc, "evB", [("Obama", "P19", "Honolulu"), ("Obama", "P39", "USA")])
    _ev(conn, doc, "evA", [("Obama", "P19", "Honolulu")])  # P39 disappears
    _ev(conn, doc, "evC", [("Obama", "P19", "Honolulu"), ("Obama", "P39", "USA")])  # all stable
    n = e0.update_stochastic_variance(conn, "evB", ["evA", "evC"], base_relation_ids={"P19", "P39"})
    assert n == 2
    rows = {r["edge_id"]: r["stochastic_variance"]
            for r in conn.execute("SELECT * FROM edge_reliability_scores")}
    # The "Obama-P19-Honolulu" edge stayed in both -> variance 0
    # The "Obama-P39-USA" edge missing in evA, present in evC -> variance 0.5
    assert rows[base[0].edge_id] == 0.0
    assert rows[base[1].edge_id] == 0.5


# ---------- E2 ----------

def _add_gold(conn, doc, edges):
    rows = []
    for i, (h, t, r) in enumerate(edges):
        rows.append(repo.GoldEdge(
            gold_edge_id=f"{doc}::g{i}", document_id=doc,
            head_entity_id=None, tail_entity_id=None,
            head_name=h, tail_name=t, relation_base=r,
            evidence_sentence_ids=[], source="docred",
        ))
    repo.upsert_gold_edges(conn, rows)
    conn.commit()


def test_e2_label_and_metrics(tmp_path):
    conn = _fresh_db(tmp_path)
    doc = _seed_basic(conn)
    _ev(conn, doc, "ev", [
        ("Obama", "P19", "Honolulu"),  # correct
        ("Obama", "P20", "Honolulu"),  # wrong relation (same pair)
        ("Mars",  "P31", "Planet"),    # unmatched (no gold pair)
    ])
    _add_gold(conn, doc, [("Obama", "Honolulu", "P19")])
    labels = e2.label_extracted_edges(conn)
    by_label = {l.edge_id.split("::")[-1]: l.label for l in labels}
    assert by_label["e0"] == "correct"
    assert by_label["e1"] == "wrong"
    assert by_label["e2"] == "unmatched"

    # also test ranking helpers
    scores = [0.9, 0.5, 0.1]
    pos = [0, 1, 1]
    assert e2.precision_at_k(scores, pos, 1) == 0.0  # top-1 score is the correct edge
    assert e2.precision_at_k(scores, pos, 3) == pytest.approx(2 / 3)
    assert e2.average_precision(scores, pos) > 0
    assert 0.0 <= e2.roc_auc(scores, pos) <= 1.0


# ---------- planners ----------

def _candidates():
    from graphguard.interventions.candidates import InterventionCandidate
    return [
        InterventionCandidate("a-schema-1", "d", "schema", "with_other", "switch_schema", ""),
        InterventionCandidate("b-prompt-1", "d", "prompt_clause", "C1", "remove", ""),
        InterventionCandidate("c-sent-mask", "d", "sentence", "d::s0", "mask", ""),
        InterventionCandidate("d-sent-rm", "d", "sentence", "d::s0", "remove", ""),
        InterventionCandidate("e-sent-rm2", "d", "sentence", "d::s1", "remove", ""),
    ]


def test_planner_filters_by_type():
    cs = _candidates()
    assert {c.target_type for c in SpanOnlyPlanner().choose(cs, 10)} == {"sentence"}
    assert {c.target_type for c in PromptOnlyPlanner().choose(cs, 10)} == {"prompt_clause"}
    assert {c.target_type for c in SchemaOnlyPlanner().choose(cs, 10)} == {"schema"}


def test_planner_random_respects_budget():
    cs = _candidates()
    chosen = RandomPlanner(seed=42).choose(cs, 2)
    assert len(chosen) == 2


def test_planner_graphguard_priorities():
    cs = _candidates()
    chosen = GraphGuardPlanner().choose(cs, 3)
    # tier 0 schema and tier 1 prompt should appear before any sentence
    target_types = [c.target_type for c in chosen]
    assert target_types[0] == "schema"
    assert target_types[1] == "prompt_clause"


def test_planner_registry():
    assert isinstance(get_planner("exhaustive"), ExhaustivePlanner)
    assert isinstance(get_planner("graphguard"), GraphGuardPlanner)
    with pytest.raises(ValueError):
        get_planner("doesnotexist")


# ---------- E6 repair ----------

def test_repair_filtering_by_risk(tmp_path):
    conn = _fresh_db(tmp_path)
    doc = _seed_basic(conn)
    _ev(conn, doc, "ev", [
        ("A", "R1", "B"),  # correct
        ("A", "R2", "B"),  # wrong
        ("C", "R3", "D"),  # unmatched
        ("E", "R4", "F"),  # correct
    ])
    _add_gold(conn, doc, [("A", "B", "R1"), ("E", "F", "R4")])
    e2.label_extracted_edges(conn)
    # populate risk_scores: high risk for the wrong/unmatched ones
    edges = list(conn.execute("SELECT edge_id FROM extracted_edges"))
    for i, r in enumerate(edges):
        risk = 0.9 if i in (1, 2) else 0.1
        conn.execute(
            "INSERT INTO edge_reliability_scores(edge_id, risk_score, schema_sensitivity, "
            "stability_score, computed_at) VALUES (?,?,?,?,datetime('now'))",
            (r["edge_id"], risk, risk, 1 - risk),
        )
    conn.commit()
    pts = evaluate_repair(conn, fractions=(0.5,), seed=0)
    by = {(p.method, p.fraction_removed): p for p in pts}
    raw = by[("raw", 0.0)]
    by_risk = by[("by_risk", 0.5)]
    # by_risk drops 2 edges (50% of 4) and should drop the 2 high-risk wrong ones,
    # leaving precision = 1.0 (both kept are correct)
    assert by_risk.precision >= raw.precision
    assert by_risk.precision == 1.0