"""E4: planner cost-quality curve.

Approach (no extra LLM calls; all reuses cf data already in DB):

1. Treat the cf-cache for a document as the *exhaustive oracle*: the responsibility
   of intervention i for edge e is `Change(e, i)` from edge_outcomes.
2. For each planner P and budget B:
     - call P.choose(candidates, budget=B) on the document's full candidate list
     - intersect the chosen ids with what the oracle already has data for
     - compute per-edge top-k cause recall vs the oracle's full top-k
3. Aggregate (recall@k vs B) across documents.

Reported metrics per (planner, budget):
    n_chosen                  : interventions selected (= cost in calls)
    n_chosen_with_data        : interventions for which cf data exists in cache
    cause_recall_at_k         : for each base edge, fraction of oracle's top-k
                                 changing interventions also chosen by planner
    rank_kendall_tau_avg      : optional rank correlation (skipped if scipy missing)
    cache_hit_rate            : n_chosen_with_data / n_chosen
    shared_run_reuse          : mean base-edge outcomes informed per selected
                                 intervention (not cross-contract endpoint savings)
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import List

from ..planning.planners import get_planner


CHANGE = {"DISAPPEARED", "TYPE_FLIP", "OBJECT_FLIP", "SUBJECT_FLIP", "AMBIGUOUS"}


@dataclass
class CostQualityPoint:
    planner: str
    budget: int
    n_chosen: int
    n_chosen_with_data: int
    cause_recall_at_k: float
    cache_hit_rate: float
    avg_estimated_cost: float = 0.0
    sum_estimated_cost: float = 0.0
    token_input: int = 0
    token_output: int = 0
    shared_run_reuse: float = 0.0


def _doc_cf_data(conn: sqlite3.Connection, doc_id: str):
    """Return list of (edge_id, intervention_id, change01)."""
    return list(conn.execute("""
        SELECT eo.original_edge_id AS edge_id, cfr.intervention_id, eo.outcome_type
        FROM edge_outcomes eo
        JOIN counterfactual_runs cfr ON cfr.run_id = eo.run_id
        WHERE cfr.document_id = ?
    """, (doc_id,)))


def _iv_token_costs(conn: sqlite3.Connection, doc_id: str) -> dict[str, tuple[int, int]]:
    """For each intervention_id observed in cf runs for this doc, sum token usage."""
    out: dict[str, tuple[int, int]] = {}
    for r in conn.execute("""
        SELECT cfr.intervention_id,
               COALESCE(SUM(cfr.token_input), 0)  AS ti,
               COALESCE(SUM(cfr.token_output), 0) AS to_
        FROM counterfactual_runs cfr
        WHERE cfr.document_id = ?
        GROUP BY cfr.intervention_id
    """, (doc_id,)):
        out[r["intervention_id"]] = (int(r["ti"] or 0), int(r["to_"] or 0))
    return out


def _candidates_for_doc(conn: sqlite3.Connection, doc_id: str):
    return list(conn.execute(
        "SELECT * FROM intervention_candidates WHERE document_id = ?", (doc_id,)
    ))


def _auc(points: list[tuple[float, float]]) -> float:
    """Trapezoidal AUC of (x, y) points sorted by x."""
    pts = sorted(points)
    if len(pts) < 2:
        return 0.0
    a = 0.0
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        a += 0.5 * (y0 + y1) * (x1 - x0)
    # normalise by x-range so different budget grids are comparable
    span = pts[-1][0] - pts[0][0]
    return a / span if span else 0.0


def evaluate(conn: sqlite3.Connection, *,
             planners: List[str],
             budgets: List[int],
             top_k: int = 3,
             document_ids: List[str] | None = None) -> List[CostQualityPoint]:
    if document_ids is None:
        document_ids = [r[0] for r in conn.execute(
            "SELECT DISTINCT document_id FROM counterfactual_runs"
        )]

    # Build oracle: per (doc, edge) -> list of (iv_id, change01) sorted by change desc
    oracle: dict[tuple[str, str], list[tuple[str, int]]] = {}
    cache_iv: dict[str, set[str]] = {}
    iv_costs_per_doc: dict[str, dict[str, tuple[int, int]]] = {}
    for doc_id in document_ids:
        ivs_with_data = set()
        per_edge: dict[str, list[tuple[str, int]]] = {}
        for r in _doc_cf_data(conn, doc_id):
            ivs_with_data.add(r["intervention_id"])
            ch = 1 if r["outcome_type"] in CHANGE else 0
            per_edge.setdefault(r["edge_id"], []).append((r["intervention_id"], ch))
        cache_iv[doc_id] = ivs_with_data
        for e, lst in per_edge.items():
            lst.sort(key=lambda x: -x[1])
            oracle[(doc_id, e)] = lst
        iv_costs_per_doc[doc_id] = _iv_token_costs(conn, doc_id)

    out: List[CostQualityPoint] = []
    for planner_name in planners:
        planner = get_planner(planner_name)
        for B in budgets:
            chosen_total = 0
            chosen_with_data = 0
            sum_cost = 0.0
            ti_total = 0
            to_total = 0
            recalls: list[float] = []
            shared_reuse_acc: list[float] = []
            for doc_id in document_ids:
                cands = _candidates_for_doc(conn, doc_id)
                if not cands:
                    continue
                picks = planner.choose(cands, budget=B, conn=conn)
                pick_ids = {(p["intervention_id"] if not hasattr(p, "intervention_id")
                             else p.intervention_id) for p in picks}
                chosen_total += len(pick_ids)
                chosen_with_data += len(pick_ids & cache_iv[doc_id])
                for p in picks:
                    cost = p["estimated_cost"] if not hasattr(p, "estimated_cost") else p.estimated_cost
                    sum_cost += float(cost or 1.0)
                ic = iv_costs_per_doc.get(doc_id, {})
                for iv in pick_ids:
                    ti, to_ = ic.get(iv, (0, 0))
                    ti_total += ti
                    to_total += to_
                # per-edge cause recall@k and shared-run reuse: how many edges
                # in the doc each chosen intervention informs (avg).
                doc_edges_per_iv: dict[str, int] = {}
                for (d, e), lst in oracle.items():
                    if d != doc_id:
                        continue
                    oracle_top = {iv for iv, ch in lst[:top_k] if ch == 1}
                    if oracle_top:
                        recalls.append(len(oracle_top & pick_ids) / len(oracle_top))
                    for iv, _ in lst:
                        if iv in pick_ids:
                            doc_edges_per_iv[iv] = doc_edges_per_iv.get(iv, 0) + 1
                if doc_edges_per_iv:
                    shared_reuse_acc.append(
                        sum(doc_edges_per_iv.values()) / len(doc_edges_per_iv)
                    )
            avg_recall = sum(recalls) / len(recalls) if recalls else 0.0
            hit = (chosen_with_data / chosen_total) if chosen_total else 0.0
            avg_cost = (sum_cost / chosen_total) if chosen_total else 0.0
            avg_reuse = (sum(shared_reuse_acc) / len(shared_reuse_acc)) if shared_reuse_acc else 0.0
            out.append(CostQualityPoint(
                planner=planner_name, budget=B,
                n_chosen=chosen_total, n_chosen_with_data=chosen_with_data,
                cause_recall_at_k=avg_recall, cache_hit_rate=hit,
                avg_estimated_cost=avg_cost, sum_estimated_cost=sum_cost,
                token_input=ti_total, token_output=to_total,
                shared_run_reuse=avg_reuse,
            ))
    return out


def cost_quality_auc(points: List[CostQualityPoint]) -> dict[str, float]:
    """Per-planner AUC of (budget, recall@k). Higher = better cost-quality."""
    by_planner: dict[str, list[tuple[float, float]]] = {}
    for p in points:
        by_planner.setdefault(p.planner, []).append((float(p.budget), float(p.cause_recall_at_k)))
    return {k: round(_auc(v), 4) for k, v in by_planner.items()}
