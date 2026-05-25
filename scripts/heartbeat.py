#!/usr/bin/env python
"""Heartbeat: periodically emit row counts from each run DB so users can see progress."""
from __future__ import annotations

import sqlite3
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUNS = ROOT / "data/processed/runs"
INTERVAL = int(sys.argv[1]) if len(sys.argv) > 1 else 60


def snapshot() -> str:
    parts = [time.strftime("%H:%M:%S")]
    for run_dir in sorted(RUNS.iterdir()):
        db = run_dir / f"{run_dir.name}.db"
        if not db.exists():
            continue
        try:
            con = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=2.0)
            ev = con.execute("SELECT COUNT(*) FROM extraction_events").fetchone()[0]
            cf = con.execute("SELECT COUNT(*) FROM counterfactual_runs").fetchone()[0]
            try:
                docs = con.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
            except sqlite3.OperationalError:
                docs = 0
            con.close()
            parts.append(f"{run_dir.name}: docs={docs} ev={ev} cf={cf}")
        except sqlite3.OperationalError as exc:
            parts.append(f"{run_dir.name}: locked ({exc})")
    return " | ".join(parts)


if __name__ == "__main__":
    while True:
        print("[heartbeat] " + snapshot(), flush=True)
        time.sleep(INTERVAL)
