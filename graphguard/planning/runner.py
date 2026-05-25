"""Counterfactual run executor.

For each (document, intervention) it:
  1. Loads the base prompt/schema and applies the intervention.
  2. Calls the LLM (with caching) to extract under the intervention.
  3. Persists a counterfactual_runs row + the resulting edges (under a fresh event).
  4. Matches base-edges to cf-edges and stores edge_outcomes.

Shared execution: sentence/prompt/schema interventions are document-level, so a
single LLM call covers all base edges of that document.
"""
from __future__ import annotations

import logging
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Iterable, Optional

from ..db import repositories as repo
from ..extraction.extractor import extract_document
from ..extraction.prompts import register_prompt, register_schema
from ..interventions.apply import apply as apply_intervention
from ..llm.client import LLMClient
from ..matching.edge_matcher import match_edges, persist_outcomes

log = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get_base_event_id(conn: sqlite3.Connection, document_id: str,
                       prompt_id: str, schema_id: str, model_id: str) -> Optional[str]:
    row = conn.execute(
        "SELECT event_id FROM extraction_events "
        "WHERE document_id=? AND prompt_id=? AND schema_id=? AND model_id=? "
        "ORDER BY created_at DESC LIMIT 1",
        (document_id, prompt_id, schema_id, model_id),
    ).fetchone()
    return row["event_id"] if row else None


def _base_edges(conn: sqlite3.Connection, event_id: str) -> list[sqlite3.Row]:
    return list(conn.execute(
        "SELECT * FROM extracted_edges WHERE event_id = ?", (event_id,)
    ))


def _cf_edges(conn: sqlite3.Connection, event_id: str) -> list[sqlite3.Row]:
    return _base_edges(conn, event_id)


def run_one(conn: sqlite3.Connection, llm: LLMClient, intervention: sqlite3.Row,
            *, document_row, base_prompt_def: dict, base_schema_def: dict,
            base_event_id: str, temperature: float = 0.0, seed: Optional[int] = 7,
            max_tokens: int = 2048) -> tuple[str, int, int]:
    """Returns (run_id, n_cf_edges, n_outcomes)."""
    document_id = document_row["document_id"]
    sentences = repo.get_sentences(conn, document_id)

    new_sentences, new_prompt_def, new_schema_def = apply_intervention(
        conn, intervention,
        sentences=sentences, prompt_def=base_prompt_def, schema_def=base_schema_def,
    )
    register_prompt(conn, new_prompt_def)
    register_schema(conn, new_schema_def)
    conn.commit()  # release write lock before the slow LLM call

    # noop:repeat → re-run with a different seed to elicit stochastic variation
    eff_seed = seed
    eff_temperature = temperature
    if intervention["target_type"] == "noop":
        try:
            k = int(str(intervention["target_id"]).replace("seed", ""))
        except Exception:
            k = 0
        eff_seed = (seed or 7) + 1009 * (k + 1)
        eff_temperature = max(0.2, temperature)

    # Run the cf extraction (this writes its own extraction_events row + edges)
    cf_event_id, n_edges = extract_document(
        conn, llm,
        document_row=document_row, prompt_def=new_prompt_def, schema_def=new_schema_def,
        temperature=eff_temperature, seed=eff_seed, max_tokens=max_tokens,
        sentences_override=new_sentences if intervention["target_type"] == "sentence" else None,
    )

    run_id = f"run-{uuid.uuid4().hex[:10]}"
    conn.execute(
        "INSERT INTO counterfactual_runs("
        "run_id, base_event_id, intervention_id, document_id, prompt_id, schema_id, model_id, "
        "temperature, seed, token_input, token_output, latency_ms, status, created_at, cf_event_id) "
        "SELECT ?, ?, ?, ?, prompt_id, schema_id, model_id, temperature, seed, "
        "token_input, token_output, latency_ms, 'ok', ?, ? "
        "FROM extraction_events WHERE event_id = ?",
        (run_id, base_event_id, intervention["intervention_id"], document_id,
         _now(), cf_event_id, cf_event_id),
    )
    conn.commit()

    base_edges = _base_edges(conn, base_event_id)
    cf_edges = _cf_edges(conn, cf_event_id)
    base_relation_ids = {r["id"] for r in base_schema_def["relations"]}
    outcomes = match_edges(base_edges, cf_edges, run_id=run_id,
                           base_relation_ids=base_relation_ids)
    persist_outcomes(conn, outcomes)
    return run_id, len(cf_edges), len(outcomes)


def run_for_document(conn: sqlite3.Connection, llm: LLMClient, *,
                     document_row, base_prompt_def: dict, base_schema_def: dict,
                     interventions: Iterable[sqlite3.Row],
                     temperature: float = 0.0, seed: Optional[int] = 7,
                     max_tokens: int = 2048,
                     budget_calls: Optional[int] = None,
                     skip_existing: bool = True) -> dict:
    document_id = document_row["document_id"]
    base_event_id = _get_base_event_id(
        conn, document_id, base_prompt_def["id"], base_schema_def["id"], llm.model_id)
    if base_event_id is None:
        log.warning("No base extraction event for %s; run base extraction first", document_id)
        return {"runs": 0, "skipped": 0, "outcomes": 0, "doc": document_id}

    # Skip already executed (intervention -> run) pairs
    existing = {row["intervention_id"] for row in conn.execute(
        "SELECT intervention_id FROM counterfactual_runs WHERE document_id=? AND base_event_id=?",
        (document_id, base_event_id),
    )}

    runs = skipped = outcomes_total = 0
    for iv in interventions:
        if budget_calls is not None and runs >= budget_calls:
            break
        if skip_existing and iv["intervention_id"] in existing:
            skipped += 1
            continue
        try:
            _, _, n_outcomes = run_one(
                conn, llm, iv,
                document_row=document_row,
                base_prompt_def=base_prompt_def, base_schema_def=base_schema_def,
                base_event_id=base_event_id,
                temperature=temperature, seed=seed, max_tokens=max_tokens,
            )
            runs += 1
            outcomes_total += n_outcomes
        except Exception as e:
            log.exception("intervention failed: %s (%s)", iv["intervention_id"], e)
    return {"runs": runs, "skipped": skipped, "outcomes": outcomes_total, "doc": document_id}
