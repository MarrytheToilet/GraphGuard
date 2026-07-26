#!/usr/bin/env python3
"""K5 across model sizes within one family (PVLDB revision, Rev6-W5).

Evaluates the cross-model recall-stability contract K5 over the dense Qwen3
size ladder (8B / 14B / 32B) plus the primary extractor, using the same
protocol as scripts/run_k5_cross_model.py: identifier-first per-document
recall against gold edges, pairwise |Delta recall| with
tolerance TAU on at most ALPHA of shared documents, bootstrap 95% CI
verdicts. Also reports pairwise graph drift between the size variants'
base views for context.

Outputs reports/cross_run/k5_model_size.json / .md.
"""
from __future__ import annotations

import json
import random
import sqlite3
import sys
from itertools import combinations
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from graphguard.contracts import REGISTRY  # noqa: E402
from graphguard.contracts import metrics as M  # noqa: E402

RUNS = {
    "Qwen3-8B":  "docred__qwen3-8b__100d",
    "Qwen3-14B": "docred__qwen3-14b__100d",
    "Qwen3-32B": "docred__qwen3-32b__100d",
    "DeepSeek-V4-Flash": "docred__deepseek-v4-flash__300d",
}
SIZE_ORDER = ["Qwen3-8B", "Qwen3-14B", "Qwen3-32B", "DeepSeek-V4-Flash"]
TAU = REGISTRY["K5"].threshold
ALPHA = REGISTRY["K5"].alpha
B = 2000


def per_doc_recall_and_edges(db_path: Path):
    """Protocol identical to run_k5_cross_model.per_doc_recall, plus the
    predicted edge set of the same base event for drift computation."""
    con = sqlite3.connect(str(db_path))
    con.row_factory = sqlite3.Row
    c = con.cursor()
    recall: dict[str, float] = {}
    edges: dict[str, list] = {}
    for (doc,) in c.execute("SELECT DISTINCT document_id FROM extraction_events").fetchall():
        gold = list(c.execute(
            "SELECT head_entity_id, head_name, relation_base, "
            "tail_entity_id, tail_name FROM gold_edges WHERE document_id=?",
            (doc,)))
        if not gold:
            continue
        ev = c.execute("SELECT event_id FROM extraction_events "
                       "WHERE document_id=? ORDER BY created_at LIMIT 1", (doc,)).fetchone()
        if ev is None:
            continue
        pred = list(c.execute(
            "SELECT subject_entity_id, subject_name, relation, "
            "object_entity_id, object_name "
            "FROM extracted_edges WHERE event_id=?", (ev[0],)))
        recall[doc] = M.gold_recall(pred, gold)
        edges[doc] = pred
    con.close()
    return recall, edges


def main() -> int:
    recalls, edge_sets = {}, {}
    for name, run in RUNS.items():
        db = ROOT / "data/processed/runs" / run / f"{run}.db"
        if not db.exists():
            print(f"[skip] {name}: missing {db}")
            continue
        recalls[name], edge_sets[name] = per_doc_recall_and_edges(db)
        print(f"{name}: {len(recalls[name])} docs with gold, "
              f"mean recall {sum(recalls[name].values())/max(1,len(recalls[name])):.3f}")

    names = [n for n in SIZE_ORDER if n in recalls]
    shared = sorted(set.intersection(*(set(recalls[n]) for n in names)))
    print("shared docs:", len(shared))

    rng = random.Random(0)
    out = {"tau": TAU, "alpha": ALPHA, "shared_docs": len(shared),
           "mean_recall": {n: sum(recalls[n][d] for d in shared) / len(shared) for n in names},
           "pairs": {}}
    md = ["# K5 across model sizes (Qwen3 family)\n",
          f"Shared documents: **{len(shared)}**. tau = {TAU}, alpha = {ALPHA}, B = {B}.\n",
          "| pair | recall A | recall B | mean |dR| | frac>tau | 95% CI | drift | verdict |",
          "|---|---:|---:|---:|---:|---|---:|:---:|"]
    for a, b in combinations(names, 2):
        ra = [recalls[a][d] for d in shared]
        rb = [recalls[b][d] for d in shared]
        diffs = [abs(x - y) for x, y in zip(ra, rb)]
        n = len(diffs)
        frac = sum(1 for d in diffs if d > TAU) / n
        boots = sorted(
            sum(1 for i in (rng.randrange(n) for _ in range(n)) if diffs[i] > TAU) / n
            for _ in range(B))
        lo, hi = boots[int(0.025 * B)], boots[int(0.975 * B)]
        verdict = "VIOLATED" if lo > ALPHA else ("SATISFIED" if hi < ALPHA else "INCONCLUSIVE")
        drift = sum(
            1.0 - M.edge_jaccard(edge_sets[a][d], edge_sets[b][d])
            for d in shared
        ) / n
        out["pairs"][f"{a} vs {b}"] = dict(
            n=n, mean_recall_A=sum(ra) / n, mean_recall_B=sum(rb) / n,
            mean_abs_diff=sum(diffs) / n, frac_above_tau=frac,
            ci_low=lo, ci_high=hi, mean_graph_drift=drift, verdict=verdict)
        md.append(f"| {a} vs {b} | {sum(ra)/n:.3f} | {sum(rb)/n:.3f} | "
                  f"{sum(diffs)/n:.3f} | {frac:.2f} | [{lo:.2f}, {hi:.2f}] | "
                  f"{drift:.2f} | **{verdict}** |")
        print(md[-1])

    out_path = ROOT / "reports/cross_run/k5_model_size.json"
    out_path.write_text(json.dumps(out, indent=2))
    (ROOT / "reports/cross_run/k5_model_size.md").write_text("\n".join(md) + "\n")
    print("wrote", out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
