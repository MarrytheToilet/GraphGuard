#!/usr/bin/env python3
"""Clone an existing GraphGuard SQLite DB and wipe model-dependent tables.

The result is a DB that retains:
  - documents, sentences, entities, gold_edges
  - prompts, schemas, prompt_clauses
  - intervention_candidates  (model-independent: derived from sentences/clauses)

But starts empty for:
  - extraction_events, extracted_edges
  - counterfactual_runs, edge_outcomes
  - edge_correctness, edge_reliability_scores, stability_reports
  - llm_call_cache  (so the new model doesn't reuse stale envelopes)

This lets a different LLM (e.g. MiniMax-M2.5) run the full pipeline against
identical data prep, producing comparable per-model metrics.
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

WIPE_TABLES = [
    "edge_outcomes",
    "counterfactual_runs",
    "edge_reliability_scores",
    "edge_correctness",
    "stability_reports",
    "extracted_edges",
    "extraction_events",
    "llm_call_cache",
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True, help="Source DB (with prep + interventions).")
    ap.add_argument("--dst", required=True, help="Destination DB to create.")
    ap.add_argument("--keep-cache", action="store_true",
                    help="Preserve llm_call_cache (cache key includes model, "
                         "so foreign envelopes are inert but waste space).")
    args = ap.parse_args()

    src = Path(args.src)
    dst = Path(args.dst)
    if not src.exists():
        print(f"[error] source DB not found: {src}", file=sys.stderr)
        return 1
    dst.parent.mkdir(parents=True, exist_ok=True)

    for suffix in ("", "-wal", "-shm"):
        p = Path(str(dst) + suffix)
        if p.exists():
            p.unlink()

    # Use SQLite's online backup API so we can clone safely while the source
    # may still be receiving writes (WAL-aware, atomic snapshot).
    src_conn = sqlite3.connect(f"file:{src}?mode=ro", uri=True)
    dst_conn = sqlite3.connect(dst)
    try:
        src_conn.backup(dst_conn)
    finally:
        src_conn.close()
        dst_conn.close()
    print(f"[clone] {src} -> {dst} (online backup)")

    conn = sqlite3.connect(dst)
    conn.executescript("PRAGMA foreign_keys = OFF;")
    cur = conn.cursor()
    for t in WIPE_TABLES:
        if args.keep_cache and t == "llm_call_cache":
            continue
        try:
            cur.execute(f"DELETE FROM {t}")
            print(f"  wiped {t}")
        except sqlite3.OperationalError as e:
            print(f"  skip {t}: {e}")
    conn.commit()
    conn.execute("VACUUM")
    conn.close()

    print(f"[done] dst={dst}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
