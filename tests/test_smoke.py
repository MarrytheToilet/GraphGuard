"""Tests that don't hit the LLM or the network."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from graphguard.db.database import open_db          # noqa: E402
from graphguard.db import repositories as repo      # noqa: E402
from graphguard.extraction.normalize import normalize_edges  # noqa: E402
from graphguard.extraction.prompts import (         # noqa: E402
    get_prompt_def, get_schema_def, load_yaml, render_prompt,
    register_prompt, register_schema,
)
from graphguard.extraction.schemas import normalize_relation  # noqa: E402
from graphguard.llm.json_repair import parse_json_lenient    # noqa: E402


def test_json_repair_handles_fences_and_trailing_commas():
    txt = """```json
    { "edges": [ { "subject": "A", "relation": "P19", "object": "B", }, ] }
    ```"""
    obj = parse_json_lenient(txt)
    assert obj["edges"][0]["subject"] == "A"


def test_db_init_and_doc_roundtrip(tmp_path):
    db = tmp_path / "t.db"
    conn = open_db(db)

    repo.upsert_document(conn, repo.Document(
        document_id="doc1", dataset="docred", title="T", raw_text="...", split="validation"))
    repo.upsert_sentences(conn, [
        repo.Sentence(sentence_id="doc1::s0", document_id="doc1", sentence_index=0,
                      text="Obama was born in Honolulu."),
        repo.Sentence(sentence_id="doc1::s1", document_id="doc1", sentence_index=1,
                      text="He later became president."),
    ])
    repo.upsert_entities(conn, [
        repo.Entity(entity_id="doc1::e0", document_id="doc1",
                    canonical_name="Barack Obama", aliases=["Obama"], entity_type="PER"),
        repo.Entity(entity_id="doc1::e1", document_id="doc1",
                    canonical_name="Honolulu", aliases=["Honolulu"], entity_type="LOC"),
    ])
    conn.commit()

    docs = repo.list_documents(conn)
    assert len(docs) == 1
    assert docs[0]["document_id"] == "doc1"
    assert len(repo.get_sentences(conn, "doc1")) == 2
    assert len(repo.get_entities(conn, "doc1")) == 2


def test_render_prompt_and_normalize_edges(tmp_path):
    prompts_cfg = load_yaml(ROOT / "configs/prompts.yaml")
    schemas_cfg = load_yaml(ROOT / "configs/schemas.yaml")
    prompt_def = get_prompt_def(prompts_cfg, "base_v1")
    schema_def = get_schema_def(schemas_cfg, "docred_full")

    db = tmp_path / "t.db"
    conn = open_db(db)
    repo.upsert_document(conn, repo.Document(
        document_id="doc1", dataset="docred", title="T", raw_text="x", split="validation"))
    repo.upsert_sentences(conn, [
        repo.Sentence("doc1::s0", "doc1", 0, "Obama was born in Honolulu."),
        repo.Sentence("doc1::s1", "doc1", 1, "He later became president."),
    ])
    repo.upsert_entities(conn, [
        repo.Entity("doc1::e0", "doc1", "Barack Obama", ["Obama"], "PER"),
        repo.Entity("doc1::e1", "doc1", "Honolulu", ["Honolulu"], "LOC"),
    ])
    register_prompt(conn, prompt_def)
    register_schema(conn, schema_def)
    conn.commit()

    sents = repo.get_sentences(conn, "doc1")
    ents = repo.get_entities(conn, "doc1")
    text = render_prompt(prompt_def, schema_def, sents, ents)
    assert "Obama" in text and "P19" in text and "Honolulu" in text

    fake_resp = {"edges": [{
        "subject": "Barack Obama", "relation": "place_of_birth",
        "object": "Honolulu", "evidence_sentences": [1], "confidence": 0.9,
        "rationale": "stated in s1",
    }]}
    edges = normalize_edges(fake_resp, event_id="evt-x", document_id="doc1",
                            sentences=sents, entities=ents, schema_def=schema_def)
    assert len(edges) == 1
    e = edges[0]
    assert e.relation == "P19"
    assert e.subject_entity_id == "doc1::e0"
    assert e.object_entity_id == "doc1::e1"
    assert e.evidence_sentence_ids == ["doc1::s0"]


def test_relation_normalization():
    schemas_cfg = load_yaml(ROOT / "configs/schemas.yaml")
    schema_def = get_schema_def(schemas_cfg, "docred_full")
    assert normalize_relation("P19", schema_def) == "P19"
    assert normalize_relation("place_of_birth", schema_def) == "P19"
    assert normalize_relation("totally_unknown", schema_def) == "OTHER"
