"""Shared helpers for E1/E5/E6/E7 — pair (intervention, base_event) → cf_event_id."""
from __future__ import annotations

import sqlite3
from typing import Iterator


def iter_doc_pairs(conn: sqlite3.Connection, document_id: str
                   ) -> Iterator[tuple[str, str, str, str, str]]:
    """Yield (intervention_id, run_id, base_event_id, cf_event_id, cause_family).

    Prefers the cf_event_id column when populated; otherwise falls back to a
    configuration-tuple join (document_id, schema_id, prompt_id, model_id,
    temperature, seed) with nearest-time tie-break. Never uses the legacy
    next-event-after-cfr heuristic, which silently cross-paired interventions
    that landed close in time.
    """
    rows = conn.execute(
        """
        SELECT cfr.intervention_id, cfr.run_id, cfr.base_event_id,
               cfr.created_at AS cf_at, cfr.cf_event_id,
               cfr.schema_id AS cfr_schema, cfr.prompt_id AS cfr_prompt,
               cfr.model_id AS cfr_model, cfr.temperature AS cfr_temp, cfr.seed AS cfr_seed,
               ic.cause_family, ic.semantic_class
        FROM counterfactual_runs cfr
        LEFT JOIN intervention_candidates ic
               ON ic.intervention_id = cfr.intervention_id
        WHERE cfr.document_id = ?
        ORDER BY cfr.created_at ASC
        """,
        (document_id,),
    ).fetchall()
    for r in rows:
        cf_event = r["cf_event_id"]
        if not cf_event:
            ee = conn.execute(
                """
                SELECT event_id FROM extraction_events
                WHERE document_id=? AND schema_id=? AND prompt_id=? AND model_id=?
                  AND temperature=? AND seed=?
                ORDER BY abs(julianday(created_at) - julianday(?)) ASC LIMIT 1
                """,
                (document_id, r["cfr_schema"], r["cfr_prompt"], r["cfr_model"],
                 r["cfr_temp"], r["cfr_seed"], r["cf_at"]),
            ).fetchone()
            cf_event = ee["event_id"] if ee else None
        if cf_event is None:
            continue
        yield (r["intervention_id"], r["run_id"], r["base_event_id"],
               cf_event, r["cause_family"] or "unknown")


def base_event_for(conn: sqlite3.Connection, document_id: str) -> str | None:
    r = conn.execute(
        """SELECT event_id FROM extraction_events
           WHERE document_id=? ORDER BY created_at ASC LIMIT 1""",
        (document_id,),
    ).fetchone()
    return r["event_id"] if r else None


def edges_of(conn: sqlite3.Connection, event_id: str) -> list[sqlite3.Row]:
    return list(conn.execute(
        "SELECT * FROM extracted_edges WHERE event_id = ?", (event_id,)
    ))
