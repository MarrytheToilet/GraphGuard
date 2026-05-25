#!/usr/bin/env python3
"""Build the final aggregate report from per-experiment artifacts.

Example:
  python scripts/make_report.py --out reports/docred_main
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from graphguard.db.database import open_db
from graphguard.reports.build import make_report


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--docred-config", default="configs/docred.yaml")
    ap.add_argument("--db", default=None)
    ap.add_argument("--out", default="reports/docred_main")
    ap.add_argument("--e0", default="data/processed/e0_report.json")
    ap.add_argument("--e1", default="data/processed/e1_report.json")
    ap.add_argument("--e2", default="data/processed/e2_report.json")
    ap.add_argument("--e3", default="data/processed/e3_report.json")
    ap.add_argument("--e4", default="data/processed/e4_report.json")
    ap.add_argument("--repair", default="data/processed/repair_report.json")
    ap.add_argument("--e5-audit", dest="e5_audit",
                    default="data/processed/e5_audit_report.json")
    ap.add_argument("--cases", type=int, default=5)
    args = ap.parse_args()
    cfg = yaml.safe_load(Path(args.docred_config).read_text(encoding="utf-8"))
    db_path = args.db or cfg["storage"]["db_path"]
    conn = open_db(db_path)
    summary = make_report(
        conn, args.out,
        e0_path=args.e0, e1_path=args.e1, e2_path=args.e2,
        e3_path=args.e3, e4_path=args.e4, repair_path=args.repair,
        e5_audit_path=args.e5_audit,
        k_cases=args.cases,
    )
    print(f"[done] cases={len(summary['case_studies'])}  "
          f"artifacts={list(summary['artifacts'].keys())}  out={args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
