from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from graphguard.experiments.controlled_magnitude import (
    MASK_TOKEN,
    evidence_variants,
    prompt_variants,
    schema_variants,
)
from graphguard.extraction.prompts import get_prompt_def, get_schema_def, load_yaml

_RUNNER_PATH = Path(__file__).resolve().parents[1] / "scripts" / "run_magnitude_analysis.py"
_RUNNER_SPEC = importlib.util.spec_from_file_location(
    "run_magnitude_analysis", _RUNNER_PATH
)
assert _RUNNER_SPEC is not None and _RUNNER_SPEC.loader is not None
runner = importlib.util.module_from_spec(_RUNNER_SPEC)
_RUNNER_SPEC.loader.exec_module(runner)


LEVELS = (0.10, 0.25, 0.50, 0.75)


def _plans(variants):
    return [variant.plan for variant in variants]


def _assert_nested(variants):
    plans = _plans(variants)
    for left, right in zip(plans, plans[1:]):
        assert set(left.changed_keys) < set(right.changed_keys)
        assert left.changed < right.changed
    assert [p.nominal_magnitude for p in plans] == list(LEVELS)
    assert all(p.actual_magnitude == p.changed / p.eligible for p in plans)


def test_schema_masking_excludes_other_and_preserves_structure():
    schema = {
        "id": "s",
        "name": "schema",
        "description": "top",
        "relations": [
            {
                "id": "R1",
                "label": "r1",
                "description": "one two three four five six seven eight",
            },
            {
                "id": "R2",
                "label": "r2",
                "description": "nine ten eleven twelve thirteen fourteen",
            },
            {
                "id": "OTHER",
                "label": "other",
                "description": "must stay exactly unchanged",
            },
        ],
    }
    variants = schema_variants(
        schema, corpus="toy", document_id="doc", design_seed="seed"
    )
    _assert_nested(variants)
    for variant in variants:
        payload = variant.payload
        assert payload["id"] == schema["id"]
        assert payload["description"] == schema["description"]
        assert [(r["id"], r["label"]) for r in payload["relations"]] == [
            (r["id"], r["label"]) for r in schema["relations"]
        ]
        assert payload["relations"][-1] == schema["relations"][-1]
        assert sum(
            r["description"].split().count(MASK_TOKEN)
            for r in payload["relations"]
        ) == variant.plan.changed


def test_prompt_masking_preserves_format_clause_and_template():
    task_ids = [
        "C1_evidence_only",
        "C2_infer_implicit",
        "C3_use_schema",
        "C4_allow_other",
        "C5_cite_evidence",
        "C6_return_confidence",
    ]
    prompt = {
        "id": "p",
        "template": "{clauses}\n{schema}\n{document}\n{entities}",
        "clauses": [
            {"id": clause_id, "text": "one two three four five"}
            for clause_id in task_ids
        ] + [{"id": "C7_json_only", "text": "JSON only forever"}],
    }
    variants = prompt_variants(
        prompt, corpus="toy", document_id="doc", design_seed="seed"
    )
    _assert_nested(variants)
    for variant in variants:
        payload = variant.payload
        assert payload["id"] == prompt["id"]
        assert payload["template"] == prompt["template"]
        assert payload["clauses"][-1] == prompt["clauses"][-1]
        assert sum(
            c["text"].split().count(MASK_TOKEN) for c in payload["clauses"]
        ) == variant.plan.changed


def test_evidence_masking_preserves_sentence_ids_and_order():
    sentences = [
        {
            "sentence_id": f"s{i}",
            "document_id": "doc",
            "sentence_index": i,
            "text": "one two three four five six",
        }
        for i in range(4)
    ]
    variants = evidence_variants(
        sentences, corpus="toy", document_id="doc", design_seed="seed"
    )
    _assert_nested(variants)
    structure = [
        (s["sentence_id"], s["document_id"], s["sentence_index"])
        for s in sentences
    ]
    for variant in variants:
        assert [
            (s["sentence_id"], s["document_id"], s["sentence_index"])
            for s in variant.payload
        ] == structure
        assert sum(
            s["text"].split().count(MASK_TOKEN) for s in variant.payload
        ) == variant.plan.changed


class _FakeClient:
    def __init__(self, texts):
        self.texts = iter(texts)
        self.calls = []

    def complete_json(self, prompt, *, temperature, max_tokens, seed):
        self.calls.append(
            {
                "prompt": prompt,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "seed": seed,
            }
        )
        return SimpleNamespace(
            text=next(self.texts),
            model="deepseek-v4-flash",
            prompt_tokens=10,
            completion_tokens=2,
            latency_ms=1,
        )


def _minimal_extraction_inputs():
    document = {"document_id": "doc"}
    sentences = [
        {
            "sentence_id": "s0",
            "document_id": "doc",
            "sentence_index": 0,
            "text": "Alice met Bob.",
        }
    ]
    entities = [
        {
            "entity_id": "e0",
            "canonical_name": "Alice",
            "entity_type": "PER",
        },
        {
            "entity_id": "e1",
            "canonical_name": "Bob",
            "entity_type": "PER",
        },
    ]
    schema = {
        "id": "s",
        "relations": [
            {"id": "R", "label": "related", "description": "is related to"}
        ],
    }
    return document, sentences, entities, schema


def test_parse_failure_is_not_retried_or_converted_to_empty_graph():
    document, sentences, entities, schema = _minimal_extraction_inputs()
    client = _FakeClient(["not valid json", '{"edges":[]}'])
    result = runner._call_and_normalize(
        client=client,
        prompt_text="prompt",
        document=document,
        sentences=sentences,
        entities=entities,
        schema_def=schema,
        seed=7,
        condition_id="base",
    )
    assert result["status"] == "parse_error"
    assert len(client.calls) == 1
    assert result["explicit_empty_graph"] is False
    assert result["normalization_empty_graph"] is False


def test_explicit_empty_and_normalization_empty_are_distinct():
    document, sentences, entities, schema = _minimal_extraction_inputs()
    explicit = runner._call_and_normalize(
        client=_FakeClient(['{"edges":[]}']),
        prompt_text="prompt",
        document=document,
        sentences=sentences,
        entities=entities,
        schema_def=schema,
        seed=7,
        condition_id="base",
    )
    assert explicit["status"] == "ok"
    assert explicit["explicit_empty_graph"] is True
    assert explicit["normalization_empty_graph"] is False

    normalized_away = runner._call_and_normalize(
        client=_FakeClient(['{"edges":[{"subject":"","relation":"R","object":""}]}']),
        prompt_text="prompt",
        document=document,
        sentences=sentences,
        entities=entities,
        schema_def=schema,
        seed=7,
        condition_id="base",
    )
    assert normalized_away["status"] == "ok"
    assert normalized_away["explicit_empty_graph"] is False
    assert normalized_away["normalization_empty_graph"] is True


def test_nonempty_checkpoint_without_manifest_fails_closed(tmp_path):
    checkpoint = tmp_path / "checkpoint.jsonl"
    checkpoint.write_text(json.dumps({"old": "record"}) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="no manifest"):
        runner._validate_checkpoint_manifest(
            checkpoint,
            {
                "experiment_id": runner.EXPERIMENT_ID,
                "design_seed": runner.DESIGN_SEED,
            },
        )


def test_record_fingerprint_checks_more_than_input_hash():
    record = {
        "corpus": "docred",
        "document_id": "doc",
        "condition_id": "base",
        "input_sha256": "same",
        "seed": 7,
        "temperature": 0.0,
    }
    runner._assert_record_fingerprint(record, dict(record))
    with pytest.raises(ValueError, match="seed"):
        runner._assert_record_fingerprint(
            record, {**record, "seed": 13}
        )


def test_condition_grid_has_shared_input_resample_and_twelve_unique_levels():
    prompts = load_yaml(runner.PROMPTS_PATH)
    schemas = load_yaml(runner.SCHEMAS_PATH)
    prompt = get_prompt_def(prompts, "base_v1")
    schema = get_schema_def(schemas, "docred_full")
    job = {
        "run": "docred__deepseek-v4-flash__300d",
        "corpus": "docred",
        "document": {"document_id": "doc"},
        "sentences": [
            {
                "sentence_id": "s0",
                "document_id": "doc",
                "sentence_index": 0,
                "text": "one two three four five six seven eight nine ten",
            }
        ],
        "entities": [
            {
                "entity_id": "e0",
                "canonical_name": "Alice",
                "entity_type": "PER",
            }
        ],
    }
    conditions = runner._variant_conditions(job, prompt, schema)
    assert len(conditions) == 13
    magnitude = [c for c in conditions if c["family"] != "resample"]
    assert len(magnitude) == 12
    assert len({runner._sha256_text(c["prompt_text"]) for c in magnitude}) == 12
    resample = next(c for c in conditions if c["family"] == "resample")
    base_prompt = runner.render_prompt(
        prompt, schema, job["sentences"], job["entities"]
    )
    assert runner._sha256_text(resample["prompt_text"]) == runner._sha256_text(
        base_prompt
    )
    assert resample["seed"] == runner.RESAMPLE_SEED
    assert all(c["seed"] == runner.BASE_SEED for c in magnitude)


def test_dose_response_uses_document_fixed_effects_and_reported_unit():
    panels = {
        "a": [(q, 0.10 + 0.40 * q) for q in LEVELS],
        "b": [(q, 0.70 + 0.40 * q) for q in LEVELS],
    }
    first = runner._dose_response_summary(panels, seed=17, draws=100)
    second = runner._dose_response_summary(panels, seed=17, draws=100)
    assert first == second
    assert first["complete_documents"] == 2
    assert first["observations"] == 8
    assert first["slope_per_0_10"] == pytest.approx(0.04)
    assert first["ci95"] == pytest.approx([0.04, 0.04])
    assert first["bootstrap"] == {
        "unit": "document",
        "draws": 100,
        "seed": 17,
    }


def test_dose_response_requires_valid_base_and_all_four_levels():
    docs = ["complete", "missing", "bad-base"]
    bases = {
        "complete": {"status": "ok"},
        "missing": {"status": "ok"},
        "bad-base": {"status": "parse_error"},
    }
    rows_by_level = {
        q: {
            document_id: {
                "status": "ok",
                "actual_magnitude": q,
                "drift": q,
            }
            for document_id in docs
        }
        for q in LEVELS
    }
    rows_by_level[0.50]["missing"] = {"status": "parse_error"}
    panels = runner._complete_dose_panels(
        docs=docs,
        bases=bases,
        rows_by_level=rows_by_level,
    )
    assert list(panels) == ["complete"]
