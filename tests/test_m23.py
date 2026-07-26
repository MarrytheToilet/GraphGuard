"""Tests for interventions, schema variants, edge matching, and the LLM cache."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from graphguard.db import repositories as repo                         # noqa: E402
from graphguard.db.database import open_db                             # noqa: E402
from graphguard.interventions.candidates import generate_for_document  # noqa: E402
from graphguard.interventions.prompt import remove_clauses             # noqa: E402
from graphguard.interventions.schema import (                          # noqa: E402
    schema_coarse, schema_with_other, schema_without_specific,
)
from graphguard.interventions.text import mask_sentence, remove_sentence, to_mutable  # noqa: E402
from graphguard.matching.edge_matcher import match_edges, persist_outcomes  # noqa: E402


def _seed_doc(conn, doc="d1"):
    repo.upsert_document(conn, repo.Document(doc, "docred", "T", "x", "validation"))
    repo.upsert_sentences(conn, [
        repo.Sentence(f"{doc}::s0", doc, 0, "Obama was born in Honolulu."),
        repo.Sentence(f"{doc}::s1", doc, 1, "He was the 44th president."),
    ])
    repo.upsert_entities(conn, [
        repo.Entity(f"{doc}::e0", doc, "Barack Obama", ["Obama"], "PER"),
        repo.Entity(f"{doc}::e1", doc, "Honolulu", ["Honolulu"], "LOC"),
    ])
    # FK targets used by extraction_events in later tests
    repo.upsert_prompt(conn, repo.PromptRow("base_v1", "base", "t", []))
    repo.upsert_prompt(conn, repo.PromptRow("base_v1_drop_C1", "base", "t", []))
    repo.upsert_schema(conn, repo.SchemaRow("docred_full", "S", "", []))
    conn.commit()
    return doc


def test_schema_variants():
    base = {"id": "S", "name": "S", "relations": [
        {"id": "P19", "label": "place_of_birth", "description": ""},
        {"id": "P20", "label": "place_of_death", "description": ""},
        {"id": "P17", "label": "country", "description": ""},
    ]}
    s1 = schema_with_other(base)
    assert any(r["id"] == "OTHER" for r in s1["relations"])
    s2 = schema_coarse(base)
    rel_ids = {r["id"] for r in s2["relations"]}
    assert "person_origin" in rel_ids and "P19" not in rel_ids
    s3 = schema_without_specific(base, "P20")
    assert all(r["id"] != "P20" for r in s3["relations"])


def test_text_interventions():
    sents = to_mutable([
        {"sentence_id": "s0", "document_id": "d", "sentence_index": 0, "text": "A."},
        {"sentence_id": "s1", "document_id": "d", "sentence_index": 1, "text": "B."},
    ])
    rm = remove_sentence(sents, "s0")
    assert [s.sentence_id for s in rm] == ["s1"]
    mk = mask_sentence(sents, "s1")
    assert mk[1].text == "[MASKED]"


def test_prompt_remove_clauses():
    p = {"id": "p1", "clauses": [
        {"id": "C1", "type": "x", "text": "..."},
        {"id": "C2", "type": "x", "text": "..."},
    ], "template": "t"}
    p2 = remove_clauses(p, ["C1"])
    assert {c["id"] for c in p2["clauses"]} == {"C2"}
    assert p2["id"].startswith("p1_drop_")


def test_generate_candidates(tmp_path):
    conn = open_db(tmp_path / "t.db")
    doc = _seed_doc(conn)
    items = generate_for_document(
        conn, doc,
        base_prompt_id="base_v1", base_schema_id="docred_full",
        prompt_clauses_to_drop=["C1_evidence_only"],
        schema_variants=["with_other"],
    )
    types = {i.target_type for i in items}
    assert types == {"sentence", "prompt_clause", "schema", "noop"}


def _mk_edge(eid, evt, doc, subj_eid, subj, rel, obj_eid, obj):
    return repo.ExtractedEdge(eid, evt, doc, subj_eid, subj, rel, obj_eid, obj,
                              evidence_sentence_ids=[], confidence=0.9, raw_json="{}")


def test_edge_matcher_outcome_categories(tmp_path):
    conn = open_db(tmp_path / "t.db")
    doc = _seed_doc(conn)
    repo.insert_event(conn, repo.ExtractionEvent(
        event_id="evt-base", document_id=doc, prompt_id="base_v1", schema_id="docred_full",
        model_id="m", temperature=0.0, seed=7, input_sentence_ids=[], input_entity_ids=[],
    ))
    repo.insert_event(conn, repo.ExtractionEvent(
        event_id="evt-cf", document_id=doc, prompt_id="base_v1_drop_C1", schema_id="docred_full",
        model_id="m", temperature=0.0, seed=7, input_sentence_ids=[], input_entity_ids=[],
    ))
    base = [_mk_edge("e1", "evt-base", doc, f"{doc}::e0", "Obama", "P19", f"{doc}::e1", "Honolulu"),
            _mk_edge("e2", "evt-base", doc, f"{doc}::e0", "Obama", "P20", f"{doc}::e1", "Honolulu")]
    cf = [_mk_edge("c1", "evt-cf", doc, f"{doc}::e0", "Obama", "P19", f"{doc}::e1", "Honolulu"),  # exact for e1
          _mk_edge("c2", "evt-cf", doc, f"{doc}::e0", "Obama", "P17", f"{doc}::e1", "Honolulu")]  # type-flip for e2
    repo.insert_edges(conn, base + cf)

    base_rows = list(conn.execute("SELECT * FROM extracted_edges WHERE event_id='evt-base'"))
    cf_rows = list(conn.execute("SELECT * FROM extracted_edges WHERE event_id='evt-cf'"))
    outcomes = match_edges(base_rows, cf_rows, run_id="run-x",
                           base_relation_ids={"P17", "P19", "P20"})
    by_orig = {o.original_edge_id: o.outcome_type for o in outcomes}
    assert by_orig["e1"] == "EXACT_SAME"
    # One-to-one alignment reserves c1 for e1, leaving c2 as the unique
    # type-flip match for e2.
    assert by_orig["e2"] == "TYPE_FLIP"


def test_llm_cache_roundtrip(tmp_path):
    from graphguard.llm.cache import CachedLLMClient
    from graphguard.llm.client import LLMResponse

    class Fake:
        model_id = "fake"
        def __init__(self): self.calls = 0
        def complete_json(self, prompt, *, temperature=0.0, max_tokens=2048, seed=None):
            self.calls += 1
            return LLMResponse(text='{"ok": true}', model="fake",
                               prompt_tokens=1, completion_tokens=1, latency_ms=1)
    conn = open_db(tmp_path / "c.db")
    fake = Fake()
    cached = CachedLLMClient(fake, conn)
    r1 = cached.complete_json("hello", seed=7)
    r2 = cached.complete_json("hello", seed=7)
    assert r1.text == r2.text == '{"ok": true}'
    assert fake.calls == 1
    assert cached.hits == 1 and cached.misses == 1
