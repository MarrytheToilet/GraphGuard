#!/usr/bin/env python3
"""Rebuild the E4 planner cost-quality artifact from a lineage database.

This is an offline replay over cached counterfactual outcomes.  The
``shared_run_reuse`` field is edge-outcome fan-out (the average number of base
edges informed by a selected intervention), not endpoint materialization
savings across contracts.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from graphguard.experiments.e4_cost_quality import cost_quality_auc, evaluate


DEFAULT_PLANNERS = [
    "exhaustive",
    "random",
    "span_only",
    "prompt_only",
    "schema_only",
    "graphguard",
    "adaptive_graphguard",
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True)
    parser.add_argument("--planners", nargs="+", default=DEFAULT_PLANNERS)
    parser.add_argument(
        "--budgets", nargs="+", type=int, default=[1, 2, 3, 4, 6, 8]
    )
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--report", required=True)
    args = parser.parse_args()

    db_path = Path(args.db).resolve()
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        points = evaluate(
            conn,
            planners=args.planners,
            budgets=args.budgets,
            top_k=args.top_k,
        )
    finally:
        conn.close()

    report = {
        "points": [point.__dict__ for point in points],
        "cost_quality_auc": cost_quality_auc(points),
        "top_k": args.top_k,
        "shared_run_reuse_definition": (
            "average number of base-edge outcomes informed by a selected "
            "intervention extraction"
        ),
    }
    out = Path(args.report)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"[e4] points={len(points)} report={out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
