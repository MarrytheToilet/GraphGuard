#!/usr/bin/env python3
"""Compute and persist edge_reliability_scores from edge_outcomes.

Example:
  python scripts/compute_scores.py
  python scripts/compute_scores.py --top 20
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from graphguard.db.database import open_db    # noqa: E402
from graphguard.scoring.risk import compute_all  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--docred-config", default="configs/docred.yaml")
    ap.add_argument("--db", default=None)
    ap.add_argument("--top", type=int, default=10, help="Print top-K riskiest edges after compute.")
    args = ap.parse_args()

    cfg = yaml.safe_load(Path(args.docred_config).read_text(encoding="utf-8"))
    db_path = args.db or cfg["storage"]["db_path"]
    conn = open_db(db_path)
    n = compute_all(conn)
    print(f"[done] computed scores for {n} edges; db={db_path}")
    if args.top > 0:
        print(f"\nTop-{args.top} riskiest edges:")
        for r in conn.execute("""
            SELECT s.edge_id, s.risk_score, s.stability_score, s.prompt_sensitivity,
                   s.schema_sensitivity, s.text_responsibility,
                   e.subject_name, e.relation, e.object_name
            FROM edge_reliability_scores s JOIN extracted_edges e ON e.edge_id = s.edge_id
            ORDER BY s.risk_score DESC LIMIT ?
        """, (args.top,)):
            print(f"  risk={r['risk_score']:+.2f} stab={r['stability_score']:.2f} "
                  f"prompt={r['prompt_sensitivity']:.2f} schema={r['schema_sensitivity']:.2f} "
                  f"text={r['text_responsibility']:.2f}  ::  "
                  f"({r['subject_name']}) -[{r['relation']}]-> ({r['object_name']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
