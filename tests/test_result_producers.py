"""Determinism checks for paper-facing result producers."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_script(name: str):
    path = ROOT / "scripts" / name
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_family_type_agreement_handles_multi_relation_pairs() -> None:
    family = load_script("run_family_decomposition.py")
    base = {
        ("a", "r1", "b"),
        ("a", "r2", "b"),
        ("x", "r3", "y"),
    }
    counterfactual = {
        ("a", "r1", "b"),
        ("a", "r3", "b"),
        ("x", "r3", "y"),
    }

    expected = ((1.0 / 3.0) + 1.0) / 2.0
    assert family.pair_stats(base, counterfactual)["type_agree"] == expected
    assert (
        family.pair_stats(set(reversed(sorted(base))), counterfactual)[
            "type_agree"
        ]
        == expected
    )


def test_extended_query_threshold_is_closed_at_boundary() -> None:
    extended = load_script("run_extended_queries.py")

    assert not extended.exceeds_tolerance(0.3, 0.3)
    assert not extended.exceeds_tolerance(1.0 - 0.7, 0.3)
    assert extended.exceeds_tolerance(0.3000001, 0.3)
    assert not extended.exceeds_tolerance(
        0.3 + extended.THRESHOLD_ATOL,
        0.3,
    )


def test_langchain_evidence_order_seed_is_stable() -> None:
    langchain = load_script("run_langchain_toolchain.py")

    doc_id = "docred-validation-000001"
    assert langchain.stable_evidence_seed(doc_id) == int.from_bytes(
        __import__("hashlib").sha256(doc_id.encode("utf-8")).digest()[:8],
        "big",
    )
    text_a = langchain.doc_text(
        "evidence_reorder",
        doc_id,
        "unused",
        ["zero", "one", "two", "three"],
    )
    text_b = langchain.doc_text(
        "evidence_reorder",
        doc_id,
        "unused",
        ["zero", "one", "two", "three"],
    )
    assert text_a == text_b


def test_langchain_analysis_keeps_one_fingerprinted_cohort() -> None:
    langchain = load_script("run_langchain_toolchain.py")
    records = [
        {
            "doc": "d1",
            "condition": "base",
            "edges": [["a", "r", "b"]],
        },
        {
            "doc": "d1",
            "condition": "base",
            "cohort_fingerprint": "new",
            "config_fingerprint": "base-config",
            "input_sha256": "base-input",
            "extraction_dependency_versions": {"langchain-core": "1"},
            "model": "deepseek-v4-flash",
            "evidence_seed_rule": "sha256",
            "ignore_tool_usage": True,
            "edges": [["a", "r", "c"]],
        },
        {
            "doc": "d1",
            "condition": "resample",
            "cohort_fingerprint": "new",
            "config_fingerprint": "resample-config",
            "input_sha256": "resample-input",
            "extraction_dependency_versions": {"langchain-core": "1"},
            "model": "deepseek-v4-flash",
            "evidence_seed_rule": "sha256",
            "ignore_tool_usage": True,
            "edges": [["a", "r", "d"]],
        },
        {
            "doc": "d1",
            "condition": "resample",
            "cohort_fingerprint": "new",
            "config_fingerprint": "resample-config",
            "input_sha256": "resample-input",
            "extraction_dependency_versions": {"langchain-core": "1"},
            "model": "deepseek-v4-flash",
            "evidence_seed_rule": "sha256",
            "ignore_tool_usage": True,
            "edges": None,
            "error": "retryable",
        },
    ]

    selected, errors, metadata = langchain.select_analysis_records(records)

    assert selected["d1"]["base"] == [["a", "r", "c"]]
    assert "resample" not in selected["d1"]
    assert errors["resample"] == 1
    assert metadata == {
        "mode": "fingerprinted-cohort",
        "cohort_fingerprint": "new",
        "selected_records": 2,
        "extraction_dependency_versions": {"langchain-core": "1"},
        "model": "deepseek-v4-flash",
        "evidence_seed_rule": "sha256",
        "ignore_tool_usage": True,
    }


def test_langchain_reuse_is_scoped_and_failures_retry() -> None:
    langchain = load_script("run_langchain_toolchain.py")

    def record(cohort: str, edges):
        return {
            "doc": "d1",
            "condition": "base",
            "cohort_fingerprint": cohort,
            "config_fingerprint": "config",
            "input_sha256": "input",
            "edges": edges,
        }

    old_key = ("old", "d1", "base", "config", "input")
    new_key = ("new", "d1", "base", "config", "input")
    assert langchain.successful_record_keys(
        [record("old", [["a", "r", "b"]])]
    ) == {old_key}
    assert new_key not in langchain.successful_record_keys(
        [record("old", [["a", "r", "b"]])]
    )
    assert langchain.successful_record_keys(
        [
            record("old", [["a", "r", "b"]]),
            record("old", None),
        ]
    ) == set()
    assert langchain.successful_record_keys(
        [
            record("old", [["a", "r", "b"]]),
            record("old", None),
            record("old", [["a", "r", "c"]]),
        ]
    ) == {old_key}


def test_langchain_checkpoint_metadata_distinguishes_formats() -> None:
    langchain = load_script("run_langchain_toolchain.py")
    checkpoint_record = {"doc": "d1", "condition": "base", "edges": []}
    fingerprinted = {
        **checkpoint_record,
        "config_fingerprint": "config",
    }

    assert langchain.checkpoint_metadata(
        [checkpoint_record]
    )["format"] == "published-checkpoint"
    mixed = langchain.checkpoint_metadata(
        [checkpoint_record, fingerprinted]
    )
    assert mixed["format"] == "mixed"
    assert mixed["contains_fingerprinted_records"]
    assert not mixed["fully_fingerprinted"]
    complete = langchain.checkpoint_metadata([fingerprinted])
    assert complete["format"] == "fingerprinted-only"
    assert complete["fully_fingerprinted"]


def test_langchain_dependency_versions_change_fingerprints() -> None:
    langchain = load_script("run_langchain_toolchain.py")
    first = {"langchain-core": "1"}
    second = {"langchain-core": "2"}

    assert langchain.config_fingerprint(
        "base",
        ["r"],
        True,
        first,
    ) != langchain.config_fingerprint(
        "base",
        ["r"],
        True,
        second,
    )
    assert langchain.cohort_fingerprint(
        ["r"],
        True,
        "db-sha",
        first,
    ) != langchain.cohort_fingerprint(
        ["r"],
        True,
        "db-sha",
        second,
    )


def test_langchain_checkpoint_metadata_is_hash_bound(tmp_path) -> None:
    langchain = load_script("run_langchain_toolchain.py")
    cache = tmp_path / "cache.jsonl"
    cache.write_text(
        json.dumps({"doc": "d1", "condition": "base", "edges": []})
        + "\n",
        encoding="utf-8",
    )
    metadata = tmp_path / "checkpoint.json"
    metadata.write_text(
        json.dumps({
            "checkpoint": {
                "bytes": cache.stat().st_size,
                "sha256": hashlib.sha256(cache.read_bytes()).hexdigest(),
                "records": 1,
            },
            "extraction_environment": {"model": "deepseek-v4-flash"},
        }),
        encoding="utf-8",
    )

    loaded = langchain.load_checkpoint_metadata(cache, metadata)
    assert loaded["extraction_environment"]["model"] == "deepseek-v4-flash"

    cache.write_text(cache.read_text(encoding="utf-8") + "\n")
    try:
        langchain.load_checkpoint_metadata(cache, metadata)
    except RuntimeError as error:
        assert "does not match" in str(error)
    else:
        raise AssertionError("tampered checkpoint was accepted")
