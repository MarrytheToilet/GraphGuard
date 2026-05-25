"""Compute and persist baseline detector signals for E2/E5.

Runs the no-LLM baselines (confidence_inv, source_prov_inv,
subj_obj_cooccur_inv, majority_vote_inv) into ``edge_baseline_scores``.

Usage:
    python scripts/run_baselines.py --db data/processed/runs/<run>/<run>.db
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from graphguard.db.database import open_db
from graphguard.scoring import baselines


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--report", default=None,
                    help="Optional JSON file to write baseline counts")
    args = ap.parse_args()

    conn = open_db(args.db)
    counts = baselines.compute_all(conn)
    print("baseline_signal_counts:", counts)
    if args.report:
        with open(args.report, "w") as f:
            json.dump({"counts": counts, "signals": baselines.list_signals(conn)}, f, indent=2)
        print(f"wrote {args.report}")


if __name__ == "__main__":
    main()
