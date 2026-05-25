"""SQLite connection helpers and schema migration."""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Optional

SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def connect(db_path: str | Path) -> sqlite3.Connection:
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), timeout=120.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA busy_timeout = 120000;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    conn.execute("PRAGMA wal_autocheckpoint = 1000;")
    return conn


def init_schema(conn: sqlite3.Connection, schema_path: Optional[str | Path] = None) -> None:
    sql = Path(schema_path or SCHEMA_PATH).read_text(encoding="utf-8")
    conn.executescript(sql)
    _run_migrations(conn)
    conn.commit()


def _run_migrations(conn: sqlite3.Connection) -> None:
    """Idempotent column-additions for evolving schemas."""
    cur = conn.execute("PRAGMA table_info(intervention_candidates)").fetchall()
    cols = {r[1] for r in cur}
    if "semantic_class" not in cols:
        conn.execute("ALTER TABLE intervention_candidates ADD COLUMN semantic_class TEXT")
    if "cause_family" not in cols:
        conn.execute("ALTER TABLE intervention_candidates ADD COLUMN cause_family TEXT")

    cfr_cols = {r[1] for r in conn.execute("PRAGMA table_info(counterfactual_runs)").fetchall()}
    if "cf_event_id" not in cfr_cols:
        conn.execute("ALTER TABLE counterfactual_runs ADD COLUMN cf_event_id TEXT")
    # always attempt backfill (only touches rows with NULL cf_event_id; idempotent)
    _backfill_cf_event_ids(conn)


def _backfill_cf_event_ids(conn: sqlite3.Connection) -> None:
    """Match every cfr to its real cf extraction_event via the unique configuration
    tuple (document_id, schema_id, prompt_id, model_id, temperature, seed), then
    tie-break on nearest created_at. Replaces the legacy time-window heuristic."""
    rows = conn.execute(
        "SELECT run_id, document_id, schema_id, prompt_id, model_id, "
        "       temperature, seed, created_at "
        "FROM counterfactual_runs WHERE cf_event_id IS NULL"
    ).fetchall()
    for r in rows:
        ee = conn.execute(
            "SELECT event_id FROM extraction_events "
            "WHERE document_id=? AND schema_id=? AND prompt_id=? AND model_id=? "
            "  AND temperature=? AND seed=? "
            "ORDER BY abs(julianday(created_at) - julianday(?)) ASC LIMIT 1",
            (r["document_id"], r["schema_id"], r["prompt_id"], r["model_id"],
             r["temperature"], r["seed"], r["created_at"]),
        ).fetchone()
        if ee:
            conn.execute(
                "UPDATE counterfactual_runs SET cf_event_id=? WHERE run_id=?",
                (ee["event_id"], r["run_id"]),
            )
    conn.commit()


def open_db(db_path: str | Path) -> sqlite3.Connection:
    """Open and ensure schema."""
    conn = connect(db_path)
    init_schema(conn)
    return conn
