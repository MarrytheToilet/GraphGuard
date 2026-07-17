#!/usr/bin/env python3
"""K5 model-size ladder with recall restricted to the declared schema.

Sensitivity companion to run_model_size_k5.py: gold recall there is computed
against the full DocRED annotation (92 relation types), while the extractor
can emit only the declared schema relations. This script recomputes per-
document recall with gold restricted to the declared relations (excluding
the OTHER escape), so the low K5 violation rate can be checked against the
metric-ceiling explanation. Protocol otherwise identical: pairwise
|Delta recall| with tolerance TAU on at most ALPHA of shared documents,
bootstrap 95% CI verdicts.

Requires the per-run lineage databases under data/processed/runs/ (they are
rebuildable via scripts/run_paper_experiment.py; the cached output of this
script ships as reports/cross_run/k5_model_size_expressible.json).
"""
from __future__ import annotations

import json
import random
import sqlite3
from itertools import combinations
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

RUNS = {
    "Qwen3-8B":  "docred__qwen3-8b__100d",
    "Qwen3-14B": "docred__qwen3-14b__100d",
    "Qwen3-32B": "docred__qwen3-32b__100d",
    "DeepSeek-V4-Flash": "docred__deepseek-v4-flash__300d",
}
TAU, ALPHA, B = 0.20, 0.20, 2000


def per_doc_recall(db_path: Path, allowed: set | None = None) -> dict[str, float]:
    c = sqlite3.connect(str(db_path)).cursor()
    rec: dict[str, float] = {}
    docs = [d for (d,) in c.execute(
        "SELECT DISTINCT document_id FROM extraction_events").fetchall()]
    for doc in docs:
        gold = {(h.lower(), r, t.lower()) for h, r, t in c.execute(
            "SELECT head_name, relation_base, tail_name FROM gold_edges "
            "WHERE document_id=?", (doc,)).fetchall()}
        if allowed is not None:
            gold = {g for g in gold if g[1] in allowed}
        if not gold:
            continue
        ev = c.execute("SELECT event_id FROM extraction_events "
                       "WHERE document_id=? ORDER BY created_at LIMIT 1",
                       (doc,)).fetchone()
        if ev is None:
            continue
        pred = {(h.lower(), r, t.lower()) for h, r, t in c.execute(
            "SELECT subject_name, relation, object_name FROM extracted_edges "
            "WHERE event_id=?", (ev[0],)).fetchall()}
        rec[doc] = len(gold & pred) / len(gold)
    return rec


def main() -> int:
    primary_db = (ROOT / "data/processed/runs" / RUNS["DeepSeek-V4-Flash"]
                  / f"{RUNS['DeepSeek-V4-Flash']}.db")
    c = sqlite3.connect(str(primary_db)).cursor()
    schema = json.loads(c.execute(
        "SELECT relation_types_json FROM schemas WHERE schema_id='docred_full'"
    ).fetchone()[0])
    allowed = {r["id"] for r in schema} - {"OTHER"}
    print(f"declared relations (excl OTHER): {len(allowed)}")

    full, expr = {}, {}
    for name, run in RUNS.items():
        db = ROOT / "data/processed/runs" / run / f"{run}.db"
        if not db.exists():
            print(f"[skip] {name}: missing {db}")
            return 1
        full[name] = per_doc_recall(db)
        expr[name] = per_doc_recall(db, allowed)

    names = list(RUNS)
    shared = sorted(set.intersection(*(set(expr[n]) for n in names)))
    shared_full = sorted(set.intersection(*(set(full[n]) for n in names)))
    print(f"shared docs: full {len(shared_full)}, expressible {len(shared)}")
    for n in names:
        fr = sum(full[n][d] for d in shared_full) / len(shared_full)
        er = sum(expr[n][d] for d in shared) / len(shared)
        print(f"{n:20s} full-gold R {fr:.3f}  expressible R {er:.3f}")

    rng = random.Random(0)
    out = {"allowed_relations": sorted(allowed), "shared_docs": len(shared),
           "tau": TAU, "alpha": ALPHA,
           "mean_recall_full": {n: sum(full[n][d] for d in shared_full) / len(shared_full)
                                for n in names},
           "mean_recall_expressible": {n: sum(expr[n][d] for d in shared) / len(shared)
                                       for n in names},
           "pairs": {}}
    for a, b in combinations(names, 2):
        diffs = [abs(expr[a][d] - expr[b][d]) for d in shared]
        n = len(diffs)
        frac = sum(1 for d in diffs if d > TAU) / n
        boots = sorted(
            sum(1 for i in (rng.randrange(n) for _ in range(n)) if diffs[i] > TAU) / n
            for _ in range(B))
        lo, hi = boots[int(0.025 * B)], boots[int(0.975 * B)]
        verdict = ("VIOLATED" if lo > ALPHA
                   else "SATISFIED" if hi < ALPHA else "INCONCLUSIVE")
        out["pairs"][f"{a} vs {b}"] = dict(
            mean_abs_diff=sum(diffs) / n, frac_above_tau=frac,
            ci=[lo, hi], verdict=verdict)
        print(f"{a} vs {b}: |dR|={sum(diffs)/n:.3f} frac>tau={frac:.2f} "
              f"CI=[{lo:.2f},{hi:.2f}] {verdict}")

    out_path = ROOT / "reports/cross_run/k5_model_size_expressible.json"
    out_path.write_text(json.dumps(out, indent=2))
    print("wrote", out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
