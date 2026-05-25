#!/usr/bin/env python3
"""K5: cross-model recall stability.

For documents that appear in V3, Qwen3-32B, and Kimi-K2 smoke runs, compute
per-document recall against DocRED gold edges for each model.  K5 is violated
if |recall_A - recall_B| > tau on more than alpha fraction of shared documents.

Outputs:
  reports/cross_run/k5_cross_model.json
  reports/cross_run/k5_cross_model.md
"""
from __future__ import annotations
import json, sqlite3, sys, math
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parents[1]
RUNS = {
    "DeepSeek-V4-Flash (v5 primary, 300 docs)": "docred__deepseek-v4-flash__300d",
    "Qwen3-32B (legacy, 100 docs)":              "docred__qwen3-32b__100d",
    "Kimi-K2 (legacy, 100 docs)":                "docred__kimi-k2__100d",
    "GLM-5 (v5 partial, 100 docs)":              "docred__glm-5__100d",
}
TAU   = 0.20
ALPHA = 0.20


def per_doc_recall(db_path: Path) -> dict[str, float]:
    """Return {document_id: recall@gold over base extraction events}.

    Edges are matched by (head_name, relation, tail_name) tuple.  Both gold
    and predicted edges are normalized by lower-casing entity strings.
    """
    c = sqlite3.connect(str(db_path)).cursor()
    docs = [r[0] for r in c.execute(
        "SELECT DISTINCT document_id FROM extraction_events").fetchall()]
    out: dict[str, float] = {}
    for doc in docs:
        gold_rows = c.execute(
            "SELECT head_name, relation_base, tail_name "
            "FROM gold_edges WHERE document_id=?", (doc,)).fetchall()
        gold = {(h.lower(), r, t.lower()) for h, r, t in gold_rows}
        if not gold:
            continue
        ev = c.execute(
            "SELECT event_id FROM extraction_events "
            "WHERE document_id=? ORDER BY created_at LIMIT 1", (doc,)).fetchone()
        if ev is None:
            continue
        ev_id = ev[0]
        pred_rows = c.execute(
            "SELECT subject_name, relation, object_name "
            "FROM extracted_edges WHERE event_id=?", (ev_id,)).fetchall()
        pred = {(h.lower(), r, t.lower()) for h, r, t in pred_rows}
        rec = len(gold & pred) / len(gold)
        out[doc] = rec
    return out


def main():
    recalls = {}
    for model, run in RUNS.items():
        db = ROOT / "data/processed/runs" / run / f"{run}.db"
        recalls[model] = per_doc_recall(db)
        print(f"{model}: {len(recalls[model])} docs with gold")

    shared = set.intersection(*(set(d) for d in recalls.values()))
    print("shared:", len(shared))

    pairs = [("DeepSeek-V4-Flash (v5 primary, 300 docs)", "Qwen3-32B (legacy, 100 docs)"),
             ("DeepSeek-V4-Flash (v5 primary, 300 docs)", "Kimi-K2 (legacy, 100 docs)"),
             ("DeepSeek-V4-Flash (v5 primary, 300 docs)", "GLM-5 (v5 partial, 100 docs)"),
             ("Qwen3-32B (legacy, 100 docs)",            "Kimi-K2 (legacy, 100 docs)")]
    out = {"tau": TAU, "alpha": ALPHA, "shared_docs": len(shared), "pairs": {}}
    md = ["# K5 cross-model recall stability\n",
          f"Shared documents (V3 ∩ Qwen3 ∩ Kimi): **{len(shared)}**.  "
          f"τ = {TAU}, α = {ALPHA}.  Bootstrap 95% CIs use B=2000 percentile resamples.\n",
          "| pair | mean recall A | mean recall B | mean \\|Δrecall\\| | fraction \\|Δ\\|>τ | 95% CI | verdict |",
          "|---|---:|---:|---:|---:|---|:---:|"]
    import random
    random.seed(0)
    B = 2000
    shared_list = sorted(shared)
    for a, b in pairs:
        ra = [recalls[a][d] for d in shared_list]
        rb = [recalls[b][d] for d in shared_list]
        diffs = [abs(x - y) for x, y in zip(ra, rb)]
        n = len(diffs)
        ma, mb, md_diff = sum(ra)/n, sum(rb)/n, sum(diffs)/n
        frac_violate = sum(1 for d in diffs if d > TAU) / n
        boots = []
        for _ in range(B):
            idx = [random.randrange(n) for _ in range(n)]
            boots.append(sum(1 for i in idx if diffs[i] > TAU) / n)
        boots.sort()
        lo, hi = boots[int(0.025*B)], boots[int(0.975*B)]
        verdict = "VIOLATED" if lo > ALPHA else ("SATISFIED" if hi < ALPHA else "INCONCLUSIVE")
        out["pairs"][f"{a} vs {b}"] = dict(
            n=n, mean_recall_A=ma, mean_recall_B=mb,
            mean_abs_diff=md_diff, frac_above_tau=frac_violate,
            ci_low=lo, ci_high=hi, verdict=verdict)
        md.append(f"| {a} vs {b} | {ma:.3f} | {mb:.3f} | {md_diff:.3f} "
                  f"| {frac_violate:.2f} | [{lo:.2f}, {hi:.2f}] | **{verdict}** |")

    out_path = ROOT / "reports/cross_run/k5_cross_model.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    json.dump(out, open(out_path, "w"), indent=2)
    md_path = ROOT / "reports/cross_run/k5_cross_model.md"
    md_path.write_text("\n".join(md) + "\n")
    print("wrote", out_path, "and", md_path)


if __name__ == "__main__":
    main()
