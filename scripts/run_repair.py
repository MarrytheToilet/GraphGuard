#!/usr/bin/env python3
"""M6/E5: graph repair — evaluate filtering strategies vs DocRED gold.

Requires `edge_correctness` to be populated (run scripts/run_e2_error_detection.py first).

Example:
  python scripts/run_repair.py --report data/processed/repair_report.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from graphguard.db.database import open_db
from graphguard.experiments.e6_repair import evaluate_repair


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--docred-config", default="configs/docred.yaml")
    ap.add_argument("--db", default=None)
    ap.add_argument("--fractions", default="0.0,0.1,0.2,0.3,0.5")
    ap.add_argument("--report", default="data/processed/repair_report.json")
    args = ap.parse_args()
    cfg = yaml.safe_load(Path(args.docred_config).read_text(encoding="utf-8"))
    db_path = args.db or cfg["storage"]["db_path"]
    conn = open_db(db_path)
    fracs = tuple(float(x) for x in args.fractions.split(","))
    points = evaluate_repair(conn, fractions=fracs)
    rows = [p.__dict__ for p in points]
    Path(args.report).parent.mkdir(parents=True, exist_ok=True)
    Path(args.report).write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[done] points={len(rows)} report={args.report}")
    print("method            frac    kept   tp  fp  fn   prec   rec    f1")
    for p in points:
        print(f"  {p.method:<16} {p.fraction_removed:<6.2f} {p.n_kept:<6} "
              f"{p.tp:<3} {p.fp:<3} {p.fn:<3}  {p.precision:.3f}  {p.recall:.3f}  {p.f1:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
