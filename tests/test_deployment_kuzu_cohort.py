import copy
import json
import sqlite3
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from graphguard.deployment_cohorts import (
    COHORT_ARTIFACT_TYPE,
    COHORT_ARTIFACT_VERSION,
    canonical_digest,
    select_anchored_cohort,
)
from graphguard.deployment_downstream import (
    build_downstream_artifact,
    load_registered_inputs,
)
from graphguard.deployment_kuzu_cohort import (
    KUZU_COHORT_ARTIFACT_TYPE,
    KUZU_COHORT_TEST_ARTIFACT_TYPE,
    REGISTERED_COHORT_MANIFEST_SHA256,
    _run_kuzu_cohort,
    _run_kuzu_cohort_for_test,
    load_kuzu_cohort_context,
    run_kuzu_cohort,
    write_json_atomic,
)
from graphguard.deployment_runner import (
    ARTIFACT_TYPE,
    ARTIFACT_VERSION,
    build_catalog,
    evaluate_pair,
)
from graphguard.kuzu_executor import KuzuGraph
from graphguard.sqlite_snapshot import sha256_file
ROOT = Path(__file__).resolve().parents[1]
RUN = "fixture"
PAIR_METADATA = {
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
}


def _git_commit() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _write_fixture(
    tmp_path,
    *,
    empty_base=False,
    missing_base_event=False,
):
    tmp_path.mkdir(parents=True, exist_ok=True)
    db_path = tmp_path / "source.db"
    with sqlite3.connect(db_path) as connection:
        connection.executescript(
            """
            CREATE TABLE extraction_events (
                event_id TEXT PRIMARY KEY,
                document_id TEXT
            );
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
        if not missing_base_event:
            connection.execute(
                "INSERT INTO extraction_events VALUES (?, ?)",
                ("base-1", "doc-1"),
            )
        connection.execute(
            "INSERT INTO extraction_events VALUES (?, ?)",
            ("cf-1", "doc-1"),
        )
        if not empty_base and not missing_base_event:
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
    catalog, queries = build_catalog(
        "doc-1",
        "schema-1",
        gold,
        {"r"},
    )
    base_edges = set() if empty_base or missing_base_event else {
        ("a", "r", "x")
    }
    cf_edges = {("a", "r", "y")}
    pair = evaluate_pair(
        {
            **PAIR_METADATA,
            "base_linked_row_count": len(base_edges),
            "cf_linked_row_count": len(cf_edges),
        },
        base_edges=base_edges,
        cf_edges=cf_edges,
        all_base_edge_count=len(base_edges),
        all_cf_edge_count=len(cf_edges),
        catalog_id=catalog["catalog_id"],
        queries=queries,
    )
    deployment = {
        "artifact_type": ARTIFACT_TYPE,
        "artifact_version": ARTIFACT_VERSION,
        "source_run": RUN,
        "source_database": {"sha256": sha256_file(db_path)},
        "query_catalogs": {catalog["catalog_id"]: catalog},
        "per_pair": [pair],
    }
    deployment_path = tmp_path / "deployment.json"
    deployment_path.write_text(
        json.dumps(deployment),
        encoding="utf-8",
    )
    inputs = load_registered_inputs(db_path, deployment_path)
    downstream = build_downstream_artifact(inputs)
    downstream_path = tmp_path / "downstream.json"
    downstream_path.write_text(
        json.dumps(downstream),
        encoding="utf-8",
    )
    selection = select_anchored_cohort(
        ["run-1"],
        ["run-1"],
        target_size=1,
        seed=0,
        authoritative_run_ids={"run-1"},
    )
    implementation_path = "graphguard/deployment_cohorts.py"
    manifest = {
        "artifact_type": COHORT_ARTIFACT_TYPE,
        "artifact_version": COHORT_ARTIFACT_VERSION,
        "protocol": {"selection_is_label_blind": True},
        "cohorts": {
            "rq10_n300": {
                RUN: {
                    "purpose": "test",
                    "source": {
                        "source_run": RUN,
                        "downstream_artifact": {
                            "path": str(downstream_path),
                            "sha256": sha256_file(downstream_path),
                        },
                        "deployment_artifact": {
                            "path": str(deployment_path),
                            "sha256": sha256_file(deployment_path),
                        },
                        "source_database": {
                            "path": str(db_path),
                            "sha256": sha256_file(db_path),
                        },
                        "n_authoritative_pairs": 1,
                        "n_registered_eligible_pairs": 1,
                    },
                    "selection_anchor": {
                        "method": "fixture",
                        "n_pairs": 1,
                        "run_ids_sha256": canonical_digest(["run-1"]),
                    },
                    "selection": selection,
                }
            }
        },
        "implementation": {
            "base_git_commit": _git_commit(),
            "source_state": "working_tree_content_hashes",
            "file_sha256": {
                implementation_path: sha256_file(
                    ROOT / implementation_path
                )
            },
        },
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    return {
        "db": db_path,
        "deployment": deployment_path,
        "downstream": downstream_path,
        "manifest": manifest_path,
        "manifest_value": manifest,
        "manifest_sha": sha256_file(manifest_path),
    }


def _load_fixture(files):
    return load_kuzu_cohort_context(
        files["manifest"],
        RUN,
        repo_root=ROOT,
        expected_manifest_sha256=files["manifest_sha"],
    )


def test_fixture_executes_actual_kuzu_without_official_provenance(
    tmp_path,
):
    files = _write_fixture(tmp_path)
    context = _load_fixture(files)

    artifact = _run_kuzu_cohort_for_test(context)

    assert artifact["artifact_type"] == KUZU_COHORT_TEST_ARTIFACT_TYPE
    assert artifact["status"] == "test_pass"
    assert artifact["complete"] is False
    assert artifact["protocol"]["execution_backend"] == (
        "test_injected_executor"
    )
    assert artifact["cohort"]["executed_run_ids"] == ["run-1"]
    assert artifact["execution"] == {
        "n_pairs_expected": 1,
        "n_pairs_completed": 1,
        "n_graphs_materialized": 2,
        "n_query_instances_checked": 1,
        "n_answer_sets_checked": 2,
        "n_mismatches": 0,
    }
    evidence = artifact["per_pair"][0]["per_query"][0]["kuzu_answers"]
    assert evidence["base_answer_count"] == 1
    assert evidence["cf_answer_count"] == 1
    assert len(evidence["base_answer_sha256"]) == 64
    assert len(evidence["cf_answer_sha256"]) == 64


def test_official_execution_rejects_unregistered_manifest(tmp_path):
    files = _write_fixture(tmp_path)
    context = _load_fixture(files)

    with pytest.raises(ValueError, match="registered manifest SHA"):
        run_kuzu_cohort(
            context,
        )


def test_official_entry_does_not_accept_executor_injection(tmp_path):
    files = _write_fixture(tmp_path)
    context = _load_fixture(files)

    with pytest.raises(TypeError, match="graph_factory"):
        run_kuzu_cohort(
            context,
            graph_factory=object,
        )


def test_internal_core_cannot_forge_official_kuzu_envelope(tmp_path):
    files = _write_fixture(tmp_path)
    context = _load_fixture(files)
    context.manifest_sha256 = REGISTERED_COHORT_MANIFEST_SHA256

    class OfflineGraph:
        pass

    with pytest.raises(
        ValueError,
        match="invalid official complete execution envelope",
    ):
        _run_kuzu_cohort(
            context,
            mode="complete",
            run_ids=context.selected_run_ids,
            artifact_type=KUZU_COHORT_ARTIFACT_TYPE,
            status="pass",
            complete=True,
            execution_backend="kuzu_cypher",
            enforce_registered_query_count=True,
            graph_factory=OfflineGraph,
        )


def test_cli_rejects_explicit_empty_runs():
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "run_deployment_kuzu_cohort.py"),
            "--runs",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 2
    assert "expected at least one argument" in result.stderr


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("digest", "selected ID digest mismatch"),
        ("duplicate", "not unique and complete"),
        ("anchor", "selection anchor digest mismatch"),
    ],
)
def test_context_rejects_tampered_selection(
    tmp_path,
    mutation,
    message,
):
    files = _write_fixture(tmp_path)
    manifest = copy.deepcopy(files["manifest_value"])
    selection = manifest["cohorts"]["rq10_n300"][RUN]["selection"]
    if mutation == "digest":
        selection["selected_run_ids_sha256"] = "wrong"
    elif mutation == "duplicate":
        selection["selected_run_ids"] = ["run-1", "run-1"]
        selection["target_size"] = 2
        selection["n_anchor"] = 2
    else:
        selection["anchor_run_ids_sha256"] = "tampered"
    files["manifest"].write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match=message):
        load_kuzu_cohort_context(
            files["manifest"],
            RUN,
            repo_root=ROOT,
            expected_manifest_sha256=sha256_file(files["manifest"]),
        )


def test_context_rejects_wrong_manifest_trust_anchor(tmp_path):
    files = _write_fixture(tmp_path)

    with pytest.raises(ValueError, match="cohort manifest SHA mismatch"):
        load_kuzu_cohort_context(
            files["manifest"],
            RUN,
            repo_root=ROOT,
            expected_manifest_sha256="wrong",
        )


def test_context_distinguishes_missing_event_from_legal_empty_graph(
    tmp_path,
):
    missing_files = _write_fixture(
        tmp_path / "missing",
        empty_base=True,
        missing_base_event=True,
    )
    with pytest.raises(ValueError, match="extraction event is missing"):
        _load_fixture(missing_files)

    empty_files = _write_fixture(
        tmp_path / "empty",
        empty_base=True,
    )
    context = _load_fixture(empty_files)
    artifact = _run_kuzu_cohort_for_test(context)
    evidence = artifact["per_pair"][0]["per_query"][0]["kuzu_answers"]
    assert evidence["base_answer_count"] == 0
    assert evidence["cf_answer_count"] == 1


def test_kuzu_answer_mismatch_fails_without_offline_fallback(tmp_path):
    files = _write_fixture(tmp_path)
    context = _load_fixture(files)

    class WrongGraph:
        def __init__(self, edges):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return None

        def execute(self, query):
            return {"wrong"}

    with pytest.raises(ValueError, match="answer hash mismatch"):
        _run_kuzu_cohort_for_test(
            context,
            graph_factory=WrongGraph,
        )


def test_kuzu_constructor_failure_removes_temporary_directory(
    tmp_path,
    monkeypatch,
):
    directory = tmp_path / "kuzu-constructor-failure"

    def make_directory(prefix):
        directory.mkdir()
        return str(directory)

    class BrokenKuzu:
        @staticmethod
        def Database(path):
            raise RuntimeError("construction failed")

    monkeypatch.setattr(
        "graphguard.kuzu_executor.tempfile.mkdtemp",
        make_directory,
    )
    monkeypatch.setitem(sys.modules, "kuzu", BrokenKuzu)

    with pytest.raises(RuntimeError, match="construction failed"):
        KuzuGraph(set())

    assert not directory.exists()


def test_kuzu_constructor_interrupt_removes_temporary_directory(
    tmp_path,
    monkeypatch,
):
    directory = tmp_path / "kuzu-constructor-interrupt"

    def make_directory(prefix):
        directory.mkdir()
        return str(directory)

    class InterruptedKuzu:
        @staticmethod
        def Database(path):
            raise KeyboardInterrupt

    monkeypatch.setattr(
        "graphguard.kuzu_executor.tempfile.mkdtemp",
        make_directory,
    )
    monkeypatch.setitem(sys.modules, "kuzu", InterruptedKuzu)

    with pytest.raises(KeyboardInterrupt):
        KuzuGraph(set())

    assert not directory.exists()


def test_atomic_writer_refuses_overwrite_and_leaves_no_temp(tmp_path):
    output = tmp_path / "artifact.json"
    write_json_atomic(output, {"status": "pass"}, overwrite=False)
    assert json.loads(output.read_text(encoding="utf-8")) == {
        "status": "pass"
    }

    with pytest.raises(FileExistsError):
        write_json_atomic(output, {"status": "changed"}, overwrite=False)

    assert not list(tmp_path.glob(".*.tmp"))
