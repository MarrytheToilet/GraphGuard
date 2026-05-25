"""Document-level extraction: build prompt, call LLM, persist event + edges.

Always logs raw LLM output to extracted_edges.raw_json; the full extractor response
is also written to data/cache/extractions/<event_id>.json so we never lose data.
"""
from __future__ import annotations

import json
import logging
import uuid
from pathlib import Path
from typing import Optional

from ..db import repositories as repo
from ..llm.client import LLMClient
from ..llm.json_repair import parse_json_lenient
from .normalize import normalize_edges
from .prompts import (register_prompt, register_schema, render_prompt)

log = logging.getLogger(__name__)

CACHE_DIR = Path("data/cache/extractions")


def _new_event_id(document_id: str) -> str:
    return f"evt-{document_id}-{uuid.uuid4().hex[:10]}"


_JSON_RETRY_INSTRUCTION = """

The previous response was not valid JSON. Retry the same extraction now.
Return exactly:
{"edges":[{"subject":"...","relation":"...","object":"...","evidence_sentences":[1],"confidence":0.0}]}
Use an empty list if no valid edge exists. Return only JSON.
"""


def extract_document(conn, llm: LLMClient, *,
                     document_row,
                     prompt_def: dict,
                     schema_def: dict,
                     active_clause_ids: Optional[list[str]] = None,
                     temperature: float = 0.0,
                     seed: Optional[int] = 7,
                     max_tokens: int = 2048,
                     write_raw_cache: bool = True,
                     sentences_override: Optional[list] = None) -> tuple[str, int]:
    """Run a single base extraction. Returns (event_id, n_edges).

    `sentences_override` allows counterfactual callers to supply a modified
    sentence list (e.g. with one sentence removed/masked) without touching the
    persisted sentences for the document.
    """
    document_id = document_row["document_id"]

    # ensure prompt/schema rows exist for lineage; commit immediately so we do
    # NOT hold a write transaction across the slow LLM call (which would serialize
    # all parallel workers and cause SQLITE_BUSY storms).
    register_prompt(conn, prompt_def)
    register_schema(conn, schema_def)
    conn.commit()

    sentences = sentences_override if sentences_override is not None \
        else repo.get_sentences(conn, document_id)
    entities = repo.get_entities(conn, document_id)
    if not sentences:
        log.warning("No sentences for %s; skipping", document_id)
        return "", 0

    prompt_text = render_prompt(prompt_def, schema_def, sentences, entities,
                                active_clause_ids=active_clause_ids)
    log.debug("Prompt size = %d chars", len(prompt_text))

    resp = llm.complete_json(prompt_text, temperature=temperature,
                             max_tokens=max_tokens, seed=seed)

    try:
        parsed = parse_json_lenient(resp.text)
    except Exception as e:
        log.warning("Failed to parse LLM JSON for %s on first try: %s; raw=%s",
                    document_id, e, resp.text[:300])
        retry_seed = (seed + 1) if isinstance(seed, int) else seed
        retry_prompt = prompt_text + _JSON_RETRY_INSTRUCTION
        retry = llm.complete_json(retry_prompt, temperature=0.0,
                                  max_tokens=max_tokens, seed=retry_seed)
        try:
            parsed = parse_json_lenient(retry.text)
            resp = retry
        except Exception as e2:
            log.error("Failed to parse LLM JSON for %s after retry: %s; raw=%s",
                      document_id, e2, retry.text[:300])
            parsed = {"edges": []}

    event_id = _new_event_id(document_id)

    if write_raw_cache:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        (CACHE_DIR / f"{event_id}.json").write_text(json.dumps({
            "event_id": event_id,
            "document_id": document_id,
            "model_id": resp.model,
            "prompt": prompt_text,
            "raw_response_text": resp.text,
            "parsed": parsed,
            "prompt_tokens": resp.prompt_tokens,
            "completion_tokens": resp.completion_tokens,
            "latency_ms": resp.latency_ms,
        }, ensure_ascii=False, indent=2), encoding="utf-8")

    repo.insert_event(conn, repo.ExtractionEvent(
        event_id=event_id,
        document_id=document_id,
        prompt_id=prompt_def["id"],
        schema_id=schema_def["id"],
        model_id=resp.model,
        temperature=temperature,
        seed=seed,
        input_sentence_ids=[s["sentence_id"] for s in sentences],
        input_entity_ids=[e["entity_id"] for e in entities],
        token_input=resp.prompt_tokens,
        token_output=resp.completion_tokens,
        latency_ms=resp.latency_ms,
    ))

    edges = normalize_edges(parsed, event_id=event_id, document_id=document_id,
                            sentences=sentences, entities=entities, schema_def=schema_def)
    if edges:
        repo.insert_edges(conn, edges)
    conn.commit()
    return event_id, len(edges)
