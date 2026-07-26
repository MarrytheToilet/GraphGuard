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
    # The former matcher-validation audit was never populated with adjudicated
    # labels. Retire its empty legacy table instead of leaving an apparent
    # evidence source in upgraded databases.
    conn.execute("DROP TABLE IF EXISTS matching_validation")

    cur = conn.execute("PRAGMA table_info(intervention_candidates)").fetchall()
    cols = {r[1] for r in cur}
    if "semantic_class" not in cols:
        conn.execute("ALTER TABLE intervention_candidates ADD COLUMN semantic_class TEXT")
    if "cause_family" not in cols:
        conn.execute("ALTER TABLE intervention_candidates ADD COLUMN cause_family TEXT")

    cfr_cols = {r[1] for r in conn.execute("PRAGMA table_info(counterfactual_runs)").fetchall()}
    if "cf_event_id" not in cfr_cols:
        conn.execute("ALTER TABLE counterfactual_runs ADD COLUMN cf_event_id TEXT")
    # Always re-resolve legacy rows: an early time/configuration-only migration
    # could populate a non-NULL but incorrect event identifier.
    _backfill_cf_event_ids(conn)


def _backfill_cf_event_ids(conn: sqlite3.Connection) -> None:
    """Resolve every counterfactual run to the extraction event it produced.

    New runs persist ``cf_event_id`` directly. Some legacy databases were
    backfilled from a configuration/time join; when several calls with the
    same configuration finished close together, that join could select the
    wrong event. A matched edge is an authoritative event witness. Otherwise,
    the run's copied token/latency fields disambiguate the extraction event
    before the configuration/time fallback is used.
    """
    rows = conn.execute(
        "SELECT run_id, document_id, schema_id, prompt_id, model_id, "
        "       temperature, seed, token_input, token_output, latency_ms, "
        "       created_at, cf_event_id "
        "FROM counterfactual_runs"
    ).fetchall()
    for r in rows:
        matched = conn.execute(
            "SELECT matched_edge_id FROM edge_outcomes "
            "WHERE run_id=? AND matched_edge_id IS NOT NULL "
            "AND matched_edge_id<>'' ORDER BY rowid LIMIT 1",
            (r["run_id"],),
        ).fetchone()
        resolved = (
            matched["matched_edge_id"].rsplit("::", 1)[0]
            if matched else None
        )
        if not resolved:
            ee = conn.execute(
                "SELECT event_id FROM extraction_events "
                "WHERE document_id=? AND schema_id=? AND prompt_id=? "
                "  AND model_id=? AND temperature=? AND seed=? "
                "  AND COALESCE(token_input,-1)=COALESCE(?,-1) "
                "  AND COALESCE(token_output,-1)=COALESCE(?,-1) "
                "  AND COALESCE(latency_ms,-1)=COALESCE(?,-1) "
                "ORDER BY abs(julianday(created_at) - julianday(?)) ASC "
                "LIMIT 1",
                (
                    r["document_id"], r["schema_id"], r["prompt_id"],
                    r["model_id"], r["temperature"], r["seed"],
                    r["token_input"], r["token_output"], r["latency_ms"],
                    r["created_at"],
                ),
            ).fetchone()
            resolved = ee["event_id"] if ee else None
        if not resolved:
            ee = conn.execute(
                "SELECT event_id FROM extraction_events "
                "WHERE document_id=? AND schema_id=? AND prompt_id=? "
                "  AND model_id=? AND temperature=? AND seed=? "
                "ORDER BY abs(julianday(created_at) - julianday(?)) ASC "
                "LIMIT 1",
                (
                    r["document_id"], r["schema_id"], r["prompt_id"],
                    r["model_id"], r["temperature"], r["seed"],
                    r["created_at"],
                ),
            ).fetchone()
            resolved = ee["event_id"] if ee else None
        if resolved and resolved != r["cf_event_id"]:
            conn.execute(
                "UPDATE counterfactual_runs SET cf_event_id=? WHERE run_id=?",
                (resolved, r["run_id"]),
            )
    conn.commit()


def open_db(db_path: str | Path) -> sqlite3.Connection:
    """Open and ensure schema."""
    conn = connect(db_path)
    init_schema(conn)
    return conn
