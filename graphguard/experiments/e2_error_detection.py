"""E2: edge error detection — match extracted edges to DocRED gold and
evaluate whether risk/stability/random rank fragile-correctness.

Labels per extracted edge:

* correct    a gold edge has same (head, tail) entity-pair *and* same relation
* wrong      a gold edge has same (head, tail) entity-pair but different relation
* unmatched  no gold edge with the same entity pair (either truly missing in gold or wrong pair)

We compute area-under-PR (AUC-PR) and Precision@K for each scoring signal,
treating "correct" as the negative class (we want to surface wrongs).
"""
from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from typing import Iterable, List, Optional

from ..db import repositories as repo
from ..matching.entity_matcher import same_entity

log = logging.getLogger(__name__)


@dataclass
class EdgeLabel:
    edge_id: str
    document_id: str
    label: str            # 'correct' | 'wrong' | 'unmatched'
    gold_edge_id: Optional[str]


def _entity_match(extracted_eid: Optional[str], extracted_name: str,
                  gold_eid: Optional[str], gold_name: str) -> bool:
    return same_entity(extracted_eid, extracted_name, gold_eid, gold_name)


def label_extracted_edges(conn: sqlite3.Connection,
                          document_ids: Optional[Iterable[str]] = None) -> List[EdgeLabel]:
    """Compare every extracted edge in a document against gold_edges and
    persist a row in `edge_correctness`. Returns the labels list.

    Only labels edges produced by *base* extraction events (events with no
    corresponding counterfactual_runs row), so that downstream E2 metrics
    aren't dominated by counterfactual extractions.
    """
    if document_ids is None:
        rows = conn.execute("SELECT DISTINCT document_id FROM extracted_edges").fetchall()
        document_ids = [r[0] for r in rows]
    out: list[EdgeLabel] = []
    for doc_id in document_ids:
        gold = repo.get_gold_edges(conn, doc_id)
        edges = list(conn.execute(
            "SELECT e.* FROM extracted_edges e "
            "WHERE e.document_id = ? "
            "AND NOT EXISTS (SELECT 1 FROM counterfactual_runs cr "
            "                WHERE cr.document_id = e.document_id "
            "                AND cr.prompt_id || cr.schema_id IN ("
            "                  SELECT ee.prompt_id || ee.schema_id "
            "                  FROM extraction_events ee WHERE ee.event_id = e.event_id"
            "                ) AND cr.base_event_id != e.event_id)",
            (doc_id,),
        ))
        # Above filter is permissive; tighten by joining base_event_id directly
        if not edges:
            edges = list(conn.execute(
                "SELECT * FROM extracted_edges WHERE document_id = ?", (doc_id,)))
        # Strict: keep edges whose event_id is a base_event_id (referenced by counterfactual_runs)
        # OR no counterfactual_runs reference this event_id at all but it is the *first* event for the doc.
        cf_event_ids = {r[0] for r in conn.execute(
            "SELECT DISTINCT base_event_id FROM counterfactual_runs WHERE document_id = ?",
            (doc_id,),
        )}
        if cf_event_ids:
            edges = [e for e in edges if e["event_id"] in cf_event_ids]
        for e in edges:
            label = "unmatched"
            matched_gold: Optional[str] = None
            best_pair_match: Optional[sqlite3.Row] = None
            for g in gold:
                head_match = _entity_match(
                    e["subject_entity_id"], e["subject_name"],
                    g["head_entity_id"], g["head_name"])
                tail_match = _entity_match(
                    e["object_entity_id"], e["object_name"],
                    g["tail_entity_id"], g["tail_name"])
                if head_match and tail_match:
                    if g["relation_base"] == e["relation"]:
                        label = "correct"
                        matched_gold = g["gold_edge_id"]
                        break
                    if best_pair_match is None:
                        best_pair_match = g
            if label != "correct" and best_pair_match is not None:
                label = "wrong"
                matched_gold = best_pair_match["gold_edge_id"]
            repo.upsert_edge_correctness(
                conn, edge_id=e["edge_id"], document_id=doc_id,
                label=label, gold_edge_id=matched_gold,
            )
            out.append(EdgeLabel(e["edge_id"], doc_id, label, matched_gold))
    conn.commit()
    return out


# ---------- ranking metrics ----------

def _rank_desc(scores: list[float], labels_pos: list[int]) -> list[tuple[float, int]]:
    """Return list of (score, is_positive) sorted by score descending."""
    pairs = list(zip(scores, labels_pos))
    pairs.sort(key=lambda x: x[0], reverse=True)
    return pairs


def precision_at_k(scores: list[float], labels_pos: list[int], k: int) -> float:
    pairs = _rank_desc(scores, labels_pos)
    if k <= 0 or k > len(pairs):
        k = len(pairs)
    if k == 0:
        return 0.0
    return sum(p[1] for p in pairs[:k]) / k


def precision_at_pct(scores: list[float], labels_pos: list[int], pct: float) -> float:
    k = max(1, int(round(len(scores) * pct)))
    return precision_at_k(scores, labels_pos, k)


def average_precision(scores: list[float], labels_pos: list[int]) -> float:
    """AUC-PR (average precision)."""
    pairs = _rank_desc(scores, labels_pos)
    n_pos = sum(labels_pos)
    if n_pos == 0:
        return 0.0
    hits = 0
    cumprec = 0.0
    for i, (_, is_pos) in enumerate(pairs, 1):
        if is_pos:
            hits += 1
            cumprec += hits / i
    return cumprec / n_pos


def roc_auc(scores: list[float], labels_pos: list[int]) -> float:
    pos = [s for s, l in zip(scores, labels_pos) if l == 1]
    neg = [s for s, l in zip(scores, labels_pos) if l == 0]
    if not pos or not neg:
        return 0.5
    wins = ties = 0
    for p in pos:
        for n in neg:
            if p > n:
                wins += 1
            elif p == n:
                ties += 1
    return (wins + 0.5 * ties) / (len(pos) * len(neg))


# ---------- end-to-end evaluation ----------

@dataclass
class DetectionReport:
    n_edges: int
    n_correct: int
    n_wrong: int
    n_unmatched: int
    n_ambiguous: int
    modes: dict   # {mode_name: {n_pos, n_eval, metrics: {signal: {...}}}}


def _eval_signals(rows, labels_pos, baselines: dict | None = None):
    import random
    rng = random.Random(0)
    signals = {
        "risk":               [r["risk"] for r in rows],
        "prompt_sensitivity": [r["prompt_s"] for r in rows],
        "schema_sensitivity": [r["schema_s"] for r in rows],
        "stochastic_variance":[r["stoch"] for r in rows],
        "1_minus_stability":  [1.0 - r["stability"] for r in rows],
        "random":             [rng.random() for _ in rows],
    }
    if baselines:
        # baselines is {edge_id: {signal_name: score}}; missing values default to 0
        sig_names: set[str] = set()
        for v in baselines.values():
            sig_names.update(v.keys())
        for name in sorted(sig_names):
            signals[f"baseline:{name}"] = [
                float(baselines.get(r["edge_id"], {}).get(name, 0.0)) for r in rows
            ]
    out = {}
    for name, sc in signals.items():
        out[name] = {
            "auc_pr": round(average_precision(sc, labels_pos), 4),
            "roc_auc": round(roc_auc(sc, labels_pos), 4),
            "p@5pct": round(precision_at_pct(sc, labels_pos, 0.05), 4),
            "p@10pct": round(precision_at_pct(sc, labels_pos, 0.10), 4),
            "p@20pct": round(precision_at_pct(sc, labels_pos, 0.20), 4),
            "p@1": round(precision_at_k(sc, labels_pos, 1), 4),
            "p@3": round(precision_at_k(sc, labels_pos, 3), 4),
            "p@10": round(precision_at_k(sc, labels_pos, 10), 4),
        }
    return out


def evaluate(conn: sqlite3.Connection,
             positive_labels: tuple[str, ...] = ("wrong", "unmatched")) -> DetectionReport:
    """Score each extracted edge with several signals against the correctness label.

    Reports three evaluation modes that bracket the DocRED gold-incompleteness
    risk pointed out in the audit notes:

      * ``strict``  : positive = wrong + unmatched  (worst-case, gold-completeness assumption)
      * ``clean``   : restrict to ``correct`` vs ``wrong`` only (drop ``unmatched``)
      * ``wrong``   : positive = wrong only (treat ``unmatched`` as negative noise)

    The legacy ``positive_labels`` argument controls only the legacy top-level
    ``metrics`` field (kept for backward-compatible CLI/UI), but downstream
    code should consume ``modes`` for the per-mode breakdown.
    """
    rows = list(conn.execute(
        "SELECT ec.edge_id, ec.label, "
        "       COALESCE(s.risk_score, 0)            AS risk, "
        "       COALESCE(s.prompt_sensitivity, 0)    AS prompt_s, "
        "       COALESCE(s.schema_sensitivity, 0)    AS schema_s, "
        "       COALESCE(s.text_responsibility, 0)   AS text_r, "
        "       COALESCE(s.stability_score, 1)       AS stability, "
        "       COALESCE(s.stochastic_variance, 0)   AS stoch "
        "FROM edge_correctness ec "
        "LEFT JOIN edge_reliability_scores s ON s.edge_id = ec.edge_id"
    ))
    n = len(rows)
    counts = {
        "correct": sum(1 for r in rows if r["label"] == "correct"),
        "wrong": sum(1 for r in rows if r["label"] == "wrong"),
        "unmatched": sum(1 for r in rows if r["label"] == "unmatched"),
        "ambiguous": sum(1 for r in rows if r["label"] == "ambiguous"),
    }
    if n == 0:
        return DetectionReport(0, 0, 0, 0, 0, {})

    # Pull baseline signals for these edges (confidence_inv, majority_vote_inv, ...)
    from ..scoring.baselines import load_for_edges
    baselines = load_for_edges(conn, [r["edge_id"] for r in rows])

    modes: dict = {}

    # Mode: strict (legacy default — wrong+unmatched are positive).
    legacy_pos = [1 if r["label"] in ("wrong", "unmatched") else 0 for r in rows]
    modes["strict"] = {
        "definition": "positive = wrong + unmatched (assumes DocRED gold is complete)",
        "n_eval": n, "n_pos": sum(legacy_pos),
        "prevalence": round(sum(legacy_pos) / n, 4),
        "signals": _eval_signals(rows, legacy_pos, baselines),
    }

    # Mode: clean (correct vs wrong only — robust to gold incompleteness).
    clean_rows = [r for r in rows if r["label"] in ("correct", "wrong")]
    if clean_rows:
        clean_pos = [1 if r["label"] == "wrong" else 0 for r in clean_rows]
        modes["clean"] = {
            "definition": "drop unmatched; correct vs wrong only (robust to gold incompleteness)",
            "n_eval": len(clean_rows), "n_pos": sum(clean_pos),
            "prevalence": round(sum(clean_pos) / max(1, len(clean_rows)), 4),
            "signals": _eval_signals(clean_rows, clean_pos, baselines),
        }

    # Mode: wrong-only (treat unmatched as negative — conservative).
    wrong_pos = [1 if r["label"] == "wrong" else 0 for r in rows]
    if sum(wrong_pos) > 0:
        modes["wrong_only"] = {
            "definition": "positive = wrong only; unmatched treated as negative",
            "n_eval": n, "n_pos": sum(wrong_pos),
            "prevalence": round(sum(wrong_pos) / n, 4),
            "signals": _eval_signals(rows, wrong_pos, baselines),
        }

    # Backward-compat top-level metrics for old CLI consumers.
    legacy_pos2 = [1 if r["label"] in positive_labels else 0 for r in rows]
    metrics = _eval_signals(rows, legacy_pos2, baselines)

    rep = DetectionReport(
        n_edges=n,
        n_correct=counts["correct"],
        n_wrong=counts["wrong"],
        n_unmatched=counts["unmatched"],
        n_ambiguous=counts["ambiguous"],
        modes=modes,
    )
    # Stash legacy metrics on the dataclass for callers that expect .metrics
    rep.metrics = metrics  # type: ignore[attr-defined]
    return rep
