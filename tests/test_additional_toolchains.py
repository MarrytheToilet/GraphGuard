from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]


def load_script():
    path = ROOT / "scripts/run_additional_toolchains.py"
    spec = importlib.util.spec_from_file_location(
        "run_additional_toolchains",
        path,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_declared_edges_inverts_registered_rename_and_reports_other_labels():
    module = load_script()
    raw = [
        ["Alice", "WORKS_FOR", "Acme"],
        ["Alice", "NOT_IN_SCHEMA", "Paris"],
    ]
    edges, off_schema = module.declared_edges(
        raw,
        "schema_rename",
        ["employer"],
    )
    assert edges == [["alice", "employer", "acme"]]
    assert off_schema == 1


def test_neo4j_edges_use_node_names_not_component_ids():
    module = load_script()
    graph = SimpleNamespace(
        nodes=[
            SimpleNamespace(id="chunk:0", properties={"name": "Alice"}),
            SimpleNamespace(id="chunk:1", properties={"name": "Acme"}),
        ],
        relationships=[
            SimpleNamespace(
                start_node_id="chunk:0",
                end_node_id="chunk:1",
                type="EMPLOYER",
            )
        ],
    )
    edges, nodes = module.neo4j_edges_from_graph(graph)
    assert edges == [["Alice", "EMPLOYER", "Acme"]]
    assert len(nodes) == 2


def test_analysis_matches_langchain_empty_pair_and_threshold_rules():
    module = load_script()
    common = {
        "cohort_fingerprint": "cohort",
        "model": "model",
        "dependency_versions": {"pkg": "1"},
        "extraction_mode": "mode",
        "outer_workers": 1,
        "error_classification": "failures remain failures",
        "native_diagnostics": {"native_output_status": "nonempty"},
        "config_fingerprint": "config",
        "input_sha256": "input",
        "raw_edge_count": 1,
        "off_schema_relation_count": 0,
    }
    records = []
    for document, base, changed in [
        ("d1", [["a", "employer", "b"]], [["a", "employer", "c"]]),
        ("d2", [], []),
    ]:
        records.append(
            {
                **common,
                "doc": document,
                "condition": "base",
                "edges": base,
            }
        )
        records.append(
            {
                **common,
                "doc": document,
                "condition": "schema_reorder",
                "edges": changed,
            }
        )
    summary, selection = module.analyze_records(
        records,
        "llamaindex",
    )
    row = summary["schema_reorder"]
    assert selection["attempted_documents"] == 2
    assert row["n"] == 1
    assert row["empty_empty_excluded"] == 1
    assert row["mean_drift"] == 1.0
    assert row["violation_rate"] == 1.0


def test_completed_keys_do_not_retry_failed_endpoints():
    module = load_script()
    failed = {
        "cohort_fingerprint": "cohort",
        "doc": "d1",
        "condition": "base",
        "config_fingerprint": "config",
        "input_sha256": "input",
        "edges": None,
    }
    assert module.completed_keys([failed]) == {
        ("cohort", "d1", "base", "config", "input")
    }


def _calibration_records(module, native_failures=()):
    failures = set(native_failures)
    records = []
    for mode in module.LLAMA_MODES:
        for doc_index in range(10):
            for condition in module.CONDITIONS:
                failed = (
                    mode == "native"
                    and (doc_index, condition) in failures
                )
                records.append(
                    {
                        "cohort_fingerprint": f"cohort-{mode}",
                        "config_fingerprint": f"config-{mode}-{condition}",
                        "input_sha256": f"input-{doc_index}-{condition}",
                        "doc": f"doc-{doc_index}",
                        "condition": condition,
                        "llama_mode": mode,
                        "edges": (
                            None
                            if failed
                            else [["source", "relation", "target"]]
                        ),
                    }
                )
    return records


def test_calibration_prefers_native_when_both_modes_qualify():
    module = load_script()
    summary = module.llama_calibration_summary(
        _calibration_records(module)
    )
    assert summary["modes"]["native"]["qualified"] is True
    assert summary["modes"]["json_object"]["qualified"] is True
    assert summary["selected_mode"] == "native"


def test_calibration_selects_json_only_after_frozen_paired_gate():
    module = load_script()
    failures = {
        (doc_index, module.CONDITIONS[1 + doc_index % 5])
        for doc_index in range(10)
    }
    summary = module.llama_calibration_summary(
        _calibration_records(module, failures)
    )
    assert summary["modes"]["native"]["qualified"] is False
    assert summary["modes"]["json_object"]["qualified"] is True
    assert (
        summary["paired_mode_comparison"][
            "json_object_success_improvement"
        ]
        == 10
    )
    assert summary["selected_mode"] == "json_object"


def test_llama_modes_have_distinct_fingerprints():
    module = load_script()
    common = (
        "llamaindex",
        ["relation"],
        "database-sha",
        {"package": "1"},
        1,
    )
    native = module.cohort_fingerprint(*common, "native")
    json_object = module.cohort_fingerprint(*common, "json_object")
    assert native != json_object


def test_failed_record_does_not_serialize_exception_text(monkeypatch):
    module = load_script()
    monkeypatch.setenv("OPENAI_MODEL", "model")
    error = module.LlamaIndexNativeParseError(
        "safe public message",
        {
            "native_output_status": "parse_error",
            "parse_error_cause": "ValueError",
            "response_sha256": "hash",
        },
    )
    error.__cause__ = ValueError("SENSITIVE GENERATED CONTENT")
    record = module.failed_record(
        "llamaindex",
        "base",
        "doc",
        "raw text",
        ["raw text"],
        ["relation"],
        "cohort",
        {"package": "1"},
        1,
        "native",
        error,
    )
    serialized = str(record)
    assert record["error"] == "LlamaIndexNativeParseError"
    assert "SENSITIVE GENERATED CONTENT" not in serialized


def test_numeric_metadata_drops_text_and_booleans():
    module = load_script()
    assert module.numeric_metadata(
        {
            "completion_tokens": 4096,
            "details": {
                "reasoning_tokens": 4096,
                "provider_note": "secret text",
            },
            "flag": True,
        }
    ) == {
        "completion_tokens": 4096,
        "details": {"reasoning_tokens": 4096},
    }


def test_neo4j_mode_records_non_thinking_control():
    module = load_script()
    mode = module.extraction_mode("neo4j")
    assert "thinking disabled" in mode
    assert (
        module.THINKING_CONTROL["neo4j"]
        == "disabled via extra_body.enable_thinking=false"
    )


def test_load_doc_by_id_selects_the_requested_failure_probe():
    module = load_script()
    doc_id = "docred-validation-000004-Conrad_O__Johnson"
    selected_id, raw, sentences = module.load_doc_by_id(doc_id)
    assert selected_id == doc_id
    assert raw
    assert sentences


def test_analyze_only_defaults_to_published_checkpoint(monkeypatch):
    module = load_script()
    captured = {}
    args = SimpleNamespace(
        calibrate_llama=False,
        combine_only=False,
        toolchain="neo4j",
        llama_mode="native",
        cache=None,
        output=None,
        cohort=None,
        analyze_only=True,
        publish=False,
        publish_existing=False,
        limit=100,
        doc_id=None,
        workers=1,
    )
    monkeypatch.setattr(module, "parse_args", lambda: args)

    def capture_analysis(toolchain, cache, output, cohort, metadata):
        captured.update(
            toolchain=toolchain,
            cache=cache,
            output=output,
            cohort=cohort,
            metadata=metadata,
        )

    monkeypatch.setattr(module, "write_analysis", capture_analysis)
    monkeypatch.setattr(
        module,
        "run_extraction",
        lambda *unused, **unused_kw: (_ for _ in ()).throw(
            AssertionError("analyze-only must not call the model")
        ),
    )

    module.main()

    assert captured == {
        "toolchain": "neo4j",
        "cache": module.PUBLISHED_CACHE["neo4j"],
        "output": module.OUTPUT["neo4j"],
        "cohort": None,
        "metadata": module.CHECKPOINT_METADATA["neo4j"],
    }
