import copy
import json
import sqlite3
from pathlib import Path

import pytest

from graphguard.deployment_downstream import (
    FormalInputs,
    build_downstream_artifact,
    evaluate_utility_pair,
    load_registered_inputs,
    load_kuzu_parity_evidence,
)
from graphguard.deployment_runner import (
    ARTIFACT_TYPE,
    build_catalog,
    evaluate_pair,
)
from graphguard.deployment_parity import select_pairs
from graphguard.sqlite_snapshot import sha256_file


PAIR = {
    "run_id": "run-1",
    "document_id": "doc-1",
    "intervention_id": "iv-1",
    "cause_family": "prompt",
    "semantic_class": "presentation",
    "operator": "reorder",
    "target_type": "prompt",
    "target_id": "reorder",
    "base_event_id": "base-1",
    "cf_event_id": "cf-1",
    "base_schema_id": "schema-1",
    "cf_schema_id": "schema-1",
    "base_linked_row_count": 1,
    "cf_linked_row_count": 1,
}


def _inputs():
    gold = {("a", "r", "x")}
    catalog, queries = build_catalog("doc-1", "schema-1", gold, {"r"})
    base = {("a", "r", "x")}
    counterfactual = {("a", "r", "y")}
    pair = evaluate_pair(
        PAIR,
        base_edges=base,
        cf_edges=counterfactual,
        all_base_edge_count=1,
        all_cf_edge_count=1,
        catalog_id=catalog["catalog_id"],
        queries=queries,
    )
    inputs = FormalInputs(
        db_path=Path("source.db"),
        deployment_artifact_path=Path("artifact.json"),
        deployment_artifact={"per_pair": [pair]},
        pairs_by_run_id={"run-1": pair},
        queries_by_catalog={catalog["catalog_id"]: queries},
        edges_by_event={"base-1": base, "cf-1": counterfactual},
        gold_by_document={"doc-1": gold},
        source_before={},
        source_after={},
    )
    return inputs, pair


def test_utility_pair_uses_registered_queries_and_directional_sign():
    inputs, pair = _inputs()
    record = evaluate_utility_pair(inputs, pair)

    assert record is not None
    assert record["n_queries"] == 1
    assert record["mean_f1_base"] == 1.0
    assert record["mean_f1_cf"] == 0.0
    assert record["mean_delta_f1_abs"] == 1.0
    assert record["mean_delta_f1_signed"] == 1.0
    assert record["max_answer_drift"] == 1.0
    assert record["delta_recall_abs"] == 1.0
    assert record["delta_precision_abs"] == 1.0
    assert record["families"]["deployment.lookup"]["eligible"] is True
    assert (
        record["families"]["deployment.shared_tail_join"]["eligible"]
        is False
    )


def test_utility_pair_rejects_answer_hash_mismatch():
    inputs, pair = _inputs()
    pair["families"]["deployment.lookup"]["queries"][0][
        "base_answer_sha256"
    ] = "wrong"

    with pytest.raises(ValueError, match="base answer hash mismatch"):
        evaluate_utility_pair(inputs, pair)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("base_answer_count", 99, "base answer count mismatch"),
        ("cf_answer_count", 99, "cf answer count mismatch"),
        ("answer_jaccard", 0.25, "answer Jaccard mismatch"),
        ("query_drift", 0.25, "query drift mismatch"),
        ("answer_state", "both_empty", "answer state mismatch"),
    ],
)
def test_utility_pair_rejects_derived_answer_field_mismatch(
    field,
    value,
    message,
):
    inputs, pair = _inputs()
    pair["families"]["deployment.lookup"]["queries"][0][field] = value

    with pytest.raises(ValueError, match=message):
        evaluate_utility_pair(inputs, pair)


def test_utility_pair_rejects_cf_answer_hash_mismatch():
    inputs, pair = _inputs()
    pair["families"]["deployment.lookup"]["queries"][0][
        "cf_answer_sha256"
    ] = "wrong"

    with pytest.raises(ValueError, match="cf answer hash mismatch"):
        evaluate_utility_pair(inputs, pair)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("duplicate", "duplicate registered query"),
        ("extra", "query inventory mismatch"),
        ("count", "query count mismatch"),
        ("eligibility", "eligibility mismatch"),
    ],
)
def test_utility_pair_requires_exact_query_inventory(mutation, message):
    inputs, pair = _inputs()
    family = pair["families"]["deployment.lookup"]
    if mutation == "duplicate":
        family["queries"].append(copy.deepcopy(family["queries"][0]))
    elif mutation == "extra":
        extra = copy.deepcopy(family["queries"][0])
        extra["query_id"] = "extra"
        family["queries"].append(extra)
    elif mutation == "count":
        family["n_queries"] += 1
    else:
        family["eligible"] = False

    with pytest.raises(ValueError, match=message):
        evaluate_utility_pair(inputs, pair)


def test_utility_pair_handles_both_empty_answers():
    inputs, pair = _inputs()
    inputs.edges_by_event = {
        "base-1": {("unrelated", "r", "base")},
        "cf-1": {("unrelated", "r", "cf")},
    }
    pair = evaluate_pair(
        PAIR,
        base_edges=inputs.edges_by_event["base-1"],
        cf_edges=inputs.edges_by_event["cf-1"],
        all_base_edge_count=1,
        all_cf_edge_count=1,
        catalog_id=pair["query_catalog_id"],
        queries=inputs.queries_by_catalog[pair["query_catalog_id"]],
    )

    record = evaluate_utility_pair(inputs, pair)

    assert record["mean_f1_base"] == 0.0
    assert record["mean_f1_cf"] == 0.0
    assert record["mean_delta_f1_abs"] == 0.0
    assert record["mean_delta_f1_signed"] == 0.0
    assert record["max_answer_drift"] == 0.0


def test_utility_pair_returns_none_for_registered_empty_catalog():
    inputs, _ = _inputs()
    pair = evaluate_pair(
        PAIR,
        base_edges=set(),
        cf_edges=set(),
        all_base_edge_count=0,
        all_cf_edge_count=0,
        catalog_id="empty",
        queries=[],
    )
    inputs.queries_by_catalog = {"empty": []}

    assert evaluate_utility_pair(inputs, pair) is None


@pytest.mark.parametrize(
    "mutation",
    ["eligibility", "count", "query", "missing_family", "extra_family"],
)
def test_empty_catalog_still_requires_exact_inventory(mutation):
    inputs, _ = _inputs()
    pair = evaluate_pair(
        PAIR,
        base_edges=set(),
        cf_edges=set(),
        all_base_edge_count=0,
        all_cf_edge_count=0,
        catalog_id="empty",
        queries=[],
    )
    inputs.queries_by_catalog = {"empty": []}
    lookup = pair["families"]["deployment.lookup"]
    if mutation == "eligibility":
        lookup["eligible"] = True
    elif mutation == "count":
        lookup["n_queries"] = 1
    elif mutation == "query":
        lookup["queries"].append({"query_id": "bogus"})
    elif mutation == "missing_family":
        pair["families"].pop("deployment.lookup")
    else:
        pair["families"]["deployment.bogus"] = {
            "eligible": False,
            "n_queries": 0,
            "queries": [],
        }

    with pytest.raises(ValueError):
        evaluate_utility_pair(inputs, pair)


def test_nonempty_catalog_rejects_extra_family():
    inputs, pair = _inputs()
    pair["families"]["deployment.bogus"] = {
        "eligible": False,
        "n_queries": 0,
        "queries": [],
    }

    with pytest.raises(ValueError, match="family inventory mismatch"):
        evaluate_utility_pair(inputs, pair)


def test_utility_pair_weights_query_instances_not_family_means():
    gold = {
        ("a", "r", "x"),
        ("b", "r", "y"),
        ("b", "s", "z"),
    }
    catalog, queries = build_catalog("doc-1", "schema-1", gold, {"r", "s"})
    base = set(gold)
    counterfactual = {("a", "r", "wrong"), ("b", "r", "y")}
    pair = evaluate_pair(
        {**PAIR, "base_linked_row_count": 3, "cf_linked_row_count": 2},
        base_edges=base,
        cf_edges=counterfactual,
        all_base_edge_count=3,
        all_cf_edge_count=2,
        catalog_id=catalog["catalog_id"],
        queries=queries,
    )
    inputs = FormalInputs(
        db_path=Path("source.db"),
        deployment_artifact_path=Path("artifact.json"),
        deployment_artifact={"per_pair": [pair]},
        pairs_by_run_id={"run-1": pair},
        queries_by_catalog={catalog["catalog_id"]: queries},
        edges_by_event={"base-1": base, "cf-1": counterfactual},
        gold_by_document={"doc-1": gold},
        source_before={},
        source_after={},
    )

    record = evaluate_utility_pair(inputs, pair)
    per_query_mean = sum(
        row["delta_f1_abs"] for row in record["per_query"]
    ) / len(record["per_query"])
    eligible_family_means = [
        family["mean_delta_f1_abs"]
        for family in record["families"].values()
        if family["eligible"]
    ]

    assert record["mean_delta_f1_abs"] == pytest.approx(per_query_mean)
    assert record["mean_delta_f1_abs"] != pytest.approx(
        sum(eligible_family_means) / len(eligible_family_means)
    )


def test_full_gold_precision_and_recall_use_full_document_denominators():
    inputs, pair = _inputs()
    inputs.gold_by_document["doc-1"].add(("b", "r", "z"))

    record = evaluate_utility_pair(inputs, pair)

    assert record["delta_recall_abs"] == 0.5
    assert record["delta_precision_abs"] == 1.0


def test_optional_executors_remain_subject_to_registered_validation():
    inputs, pair = _inputs()

    record = evaluate_utility_pair(
        inputs,
        pair,
        base_executor=lambda query: {"x"},
        cf_executor=lambda query: {"y"},
    )

    assert record["mean_delta_f1_signed"] == 1.0


def _write_minimal_registered_fixture(tmp_path):
    db_path = tmp_path / "source.db"
    with sqlite3.connect(db_path) as connection:
        connection.executescript(
            """
            CREATE TABLE extracted_edges (
                event_id TEXT,
                subject_entity_id TEXT,
                relation TEXT,
                object_entity_id TEXT
            );
            CREATE TABLE gold_edges (
                document_id TEXT,
                head_entity_id TEXT,
                relation_base TEXT,
                tail_entity_id TEXT
            );
            CREATE TABLE schemas (
                schema_id TEXT,
                relation_types_json TEXT
            );
            """
        )
        connection.execute(
            "INSERT INTO extracted_edges VALUES (?, ?, ?, ?)",
            ("base-1", "a", "r", "x"),
        )
        connection.execute(
            "INSERT INTO extracted_edges VALUES (?, ?, ?, ?)",
            ("cf-1", "a", "r", "y"),
        )
        connection.execute(
            "INSERT INTO gold_edges VALUES (?, ?, ?, ?)",
            ("doc-1", "a", "r", "x"),
        )
        connection.execute(
            "INSERT INTO schemas VALUES (?, ?)",
            ("schema-1", json.dumps([{"id": "r"}])),
        )

    gold = {("a", "r", "x")}
    catalog, queries = build_catalog("doc-1", "schema-1", gold, {"r"})
    pair = evaluate_pair(
        PAIR,
        base_edges={("a", "r", "x")},
        cf_edges={("a", "r", "y")},
        all_base_edge_count=1,
        all_cf_edge_count=1,
        catalog_id=catalog["catalog_id"],
        queries=queries,
    )
    artifact = {
        "artifact_type": ARTIFACT_TYPE,
        "artifact_version": 1,
        "source_run": "fixture",
        "source_database": {"sha256": sha256_file(db_path)},
        "query_catalogs": {catalog["catalog_id"]: catalog},
        "per_pair": [pair],
    }
    artifact_path = tmp_path / "deployment.json"
    artifact_path.write_text(json.dumps(artifact), encoding="utf-8")
    return db_path, artifact_path, artifact


def test_load_registered_inputs_rebuilds_catalog_and_source(tmp_path):
    db_path, artifact_path, _ = _write_minimal_registered_fixture(tmp_path)

    inputs = load_registered_inputs(db_path, artifact_path)

    assert len(inputs.pairs_by_run_id) == 1
    assert len(inputs.queries_by_catalog) == 1
    assert inputs.source_before["main"]["sha256"] == sha256_file(db_path)
    assert inputs.source_after["wal"]["size_bytes"] == 0


def test_load_registered_inputs_rejects_catalog_mismatch(tmp_path):
    db_path, artifact_path, artifact = _write_minimal_registered_fixture(
        tmp_path
    )
    catalog = next(iter(artifact["query_catalogs"].values()))
    catalog["eligible_gold_edge_count"] = 99
    artifact_path.write_text(json.dumps(artifact), encoding="utf-8")

    with pytest.raises(ValueError, match="query catalog mismatch"):
        load_registered_inputs(db_path, artifact_path)


def test_load_registered_inputs_rejects_database_hash_mismatch(tmp_path):
    db_path, artifact_path, artifact = _write_minimal_registered_fixture(
        tmp_path
    )
    artifact["source_database"]["sha256"] = "wrong"
    artifact_path.write_text(json.dumps(artifact), encoding="utf-8")

    with pytest.raises(ValueError, match="source database hash differs"):
        load_registered_inputs(db_path, artifact_path)


def test_load_registered_inputs_rejects_nonempty_wal(tmp_path):
    db_path, artifact_path, _ = _write_minimal_registered_fixture(tmp_path)
    Path(f"{db_path}-wal").write_bytes(b"not-empty")

    with pytest.raises(RuntimeError, match="non-empty WAL"):
        load_registered_inputs(db_path, artifact_path)


def test_build_downstream_artifact_drops_only_empty_workloads(tmp_path):
    inputs, pair = _inputs()
    empty_pair = evaluate_pair(
        {**PAIR, "run_id": "run-empty"},
        base_edges=set(),
        cf_edges=set(),
        all_base_edge_count=0,
        all_cf_edge_count=0,
        catalog_id="empty",
        queries=[],
    )
    inputs.deployment_artifact = {
        "source_run": "fixture",
        "per_pair": [pair, empty_pair],
    }
    inputs.source_before = {
        "main": {"sha256": "source-sha"},
        "wal": {"size_bytes": 0},
    }
    inputs.source_after = copy.deepcopy(inputs.source_before)
    inputs.deployment_artifact_path = tmp_path / "deployment.json"
    inputs.deployment_artifact_path.write_text(
        json.dumps(inputs.deployment_artifact),
        encoding="utf-8",
    )
    inputs.queries_by_catalog["empty"] = []

    artifact = build_downstream_artifact(inputs)

    assert artifact["protocol"]["execution_backend"] == (
        "offline_set_semantics"
    )
    assert artifact["population"] == {
        "n_authoritative_pairs": 2,
        "n_pairs_with_nonempty_workload": 1,
        "n_pairs_without_workload": 1,
        "n_query_evaluations": 1,
    }


def test_kuzu_parity_evidence_is_hash_linked(tmp_path):
    db_path, deployment_path, _ = _write_minimal_registered_fixture(tmp_path)
    inputs = load_registered_inputs(db_path, deployment_path)
    parity_path = tmp_path / "parity.json"
    selected, selection = select_pairs(
        inputs.deployment_artifact["per_pair"],
        seed=0,
        min_pairs=1,
    )
    n_queries = sum(
        len(inputs.queries_by_catalog[pair["query_catalog_id"]])
        for pair in selected
    )
    parity = {
        "artifact_type": "graphguard.deployment_q1q4_kuzu_parity",
        "artifact_version": 1,
        "source_run": "fixture",
        "source_database": {"sha256": sha256_file(db_path)},
        "deployment_artifact": {"sha256": sha256_file(deployment_path)},
        "status": "pass",
        "kuzu_version": "0.11.3",
        "n_graph_pairs_materialized": 1,
        "n_query_instances_checked": n_queries,
        "n_answer_sets_checked": 2 * n_queries,
        "n_mismatches": 0,
        "mismatches": [],
        "selection": selection,
    }
    parity_path.write_text(json.dumps(parity), encoding="utf-8")

    evidence = load_kuzu_parity_evidence(
        inputs,
        parity_path,
        selection_min_pairs=1,
    )

    assert evidence["sha256"] == sha256_file(parity_path)
    assert evidence["status"] == "pass"
    assert evidence["n_answer_sets_checked"] == 2


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("deployment", "another deployment artifact"),
        ("database", "another source database"),
        ("status", "did not pass"),
        ("coverage", "selection mismatch"),
    ],
)
def test_kuzu_parity_evidence_rejects_broken_links(
    tmp_path,
    mutation,
    message,
):
    db_path, deployment_path, _ = _write_minimal_registered_fixture(tmp_path)
    inputs = load_registered_inputs(db_path, deployment_path)
    selected, selection = select_pairs(
        inputs.deployment_artifact["per_pair"],
        seed=0,
        min_pairs=1,
    )
    n_queries = sum(
        len(inputs.queries_by_catalog[pair["query_catalog_id"]])
        for pair in selected
    )
    parity = {
        "artifact_type": "graphguard.deployment_q1q4_kuzu_parity",
        "artifact_version": 1,
        "source_run": "fixture",
        "source_database": {"sha256": sha256_file(db_path)},
        "deployment_artifact": {"sha256": sha256_file(deployment_path)},
        "status": "pass",
        "kuzu_version": "0.11.3",
        "n_graph_pairs_materialized": 1,
        "n_query_instances_checked": n_queries,
        "n_answer_sets_checked": 2 * n_queries,
        "n_mismatches": 0,
        "mismatches": [],
        "selection": selection,
    }
    if mutation == "deployment":
        parity["deployment_artifact"]["sha256"] = "wrong"
    elif mutation == "database":
        parity["source_database"]["sha256"] = "wrong"
    elif mutation == "status":
        parity["status"] = "fail"
        parity["n_mismatches"] = 1
    else:
        parity["selection"]["covered_tokens"] = []
    parity_path = tmp_path / "parity.json"
    parity_path.write_text(json.dumps(parity), encoding="utf-8")

    with pytest.raises(ValueError, match=message):
        load_kuzu_parity_evidence(
            inputs,
            parity_path,
            selection_min_pairs=1,
        )


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("version", "unsupported Kuzu parity version"),
        ("empty_coverage", "selection mismatch"),
        ("selection_sha", "selection mismatch"),
        ("pair_count", "n_graph_pairs_materialized mismatch"),
        ("query_count", "n_query_instances_checked mismatch"),
        ("answer_count", "n_answer_sets_checked mismatch"),
        ("mismatches", "did not pass"),
        ("kuzu_version", "Kuzu parity version mismatch"),
    ],
)
def test_kuzu_parity_evidence_rejects_self_consistent_tampering(
    tmp_path,
    mutation,
    message,
):
    db_path, deployment_path, _ = _write_minimal_registered_fixture(tmp_path)
    inputs = load_registered_inputs(db_path, deployment_path)
    selected, selection = select_pairs(
        inputs.deployment_artifact["per_pair"],
        seed=0,
        min_pairs=1,
    )
    n_queries = sum(
        len(inputs.queries_by_catalog[pair["query_catalog_id"]])
        for pair in selected
    )
    parity = {
        "artifact_type": "graphguard.deployment_q1q4_kuzu_parity",
        "artifact_version": 1,
        "source_run": "fixture",
        "source_database": {"sha256": sha256_file(db_path)},
        "deployment_artifact": {"sha256": sha256_file(deployment_path)},
        "status": "pass",
        "kuzu_version": "0.11.3",
        "n_graph_pairs_materialized": len(selected),
        "n_query_instances_checked": n_queries,
        "n_answer_sets_checked": 2 * n_queries,
        "n_mismatches": 0,
        "mismatches": [],
        "selection": selection,
    }
    if mutation == "version":
        parity["artifact_version"] = 999
    elif mutation == "empty_coverage":
        parity["selection"]["required_coverage_tokens"] = []
        parity["selection"]["covered_tokens"] = []
    elif mutation == "selection_sha":
        parity["selection"]["selection_sha256"] = "wrong"
    elif mutation == "pair_count":
        parity["n_graph_pairs_materialized"] = 0
    elif mutation == "query_count":
        parity["n_query_instances_checked"] = 0
    elif mutation == "answer_count":
        parity["n_answer_sets_checked"] = 0
    elif mutation == "kuzu_version":
        parity["kuzu_version"] = "forged"
    else:
        parity["mismatches"] = [{"run_id": "fake"}]
    parity_path = tmp_path / "parity.json"
    parity_path.write_text(json.dumps(parity), encoding="utf-8")

    with pytest.raises(ValueError, match=message):
        load_kuzu_parity_evidence(
            inputs,
            parity_path,
            selection_min_pairs=1,
        )
