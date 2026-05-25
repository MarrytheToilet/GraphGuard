"""E5/M6: graph repair — filter or downweight risky edges and measure
the effect on relation precision/recall/F1 against DocRED gold.

The base correctness label per edge comes from `edge_correctness` (set by E2).
We treat label='correct' as a true positive; 'wrong' or 'unmatched' as FP.
Recall is computed over the fixed gold pool (count of distinct gold edges
matched by any kept extracted edge of the right relation).

Methods compared:

* raw                  no filter
* random               drop a random fraction
* by_confidence        drop edges with the lowest LLM-reported confidence (if any)
* by_risk              drop edges with the highest risk_score
* by_schema_sens       drop edges with high schema_sensitivity
* by_stability         drop edges with the lowest stability_score
"""
from __future__ import annotations

import logging
import random
import sqlite3
from dataclasses import dataclass
from typing import Iterable, List

log = logging.getLogger(__name__)


@dataclass
class RepairPoint:
    method: str
    fraction_removed: float
    n_kept: int
    tp: int
    fp: int
    fn: int
    precision: float
    recall: float
    f1: float


def _f1(p, r):
    return 2 * p * r / (p + r) if (p + r) else 0.0


def _gather_edges(conn: sqlite3.Connection):
    return list(conn.execute(
        "SELECT e.edge_id, e.document_id, e.confidence, ec.label, "
        "       COALESCE(s.risk_score, 0)             AS risk, "
        "       COALESCE(s.schema_sensitivity, 0)     AS schema_s, "
        "       COALESCE(s.stability_score, 1)        AS stability "
        "FROM extracted_edges e "
        "LEFT JOIN edge_correctness ec ON ec.edge_id = e.edge_id "
        "LEFT JOIN edge_reliability_scores s ON s.edge_id = e.edge_id "
        "WHERE ec.label IS NOT NULL"
    ))


def _gold_count(conn: sqlite3.Connection, document_ids: Iterable[str]) -> int:
    qs = ",".join("?" * len(list(document_ids)))
    if not qs:
        return 0
    rows = conn.execute(
        f"SELECT COUNT(*) FROM gold_edges WHERE document_id IN ({qs})",
        tuple(document_ids),
    ).fetchone()
    return int(rows[0])


def _eval_kept(rows, n_gold: int) -> tuple[int, int, int, float, float, float]:
    tp = sum(1 for r in rows if r["label"] == "correct")
    fp = sum(1 for r in rows if r["label"] in ("wrong", "unmatched"))
    fn = max(n_gold - tp, 0)
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    return tp, fp, fn, precision, recall, _f1(precision, recall)


def evaluate_repair(conn: sqlite3.Connection,
                    fractions: tuple[float, ...] = (0.0, 0.1, 0.2, 0.3, 0.5),
                    seed: int = 0) -> List[RepairPoint]:
    rows = _gather_edges(conn)
    if not rows:
        return []
    doc_ids = sorted({r["document_id"] for r in rows})
    n_gold = _gold_count(conn, doc_ids)
    rng = random.Random(seed)
    # Sort key semantics: we sort DESCENDING and drop the first n_drop.
    # So the key should be high for "I want to drop you first."
    by = {
        "random":          [(rng.random(), r) for r in rows],
        "by_confidence":   [(1.0 - (r["confidence"] or 0.0), r) for r in rows],   # drop lowest confidence
        "by_risk":         [((r["risk"] or 0.0), r) for r in rows],                # drop highest risk
        "by_schema_sens":  [((r["schema_s"] or 0.0), r) for r in rows],
        "by_stability":    [(1.0 - (r["stability"] or 1.0), r) for r in rows],    # drop lowest stability
    }
    # raw baseline at 0% removed
    out: list[RepairPoint] = []
    tp, fp, fn, p, rc, f1 = _eval_kept(rows, n_gold)
    out.append(RepairPoint("raw", 0.0, len(rows), tp, fp, fn, p, rc, f1))

    n = len(rows)
    for frac in fractions:
        n_drop = int(round(n * frac))
        if n_drop <= 0 and frac > 0:
            n_drop = 1
        if n_drop >= n:
            n_drop = n - 1
        for method, scored in by.items():
            scored_sorted = sorted(scored, key=lambda x: x[0], reverse=True)
            kept = [r for _, r in scored_sorted[n_drop:]]
            tp, fp, fn, p, rc, f1 = _eval_kept(kept, n_gold)
            out.append(RepairPoint(method, frac, len(kept), tp, fp, fn, p, rc, f1))
    return out
