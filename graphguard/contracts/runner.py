"""Contract execution engine.

Loads counterfactual pair data from a run-DB, evaluates each contract,
returns ContractResults. Does NOT touch LLMs.
"""
from __future__ import annotations

import sqlite3
import statistics as stats
from collections import defaultdict
from typing import Iterable, List

from .base import Contract, ContractResult, PairObservation
from .registry import REGISTRY
from ..matching.relation_normalizer import project_to_base


def _project_triples(edges, base_relation_ids):
    """Triples on (subject_name, project_to_base(relation), object_name)."""
    out = []
    for e in edges:
        s = (e["subject_name"] if "subject_name" in e.keys() else None) or e["subject_entity_id"]
        o = (e["object_name"] if "object_name" in e.keys() else None) or e["object_entity_id"]
        r = e["relation"]
        if not s or not o or not r:
            continue
        if base_relation_ids:
            proj = project_to_base(r, base_relation_ids=base_relation_ids)
            r2 = proj if proj else r  # keep unprojectable tokens distinct
        else:
            r2 = r
        out.append((str(s).strip().lower(), str(r2), str(o).strip().lower()))
    return out


def _query_q3(edges, base_relation_ids=None):
    """Multi-hop join answer set with optional relation back-projection."""
    triples = _project_triples(edges, base_relation_ids)
    by_subj = defaultdict(list)
    for s, r, o in triples:
        by_subj[s].append((r, o))
    out = set()
    for s, lst in by_subj.items():
        for i, (rA, oA) in enumerate(lst):
            for rB, oB in lst[i + 1:]:
                if rA != rB:
                    out.add((s, rA, oA, rB, oB))
    return out


def _iter_pairs(conn: sqlite3.Connection):
    """Yield (intervention_id, base_event, cf_event, cause_family, semantic_class, operator,
              document_id, description). Uses the cf_event_id column when populated; otherwise
    falls back to a configuration-tuple join (never the legacy created_at heuristic)."""
    rows = conn.execute(
        """
        SELECT cfr.intervention_id, cfr.run_id, cfr.base_event_id, cfr.created_at AS cf_at,
               cfr.document_id, cfr.cf_event_id,
               cfr.schema_id AS cfr_schema, cfr.prompt_id AS cfr_prompt,
               cfr.model_id AS cfr_model, cfr.temperature AS cfr_temp, cfr.seed AS cfr_seed,
               COALESCE(ic.cause_family, 'unknown')   AS cause_family,
               COALESCE(ic.semantic_class, 'unknown') AS semantic_class,
               COALESCE(ic.operator, 'unknown')       AS operator,
               COALESCE(ic.description, '')           AS description
        FROM counterfactual_runs cfr
        LEFT JOIN intervention_candidates ic
               ON ic.intervention_id = cfr.intervention_id
        ORDER BY cfr.document_id, cfr.created_at
        """
    ).fetchall()
    for r in rows:
        cf_event = r["cf_event_id"]
        if not cf_event:
            ee = conn.execute(
                """SELECT event_id FROM extraction_events
                   WHERE document_id=? AND schema_id=? AND prompt_id=? AND model_id=?
                     AND temperature=? AND seed=?
                   ORDER BY abs(julianday(created_at) - julianday(?)) ASC LIMIT 1""",
                (r["document_id"], r["cfr_schema"], r["cfr_prompt"], r["cfr_model"],
                 r["cfr_temp"], r["cfr_seed"], r["cf_at"]),
            ).fetchone()
            cf_event = ee["event_id"] if ee else None
        if not cf_event or not r["base_event_id"]:
            continue
        yield (r["intervention_id"], r["base_event_id"], cf_event,
               r["cause_family"], r["semantic_class"], r["operator"],
               r["document_id"], r["description"])


def _edges(conn, event_id):
    return list(conn.execute(
        "SELECT * FROM extracted_edges WHERE event_id=?", (event_id,)
    ))


_BASE_REL_CACHE: dict = {}


def _base_relation_ids_for(conn, base_event_id):
    """Look up the relation_id set the base event was extracted under, so we can
    back-project cf relation tokens emitted under a rename/coarse schema.

    Cached at module scope keyed by schema_id (sqlite3.Connection forbids
    arbitrary attribute assignment, so we cannot cache on the conn object).
    """
    from ..extraction.prompts import load_yaml, get_schema_def
    row = conn.execute("SELECT schema_id FROM extraction_events WHERE event_id=?",
                       (base_event_id,)).fetchone()
    if not row:
        return None
    schema_id = row["schema_id"] if hasattr(row, "keys") else row[0]
    if schema_id in _BASE_REL_CACHE:
        return _BASE_REL_CACHE[schema_id]
    sy = load_yaml("configs/schemas.yaml")
    sdef = get_schema_def(sy, schema_id)
    ids = {r["id"] for r in sdef["relations"]}
    _BASE_REL_CACHE[schema_id] = ids
    return ids


def evaluate_contract(conn: sqlite3.Connection, contract: Contract,
                      pairs_cache=None) -> ContractResult:
    """Evaluate a single contract against the run-DB.

    pairs_cache: optional list of materialized pairs to avoid re-iterating.
    """
    pairs = pairs_cache if pairs_cache is not None else list(_iter_pairs(conn))

    obs: List[PairObservation] = []
    for (iv, base_ev, cf_ev, cf, sc, op, doc, desc) in pairs:
        if not contract.applies(cf, sc, op, description=desc):
            continue
        be = _edges(conn, base_ev)
        ce = _edges(conn, cf_ev)
        base_relation_ids = _base_relation_ids_for(conn, base_ev)
        if contract.query_scoped:
            base_ans = _query_q3(be, base_relation_ids=base_relation_ids)
            cf_ans = _query_q3(ce, base_relation_ids=base_relation_ids)
            if not base_ans and not cf_ans:
                m = 1.0
            else:
                m = len(base_ans & cf_ans) / max(1, len(base_ans | cf_ans))
        else:
            m = contract.metric_fn(be, ce, base_relation_ids=base_relation_ids)
        obs.append(PairObservation(
            document_id=doc, intervention_id=iv,
            cause_family=cf, semantic_class=sc, operator=op,
            metric=float(m), passed=contract.passes(float(m)),
        ))

    n = len(obs)
    n_fail = sum(1 for o in obs if not o.passed)
    metric_vals = [o.metric for o in obs]
    shortfalls = [contract.shortfall(o.metric) for o in obs if not o.passed]

    by_family = {}
    fam_groups = defaultdict(list)
    for o in obs:
        fam_groups[o.cause_family].append(o)
    for fam, lst in fam_groups.items():
        nf = sum(1 for o in lst if not o.passed)
        by_family[fam] = {
            "n": len(lst),
            "n_fail": nf,
            "violation_rate": nf / max(1, len(lst)),
            "mean_metric": stats.mean(o.metric for o in lst) if lst else 0.0,
        }

    sens = {}
    for t in contract.sensitivity_thresholds:
        if contract.direction == "min":
            fails = sum(1 for v in metric_vals if v < t)
        else:
            fails = sum(1 for v in metric_vals if v > t)
        sens[str(t)] = fails / max(1, n)

    examples = sorted(
        [o for o in obs if not o.passed],
        key=lambda o: contract.shortfall(o.metric),
        reverse=True,
    )[:5]

    return ContractResult(
        contract_id=contract.id,
        name=contract.name,
        kind=contract.kind,
        scope=contract.scope,
        threshold=contract.threshold,
        direction=contract.direction,
        n_pairs=n,
        n_pass=n - n_fail,
        n_fail=n_fail,
        violation_rate=n_fail / max(1, n),
        severity_mean=stats.mean(shortfalls) if shortfalls else 0.0,
        severity_p95=(sorted(shortfalls)[int(0.95 * (len(shortfalls) - 1))]
                      if shortfalls else 0.0),
        metric_mean=stats.mean(metric_vals) if metric_vals else 0.0,
        metric_median=stats.median(metric_vals) if metric_vals else 0.0,
        by_family=by_family,
        threshold_sensitivity=sens,
        examples=[{
            "doc": o.document_id, "intervention": o.intervention_id,
            "family": o.cause_family, "semantic_class": o.semantic_class,
            "operator": o.operator, "metric": o.metric,
        } for o in examples],
    )


def run_all(conn: sqlite3.Connection, contract_ids=None) -> dict:
    """Evaluate every registered contract (or a subset) on the run-DB."""
    pairs = list(_iter_pairs(conn))
    ids = contract_ids or list(REGISTRY.keys())
    results = []
    for cid in ids:
        c = REGISTRY[cid]
        r = evaluate_contract(conn, c, pairs_cache=pairs)
        results.append(r)
    summary = {
        "n_contracts": len(results),
        "n_violated": sum(1 for r in results if r.verdict() == "VIOLATED"),
        "n_satisfied": sum(1 for r in results if r.verdict() == "SATISFIED"),
        "n_inconclusive": sum(1 for r in results if r.verdict() == "INCONCLUSIVE"),
    }
    return {
        "summary": summary,
        "contracts": [r.to_dict() for r in results],
    }
