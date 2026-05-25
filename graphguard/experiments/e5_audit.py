"""E5: Graph Reliability Audit and Human Review Prioritization.

Reframes the prior "repair" experiment as an *audit* task: given a finite
human-review budget, how many true errors does each scoring signal surface?

Metrics reported per signal (risk / schema_sensitivity / stability /
confidence / random):

  * error_hit_rate@K        — fraction of top-K reviewed edges that are errors
  * errors_per_100_reviewed — at K = 100 (or scaled to N if smaller)
  * precision_at_removal[f] — graph precision after removing top-f% by score
  * pr_curve                — list of (recall, precision) at varying K
  * cumulative_errors_caught at K = 5%, 10%, 20%, 50%

Multi-mode positives (matches E2):

  * strict     positive = wrong + unmatched
  * clean      restricted to correct vs wrong only (drops unmatched)
  * wrong_only positive = wrong only; unmatched treated as negative noise
"""
from __future__ import annotations

import logging
import random
import sqlite3
from dataclasses import dataclass, field
from typing import Iterable, List

log = logging.getLogger(__name__)


@dataclass
class AuditMetrics:
    n_eval: int
    n_pos: int
    prevalence: float
    by_signal: dict = field(default_factory=dict)


def _gather(conn: sqlite3.Connection):
    return list(conn.execute(
        "SELECT e.edge_id, e.document_id, e.confidence, ec.label, "
        "       COALESCE(s.risk_score, 0)             AS risk, "
        "       COALESCE(s.prompt_sensitivity, 0)     AS prompt_s, "
        "       COALESCE(s.schema_sensitivity, 0)     AS schema_s, "
        "       COALESCE(s.text_responsibility, 0)    AS text_r, "
        "       COALESCE(s.stability_score, 1)        AS stability, "
        "       COALESCE(s.stochastic_variance, 0)    AS stoch "
        "FROM extracted_edges e "
        "LEFT JOIN edge_correctness ec ON ec.edge_id = e.edge_id "
        "LEFT JOIN edge_reliability_scores s ON s.edge_id = e.edge_id "
        "WHERE ec.label IS NOT NULL"
    ))


def _hit_rate_at_k(scored, labels_pos, k: int) -> float:
    pairs = sorted(zip(scored, labels_pos), key=lambda x: x[0], reverse=True)
    if k <= 0 or k > len(pairs):
        k = len(pairs)
    if k == 0:
        return 0.0
    return sum(p[1] for p in pairs[:k]) / k


def _cum_errors_at(scored, labels_pos, k: int) -> int:
    pairs = sorted(zip(scored, labels_pos), key=lambda x: x[0], reverse=True)
    return sum(p[1] for p in pairs[:k])


def _pr_curve(scored, labels_pos, n_points: int = 30):
    pairs = sorted(zip(scored, labels_pos), key=lambda x: x[0], reverse=True)
    n = len(pairs)
    n_pos = sum(labels_pos)
    if not n or not n_pos:
        return []
    step = max(1, n // n_points)
    out = []
    hits = 0
    for i, (_, is_pos) in enumerate(pairs, 1):
        hits += is_pos
        if i % step == 0 or i == n:
            precision = hits / i
            recall = hits / n_pos
            out.append({"k": i, "k_pct": round(i / n, 4),
                        "precision": round(precision, 4),
                        "recall": round(recall, 4)})
    return out


def _precision_at_removal(rows, scored_high_first, frac: float) -> dict:
    """Drop the top-`frac` highest-scored edges, then measure precision on the kept set.
    Lower precision lift → signal is mis-targeting; higher → useful for filtering.
    """
    n = len(rows)
    n_drop = int(round(n * frac))
    if n_drop <= 0:
        n_drop = 0
    if n_drop >= n:
        n_drop = n - 1
    pairs = sorted(zip(scored_high_first, rows), key=lambda x: x[0], reverse=True)
    kept = [r for _, r in pairs[n_drop:]]
    tp = sum(1 for r in kept if r["label"] == "correct")
    fp = sum(1 for r in kept if r["label"] in ("wrong", "unmatched"))
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    return {"frac_removed": frac, "n_kept": len(kept),
            "tp": tp, "fp": fp,
            "precision": round(precision, 4)}


def _eval_signals_for_mode(rows, labels_pos, k_grid, baselines: dict | None = None):
    rng = random.Random(0)
    signals = {
        "risk":               [r["risk"] for r in rows],
        "prompt_sensitivity": [r["prompt_s"] for r in rows],
        "schema_sensitivity": [r["schema_s"] for r in rows],
        "stochastic_variance":[r["stoch"] for r in rows],
        "1_minus_stability":  [1.0 - r["stability"] for r in rows],
        "1_minus_confidence": [1.0 - (r["confidence"] or 0.0) for r in rows],
        "random":             [rng.random() for _ in rows],
    }
    if baselines:
        sig_names: set[str] = set()
        for v in baselines.values():
            sig_names.update(v.keys())
        for name in sorted(sig_names):
            signals[f"baseline:{name}"] = [
                float(baselines.get(r["edge_id"], {}).get(name, 0.0)) for r in rows
            ]
    out = {}
    n = len(rows)
    n_pos = sum(labels_pos)
    for name, sc in signals.items():
        hit_rates = {f"hit@{k}": round(_hit_rate_at_k(sc, labels_pos, k), 4) for k in k_grid}
        cum_pcts = {}
        for pct in (0.05, 0.10, 0.20, 0.50):
            k = max(1, int(round(n * pct)))
            cum_pcts[f"errors_caught@{int(pct*100)}pct"] = _cum_errors_at(sc, labels_pos, k)
        # Errors per 100 reviewed (scale to N if N<100)
        k100 = min(100, n)
        errs_per_100 = round(_cum_errors_at(sc, labels_pos, k100) / k100 * 100, 2)
        prec_at_removal = [
            _precision_at_removal(rows, sc, f) for f in (0.0, 0.05, 0.10, 0.20, 0.30)
        ]
        out[name] = {
            "hit_rates": hit_rates,
            "errors_per_100_reviewed": errs_per_100,
            "cumulative_errors": cum_pcts,
            "precision_at_removal": prec_at_removal,
            "pr_curve": _pr_curve(sc, labels_pos),
        }
    return out


def evaluate_audit(conn: sqlite3.Connection,
                   k_grid: tuple[int, ...] = (10, 25, 50, 100, 200)) -> dict:
    rows = _gather(conn)
    if not rows:
        return {"n_edges": 0, "modes": {}}

    from ..scoring.baselines import load_for_edges
    baselines = load_for_edges(conn, [r["edge_id"] for r in rows])

    counts = {
        "correct": sum(1 for r in rows if r["label"] == "correct"),
        "wrong": sum(1 for r in rows if r["label"] == "wrong"),
        "unmatched": sum(1 for r in rows if r["label"] == "unmatched"),
        "ambiguous": sum(1 for r in rows if r["label"] == "ambiguous"),
    }
    modes = {}

    # strict
    pos = [1 if r["label"] in ("wrong", "unmatched") else 0 for r in rows]
    modes["strict"] = {
        "definition": "positive = wrong + unmatched",
        "n_eval": len(rows), "n_pos": sum(pos),
        "prevalence": round(sum(pos) / max(1, len(rows)), 4),
        "signals": _eval_signals_for_mode(rows, pos, k_grid, baselines),
    }

    # clean: drop unmatched
    clean = [r for r in rows if r["label"] in ("correct", "wrong")]
    if clean:
        cpos = [1 if r["label"] == "wrong" else 0 for r in clean]
        modes["clean"] = {
            "definition": "drop unmatched; correct vs wrong only",
            "n_eval": len(clean), "n_pos": sum(cpos),
            "prevalence": round(sum(cpos) / max(1, len(clean)), 4),
            "signals": _eval_signals_for_mode(clean, cpos, k_grid, baselines),
        }

    # wrong_only
    wpos = [1 if r["label"] == "wrong" else 0 for r in rows]
    if sum(wpos) > 0:
        modes["wrong_only"] = {
            "definition": "positive = wrong only; unmatched treated as negative",
            "n_eval": len(rows), "n_pos": sum(wpos),
            "prevalence": round(sum(wpos) / max(1, len(rows)), 4),
            "signals": _eval_signals_for_mode(rows, wpos, k_grid, baselines),
        }

    return {
        "n_edges": len(rows),
        "n_correct": counts["correct"],
        "n_wrong": counts["wrong"],
        "n_unmatched": counts["unmatched"],
        "n_ambiguous": counts["ambiguous"],
        "k_grid": list(k_grid),
        "modes": modes,
    }
