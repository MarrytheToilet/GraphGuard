"""Thin CRUD repositories over the SQLite tables defined in schema.sql.

Kept small and explicit; no ORM. Each upsert is idempotent on its primary key.
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable, Optional


def _json(value: Any) -> Optional[str]:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# -------- dataclasses --------

@dataclass
class Document:
    document_id: str
    dataset: str
    title: str
    raw_text: str
    split: str


@dataclass
class Sentence:
    sentence_id: str
    document_id: str
    sentence_index: int
    text: str


@dataclass
class Entity:
    entity_id: str
    document_id: str
    canonical_name: str
    aliases: list[str] = field(default_factory=list)
    entity_type: Optional[str] = None


@dataclass
class SchemaRow:
    schema_id: str
    name: str
    description: str
    relation_types: list[dict]
    parent_schema_id: Optional[str] = None


@dataclass
class PromptRow:
    prompt_id: str
    name: str
    full_prompt: str
    clause_ids: list[str]


@dataclass
class PromptClause:
    clause_id: str
    prompt_id: str
    clause_type: str
    clause_text: str


@dataclass
class ExtractionEvent:
    event_id: str
    document_id: str
    prompt_id: str
    schema_id: str
    model_id: str
    temperature: float
    seed: Optional[int]
    input_sentence_ids: list[str]
    input_entity_ids: list[str]
    token_input: Optional[int] = None
    token_output: Optional[int] = None
    latency_ms: Optional[int] = None
    created_at: str = field(default_factory=_now_iso)


@dataclass
class ExtractedEdge:
    edge_id: str
    event_id: str
    document_id: str
    subject_entity_id: Optional[str]
    subject_name: str
    relation: str
    object_entity_id: Optional[str]
    object_name: str
    evidence_sentence_ids: list[str]
    confidence: Optional[float]
    raw_json: str


# -------- writers --------

def upsert_document(conn: sqlite3.Connection, d: Document) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO documents(document_id, dataset, title, raw_text, split) "
        "VALUES (?,?,?,?,?)",
        (d.document_id, d.dataset, d.title, d.raw_text, d.split),
    )


def upsert_sentences(conn: sqlite3.Connection, rows: Iterable[Sentence]) -> None:
    conn.executemany(
        "INSERT OR REPLACE INTO sentences(sentence_id, document_id, sentence_index, text) "
        "VALUES (?,?,?,?)",
        [(s.sentence_id, s.document_id, s.sentence_index, s.text) for s in rows],
    )


def upsert_entities(conn: sqlite3.Connection, rows: Iterable[Entity]) -> None:
    conn.executemany(
        "INSERT OR REPLACE INTO entities(entity_id, document_id, canonical_name, aliases_json, entity_type) "
        "VALUES (?,?,?,?,?)",
        [(e.entity_id, e.document_id, e.canonical_name, _json(e.aliases), e.entity_type) for e in rows],
    )


def upsert_schema(conn: sqlite3.Connection, s: SchemaRow) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO schemas(schema_id, name, description, relation_types_json, parent_schema_id) "
        "VALUES (?,?,?,?,?)",
        (s.schema_id, s.name, s.description, _json(s.relation_types), s.parent_schema_id),
    )


def upsert_prompt(conn: sqlite3.Connection, p: PromptRow) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO prompts(prompt_id, name, full_prompt, clause_ids_json) VALUES (?,?,?,?)",
        (p.prompt_id, p.name, p.full_prompt, _json(p.clause_ids)),
    )


def upsert_prompt_clauses(conn: sqlite3.Connection, rows: Iterable[PromptClause]) -> None:
    conn.executemany(
        "INSERT OR REPLACE INTO prompt_clauses(clause_id, prompt_id, clause_type, clause_text) "
        "VALUES (?,?,?,?)",
        [(c.clause_id, c.prompt_id, c.clause_type, c.clause_text) for c in rows],
    )


def insert_event(conn: sqlite3.Connection, e: ExtractionEvent) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO extraction_events("
        "event_id, document_id, prompt_id, schema_id, model_id, temperature, seed, "
        "input_sentence_ids_json, input_entity_ids_json, created_at, "
        "token_input, token_output, latency_ms) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            e.event_id, e.document_id, e.prompt_id, e.schema_id, e.model_id,
            e.temperature, e.seed,
            _json(e.input_sentence_ids), _json(e.input_entity_ids),
            e.created_at, e.token_input, e.token_output, e.latency_ms,
        ),
    )


def insert_edges(conn: sqlite3.Connection, rows: Iterable[ExtractedEdge]) -> None:
    conn.executemany(
        "INSERT OR REPLACE INTO extracted_edges("
        "edge_id, event_id, document_id, subject_entity_id, subject_name, relation, "
        "object_entity_id, object_name, evidence_sentence_ids_json, confidence, raw_json) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        [(
            e.edge_id, e.event_id, e.document_id, e.subject_entity_id, e.subject_name,
            e.relation, e.object_entity_id, e.object_name,
            _json(e.evidence_sentence_ids), e.confidence, e.raw_json,
        ) for e in rows],
    )


# -------- readers --------

def list_documents(conn: sqlite3.Connection, split: Optional[str] = None,
                   limit: Optional[int] = None) -> list[sqlite3.Row]:
    q = "SELECT * FROM documents"
    args: list[Any] = []
    if split:
        splits = [s.strip() for s in split.split(",") if s.strip()]
        if len(splits) == 1:
            q += " WHERE split = ?"
            args.append(splits[0])
        elif len(splits) > 1:
            q += " WHERE split IN (" + ",".join(["?"] * len(splits)) + ")"
            args.extend(splits)
    q += " ORDER BY document_id"
    if limit:
        q += f" LIMIT {int(limit)}"
    return list(conn.execute(q, args))


def get_sentences(conn: sqlite3.Connection, document_id: str) -> list[sqlite3.Row]:
    return list(conn.execute(
        "SELECT * FROM sentences WHERE document_id = ? ORDER BY sentence_index", (document_id,)))


def get_entities(conn: sqlite3.Connection, document_id: str) -> list[sqlite3.Row]:
    return list(conn.execute(
        "SELECT * FROM entities WHERE document_id = ? ORDER BY entity_id", (document_id,)))


def count_events_for_doc(conn: sqlite3.Connection, document_id: str,
                         prompt_id: str, schema_id: str, model_id: str) -> int:
    cur = conn.execute(
        "SELECT COUNT(*) FROM extraction_events "
        "WHERE document_id=? AND prompt_id=? AND schema_id=? AND model_id=?",
        (document_id, prompt_id, schema_id, model_id),
    )
    return int(cur.fetchone()[0])


# -------- M4: gold edges & correctness --------

@dataclass
class GoldEdge:
    gold_edge_id: str
    document_id: str
    head_entity_id: Optional[str]
    tail_entity_id: Optional[str]
    head_name: str
    tail_name: str
    relation_base: str
    evidence_sentence_ids: list[int] = field(default_factory=list)
    source: str = "docred"


def upsert_gold_edges(conn: sqlite3.Connection, rows: Iterable[GoldEdge]) -> None:
    conn.executemany(
        "INSERT OR REPLACE INTO gold_edges("
        "gold_edge_id, document_id, head_entity_id, tail_entity_id, head_name, tail_name, "
        "relation_base, evidence_sentence_ids_json, source) VALUES (?,?,?,?,?,?,?,?,?)",
        [(g.gold_edge_id, g.document_id, g.head_entity_id, g.tail_entity_id,
          g.head_name, g.tail_name, g.relation_base,
          _json(g.evidence_sentence_ids), g.source) for g in rows],
    )


def get_gold_edges(conn: sqlite3.Connection, document_id: str) -> list[sqlite3.Row]:
    return list(conn.execute(
        "SELECT * FROM gold_edges WHERE document_id = ?", (document_id,)))


def upsert_edge_correctness(conn: sqlite3.Connection, edge_id: str,
                            document_id: str, label: str,
                            gold_edge_id: Optional[str]) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO edge_correctness("
        "edge_id, document_id, label, gold_edge_id, matched_at) VALUES (?,?,?,?,?)",
        (edge_id, document_id, label, gold_edge_id, _now_iso()),
    )


def upsert_stability_report(conn: sqlite3.Connection, document_id: str, **metrics: Any) -> None:
    cols = ["document_id", "n_runs", "avg_edge_overlap", "type_agreement",
            "disappearance_rate", "type_flip_rate", "new_edge_rate", "computed_at"]
    vals = [document_id,
            metrics.get("n_runs"),
            metrics.get("avg_edge_overlap"),
            metrics.get("type_agreement"),
            metrics.get("disappearance_rate"),
            metrics.get("type_flip_rate"),
            metrics.get("new_edge_rate"),
            _now_iso()]
    conn.execute(
        f"INSERT OR REPLACE INTO stability_reports({','.join(cols)}) "
        f"VALUES ({','.join(['?']*len(cols))})",
        vals,
    )
