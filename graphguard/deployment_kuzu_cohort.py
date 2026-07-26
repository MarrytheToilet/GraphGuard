"""Fail-closed Kuzu execution for registered deployment cohorts."""

from __future__ import annotations

import copy
import json
import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping, Sequence

from graphguard.deployment_cohorts import (
    COHORT_ARTIFACT_TYPE,
    COHORT_ARTIFACT_VERSION,
    canonical_digest,
)
from graphguard.deployment_downstream import (
    DOWNSTREAM_ARTIFACT_TYPE,
    DOWNSTREAM_ARTIFACT_VERSION,
    FormalInputs,
    _answer_state,
    _query_identifier,
    evaluate_utility_pair,
    load_registered_inputs,
)
from graphguard.deployment_runner import (
    ARTIFACT_TYPE,
    ARTIFACT_VERSION,
    _set_digest,
)
from graphguard.kuzu_executor import KuzuGraph, kuzu_version
from graphguard.qa import jaccard
from graphguard.sqlite_snapshot import (
    database_fingerprint,
    require_stable_quiescent_snapshot,
    runtime_versions,
    sha256_file,
)


KUZU_COHORT_ARTIFACT_TYPE = "graphguard.deployment_q1q4_kuzu_cohort"
KUZU_COHORT_SMOKE_ARTIFACT_TYPE = (
    "graphguard.deployment_q1q4_kuzu_cohort_smoke"
)
KUZU_COHORT_TEST_ARTIFACT_TYPE = (
    "graphguard.deployment_q1q4_kuzu_cohort_test"
)
KUZU_COHORT_ARTIFACT_VERSION = 1
REGISTERED_COHORT_MANIFEST_SHA256 = (
    "b0b551d6fa91d3e75bce1339a30875ce3ee516c8c415c30487e0ee2aa4295d43"
)
REGISTERED_KUZU_VERSION = "0.11.3"
REGISTERED_QUERY_COUNTS = {
    "cdr__deepseek-v4-flash__300d": 583,
    "docred__deepseek-v4-flash__300d": 5703,
    "redocred__deepseek-v4-flash__300d": 11110,
    "scierc__deepseek-v4-flash__100d": 4910,
}
REGISTERED_SMOKE_RUN_IDS = {
    "cdr__deepseek-v4-flash__300d": (
        "run-096d732a8f",
        "run-e39fb73339",
    ),
    "docred__deepseek-v4-flash__300d": (
        "run-d4f94330d2",
        "run-68614210a2",
    ),
    "redocred__deepseek-v4-flash__300d": (
        "run-03202781c0",
        "run-e43c68e2b7",
    ),
    "scierc__deepseek-v4-flash__100d": (
        "run-bc6bff607f",
        "run-a4cc33067e",
    ),
}


@dataclass
class KuzuCohortContext:
    repo_root: Path
    manifest_path: Path
    manifest_sha256: str
    manifest: dict
    source_run: str
    cohort_key: str
    cohort_entry: dict
    selected_run_ids: list[str]
    inputs: FormalInputs
    downstream_path: Path
    downstream_artifact: dict
    downstream_by_run_id: dict[str, dict]
    source_hashes_before: dict[str, str]


def _read_json(path: Path, label: str) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read {label}: {path}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object: {path}")
    return value


def _resolve_recorded_path(recorded: str, repo_root: Path) -> Path:
    """Resolve a recorded absolute path without weakening hash validation."""
    path = Path(recorded)
    if path.exists():
        return path
    parts = path.parts
    for anchor in ("reports", "data"):
        if anchor in parts:
            relocated = repo_root.joinpath(*parts[parts.index(anchor):])
            if relocated.exists():
                return relocated
    raise FileNotFoundError(f"recorded source path does not exist: {recorded}")


def _require_sha(path: Path, expected: str, label: str) -> str:
    actual = sha256_file(path)
    if actual != expected:
        raise ValueError(f"{label} SHA mismatch: {actual} != {expected}")
    return actual


def _validate_manifest_implementation(
    manifest: Mapping,
    repo_root: Path,
) -> None:
    implementation = manifest.get("implementation", {})
    base_commit = implementation.get("base_git_commit")
    source_state = implementation.get("source_state")
    recorded_hashes = implementation.get("file_sha256")
    if (
        not isinstance(base_commit, str)
        or len(base_commit) != 40
        or source_state != "working_tree_content_hashes"
        or not isinstance(recorded_hashes, dict)
        or not recorded_hashes
    ):
        raise ValueError("manifest implementation provenance is incomplete")
    try:
        int(base_commit, 16)
    except ValueError as exc:
        raise ValueError("manifest base commit is invalid") from exc
    for relative_path, expected in recorded_hashes.items():
        current_path = repo_root / relative_path
        _require_sha(
            current_path,
            expected,
            f"manifest implementation {relative_path}",
        )


def _require_artifact_identity(
    artifact: Mapping,
    *,
    artifact_type: str,
    artifact_version: int,
    source_run: str,
    label: str,
) -> None:
    if artifact.get("artifact_type") != artifact_type:
        raise ValueError(f"{label} artifact type mismatch")
    if artifact.get("artifact_version") != artifact_version:
        raise ValueError(f"{label} artifact version mismatch")
    if artifact.get("source_run") != source_run:
        raise ValueError(f"{label} source run mismatch")


def _validate_selection_shape(selection: Mapping) -> list[str]:
    selected = selection.get("selected_run_ids")
    retained = selection.get("retained_run_ids")
    replacements = selection.get("replacement_run_ids")
    excluded = selection.get("excluded")
    if not all(
        isinstance(value, list)
        for value in (selected, retained, replacements, excluded)
    ):
        raise ValueError("cohort selection lists are incomplete")
    target = selection.get("target_size")
    if not isinstance(target, int) or target <= 0:
        raise ValueError("cohort target size is invalid")
    if len(selected) != target or len(selected) != len(set(selected)):
        raise ValueError("cohort selected IDs are not unique and complete")
    if selected != retained + replacements:
        raise ValueError("cohort selected IDs do not preserve registered order")
    expected_counts = {
        "n_anchor": target,
        "n_retained": len(retained),
        "n_excluded": len(excluded),
        "n_replacements": len(replacements),
    }
    for field, expected in expected_counts.items():
        if selection.get(field) != expected:
            raise ValueError(f"cohort {field} mismatch")
    if len(excluded) != len(replacements):
        raise ValueError("cohort exclusions and replacements are unbalanced")
    if canonical_digest(selected) != selection.get(
        "selected_run_ids_sha256"
    ):
        raise ValueError("cohort selected ID digest mismatch")
    return list(selected)


def _validate_event_and_edge_inventory(
    inputs: FormalInputs,
    selected_pairs: Sequence[Mapping],
) -> None:
    event_ids = {
        event_id
        for pair in selected_pairs
        for event_id in (pair["base_event_id"], pair["cf_event_id"])
    }
    if not event_ids:
        raise ValueError("cohort has no extraction events")
    placeholders = ",".join("?" for _ in event_ids)
    connection = sqlite3.connect(
        f"file:{inputs.db_path.resolve()}?mode=ro",
        uri=True,
    )
    try:
        connection.execute("BEGIN")
        existing = {
            row[0]
            for row in connection.execute(
                "SELECT event_id FROM extraction_events "
                f"WHERE event_id IN ({placeholders})",
                tuple(sorted(event_ids)),
            )
        }
        counts = {
            event_id: {"all_rows": 0, "linked_rows": 0}
            for event_id in event_ids
        }
        for event_id, all_rows, linked_rows in connection.execute(
            "SELECT event_id, COUNT(*), "
            "SUM(CASE WHEN subject_entity_id IS NOT NULL "
            "AND relation IS NOT NULL "
            "AND object_entity_id IS NOT NULL THEN 1 ELSE 0 END) "
            "FROM extracted_edges "
            f"WHERE event_id IN ({placeholders}) GROUP BY event_id",
            tuple(sorted(event_ids)),
        ):
            counts[event_id] = {
                "all_rows": int(all_rows),
                "linked_rows": int(linked_rows or 0),
            }
    finally:
        connection.close()

    missing = sorted(event_ids - existing)
    if missing:
        raise ValueError(
            "selected extraction event is missing: " + ", ".join(missing)
        )
    for pair in selected_pairs:
        for side in ("base", "cf"):
            event_id = pair[f"{side}_event_id"]
            actual = counts[event_id]
            actual["deduplicated_typed_edges"] = len(
                inputs.edges_by_event[event_id]
            )
            actual["excluded_unlinked_rows"] = (
                actual["all_rows"] - actual["linked_rows"]
            )
            expected = pair[f"{side}_edge_counts"]
            if actual != expected:
                raise ValueError(
                    f"{pair['run_id']}/{side}: edge inventory mismatch"
                )


def load_kuzu_cohort_context(
    manifest_path: str | Path,
    source_run: str,
    *,
    repo_root: str | Path,
    expected_manifest_sha256: str,
) -> KuzuCohortContext:
    """Load and revalidate one fixed RQ10 cohort without resampling."""
    repo_root = Path(repo_root).resolve()
    manifest_path = Path(manifest_path).resolve()
    manifest_sha = _require_sha(
        manifest_path,
        expected_manifest_sha256,
        "cohort manifest",
    )
    manifest = _read_json(manifest_path, "cohort manifest")
    if manifest.get("artifact_type") != COHORT_ARTIFACT_TYPE:
        raise ValueError("cohort manifest artifact type mismatch")
    if manifest.get("artifact_version") != COHORT_ARTIFACT_VERSION:
        raise ValueError("cohort manifest artifact version mismatch")
    _validate_manifest_implementation(manifest, repo_root)

    cohort_key = f"rq10_n300/{source_run}"
    try:
        entry = manifest["cohorts"]["rq10_n300"][source_run]
    except (KeyError, TypeError) as exc:
        raise ValueError(f"cohort is not registered: {cohort_key}") from exc
    selection = entry.get("selection", {})
    selected = _validate_selection_shape(selection)
    source = entry.get("source", {})
    if source.get("source_run") != source_run:
        raise ValueError("cohort source run mismatch")

    deployment_path = _resolve_recorded_path(
        source["deployment_artifact"]["path"],
        repo_root,
    )
    downstream_path = _resolve_recorded_path(
        source["downstream_artifact"]["path"],
        repo_root,
    )
    db_path = _resolve_recorded_path(
        source["source_database"]["path"],
        repo_root,
    )
    source_hashes = {
        "manifest": manifest_sha,
        "deployment": _require_sha(
            deployment_path,
            source["deployment_artifact"]["sha256"],
            "deployment artifact",
        ),
        "downstream": _require_sha(
            downstream_path,
            source["downstream_artifact"]["sha256"],
            "downstream artifact",
        ),
    }
    deployment = _read_json(deployment_path, "deployment artifact")
    downstream = _read_json(downstream_path, "downstream artifact")
    _require_artifact_identity(
        deployment,
        artifact_type=ARTIFACT_TYPE,
        artifact_version=ARTIFACT_VERSION,
        source_run=source_run,
        label="deployment",
    )
    _require_artifact_identity(
        downstream,
        artifact_type=DOWNSTREAM_ARTIFACT_TYPE,
        artifact_version=DOWNSTREAM_ARTIFACT_VERSION,
        source_run=source_run,
        label="downstream",
    )
    if downstream["deployment_artifact"]["sha256"] != source_hashes[
        "deployment"
    ]:
        raise ValueError("downstream/deployment SHA link mismatch")
    actual_db_sha = _require_sha(
        db_path,
        source["source_database"]["sha256"],
        "source database",
    )
    if deployment["source_database"]["sha256"] != actual_db_sha:
        raise ValueError("deployment/source DB SHA link mismatch")
    if downstream["source_database"]["sha256"] != actual_db_sha:
        raise ValueError("downstream/source DB SHA link mismatch")

    deployment_ids = [pair["run_id"] for pair in deployment["per_pair"]]
    downstream_ids = [pair["run_id"] for pair in downstream["per_pair"]]
    if len(deployment_ids) != len(set(deployment_ids)):
        raise ValueError("deployment artifact contains duplicate run IDs")
    if len(downstream_ids) != len(set(downstream_ids)):
        raise ValueError("downstream artifact contains duplicate run IDs")
    if len(deployment_ids) != source.get("n_authoritative_pairs"):
        raise ValueError("authoritative population count mismatch")
    if len(downstream_ids) != source.get("n_registered_eligible_pairs"):
        raise ValueError("registered eligible population count mismatch")

    anchor = entry.get("selection_anchor")
    if not isinstance(anchor, dict):
        raise ValueError("cohort selection anchor is missing")
    if anchor.get("n_pairs") != selection["target_size"]:
        raise ValueError("cohort selection anchor count mismatch")
    if anchor.get("run_ids_sha256") != selection.get(
        "anchor_run_ids_sha256"
    ):
        raise ValueError("selection anchor digest mismatch")

    inputs = load_registered_inputs(db_path, deployment_path)
    selected_pairs = []
    downstream_by_run_id = {
        record["run_id"]: record for record in downstream["per_pair"]
    }
    for run_id in selected:
        pair = inputs.pairs_by_run_id.get(run_id)
        if pair is None:
            raise ValueError(f"selected run ID is not authoritative: {run_id}")
        if run_id not in downstream_by_run_id:
            raise ValueError(f"selected run ID is not eligible: {run_id}")
        queries = inputs.queries_by_catalog[pair["query_catalog_id"]]
        if not queries:
            raise ValueError(f"selected run ID has an empty catalog: {run_id}")
        selected_pairs.append(pair)
    _validate_event_and_edge_inventory(inputs, selected_pairs)
    db_after_inventory = database_fingerprint(db_path)
    require_stable_quiescent_snapshot(
        inputs.source_before,
        db_after_inventory,
    )
    inputs.source_after = db_after_inventory

    source_hashes["database"] = actual_db_sha
    return KuzuCohortContext(
        repo_root=repo_root,
        manifest_path=manifest_path,
        manifest_sha256=manifest_sha,
        manifest=manifest,
        source_run=source_run,
        cohort_key=cohort_key,
        cohort_entry=entry,
        selected_run_ids=selected,
        inputs=inputs,
        downstream_path=downstream_path,
        downstream_artifact=downstream,
        downstream_by_run_id=downstream_by_run_id,
        source_hashes_before=source_hashes,
    )


def _answer_evidence(
    base_answers: set,
    cf_answers: set,
) -> dict:
    answer_jaccard = jaccard(base_answers, cf_answers)
    return {
        "base_answer_count": len(base_answers),
        "base_answer_sha256": _set_digest(base_answers),
        "cf_answer_count": len(cf_answers),
        "cf_answer_sha256": _set_digest(cf_answers),
        "answer_jaccard": answer_jaccard,
        "query_drift": 1.0 - answer_jaccard,
        "answer_state": _answer_state(base_answers, cf_answers),
    }


def _evaluate_pair_with_kuzu(
    context: KuzuCohortContext,
    pair: dict,
    graph_factory: Callable = KuzuGraph,
) -> dict:
    evidence_by_query: dict[str, dict[str, set]] = {}

    def executor(graph, side: str):
        def execute(query):
            answers = graph.execute(query)
            query_id = _query_identifier(query)
            evidence_by_query.setdefault(query_id, {})[side] = answers
            return answers

        return execute

    base_edges = context.inputs.edges_by_event[pair["base_event_id"]]
    cf_edges = context.inputs.edges_by_event[pair["cf_event_id"]]
    with graph_factory(base_edges) as base_graph, graph_factory(
        cf_edges
    ) as cf_graph:
        record = evaluate_utility_pair(
            context.inputs,
            pair,
            base_executor=executor(base_graph, "base"),
            cf_executor=executor(cf_graph, "cf"),
        )
    if record is None:
        raise ValueError(f"{pair['run_id']}: selected catalog is empty")

    for query_record in record["per_query"]:
        query_id = query_record["query_id"]
        executed = evidence_by_query.get(query_id, {})
        if set(executed) != {"base", "cf"}:
            raise ValueError(
                f"{pair['run_id']}/{query_id}: incomplete Kuzu execution"
            )
        query_record["kuzu_answers"] = _answer_evidence(
            executed["base"],
            executed["cf"],
        )
    compact = copy.deepcopy(record)
    compact.pop("per_query")
    expected = context.downstream_by_run_id[pair["run_id"]]
    if compact != expected:
        raise ValueError(
            f"{pair['run_id']}: Kuzu aggregate differs from downstream"
        )
    return record


def _validate_sources_unchanged(context: KuzuCohortContext) -> dict:
    current = {
        "manifest": sha256_file(context.manifest_path),
        "deployment": sha256_file(
            context.inputs.deployment_artifact_path
        ),
        "downstream": sha256_file(context.downstream_path),
        "database": sha256_file(context.inputs.db_path),
    }
    if current != context.source_hashes_before:
        raise RuntimeError("registered source files changed during Kuzu execution")
    db_after = database_fingerprint(context.inputs.db_path)
    require_stable_quiescent_snapshot(
        context.inputs.source_before,
        db_after,
    )
    _validate_manifest_implementation(
        context.manifest,
        context.repo_root,
    )
    return db_after


def write_json_atomic(
    path: Path,
    artifact: dict,
    *,
    overwrite: bool,
) -> None:
    """Durably publish a complete artifact without leaving partial output."""
    if path.exists() and not overwrite:
        raise FileExistsError(
            f"{path} exists; choose another directory or pass --overwrite"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    if temporary.exists():
        raise FileExistsError(f"temporary output already exists: {temporary}")
    try:
        with temporary.open("x", encoding="utf-8") as handle:
            json.dump(
                artifact,
                handle,
                indent=2,
                sort_keys=True,
                ensure_ascii=False,
            )
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        if path.exists() and not overwrite:
            raise FileExistsError(f"output appeared during run: {path}")
        os.replace(temporary, path)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if temporary.exists():
            temporary.unlink()


def _validate_execution_envelope(
    context: KuzuCohortContext,
    *,
    mode: str,
    run_ids: Sequence[str],
    artifact_type: str,
    status: str,
    complete: bool,
    execution_backend: str,
    enforce_registered_query_count: bool,
    graph_factory: Callable,
) -> None:
    """Prevent injected executors from claiming official provenance."""
    run_ids = list(run_ids)
    if artifact_type == KUZU_COHORT_ARTIFACT_TYPE:
        valid = (
            context.manifest_sha256
            == REGISTERED_COHORT_MANIFEST_SHA256
            and graph_factory is KuzuGraph
            and mode == "complete"
            and run_ids == context.selected_run_ids
            and status == "pass"
            and complete is True
            and execution_backend == "kuzu_cypher"
            and enforce_registered_query_count is True
        )
        if not valid:
            raise ValueError("invalid official complete execution envelope")
        return
    if artifact_type == KUZU_COHORT_SMOKE_ARTIFACT_TYPE:
        selected_positions = {
            run_id: index
            for index, run_id in enumerate(context.selected_run_ids)
        }
        valid_subset = (
            bool(run_ids)
            and len(run_ids) == len(set(run_ids))
            and all(run_id in selected_positions for run_id in run_ids)
            and run_ids
            == sorted(
                run_ids,
                key=lambda run_id: selected_positions[run_id],
            )
        )
        valid = (
            context.manifest_sha256
            == REGISTERED_COHORT_MANIFEST_SHA256
            and graph_factory is KuzuGraph
            and mode == "smoke"
            and valid_subset
            and status == "smoke_pass"
            and complete is False
            and execution_backend == "kuzu_cypher"
            and enforce_registered_query_count is False
        )
        if not valid:
            raise ValueError("invalid official smoke execution envelope")
        return
    if artifact_type == KUZU_COHORT_TEST_ARTIFACT_TYPE:
        valid = (
            mode == "test"
            and status == "test_pass"
            and complete is False
            and execution_backend == "test_injected_executor"
            and enforce_registered_query_count is False
        )
        if not valid:
            raise ValueError("invalid test execution envelope")
        return
    raise ValueError(f"unsupported execution artifact type: {artifact_type}")


def _run_kuzu_cohort(
    context: KuzuCohortContext,
    *,
    mode: str,
    run_ids: Sequence[str],
    artifact_type: str,
    status: str,
    complete: bool,
    execution_backend: str,
    enforce_registered_query_count: bool,
    graph_factory: Callable,
    progress: Callable[[int, int, str], None] | None = None,
) -> dict:
    """Internal execution core; public provenance policy is enforced above."""
    _validate_execution_envelope(
        context,
        mode=mode,
        run_ids=run_ids,
        artifact_type=artifact_type,
        status=status,
        complete=complete,
        execution_backend=execution_backend,
        enforce_registered_query_count=enforce_registered_query_count,
        graph_factory=graph_factory,
    )
    actual_kuzu_version = kuzu_version()
    if actual_kuzu_version != REGISTERED_KUZU_VERSION:
        raise RuntimeError(
            f"Kuzu version mismatch: {actual_kuzu_version} "
            f"!= {REGISTERED_KUZU_VERSION}"
        )
    run_ids = list(run_ids)

    expected_queries = sum(
        len(
            context.inputs.queries_by_catalog[
                context.inputs.pairs_by_run_id[run_id]["query_catalog_id"]
            ]
        )
        for run_id in run_ids
    )
    if enforce_registered_query_count:
        registered = REGISTERED_QUERY_COUNTS.get(context.source_run)
        if registered is None or expected_queries != registered:
            raise ValueError("registered query count mismatch")

    records = []
    total = len(run_ids)
    for index, run_id in enumerate(run_ids, start=1):
        pair = context.inputs.pairs_by_run_id[run_id]
        records.append(
            _evaluate_pair_with_kuzu(
                context,
                pair,
                graph_factory=graph_factory,
            )
        )
        if progress is not None:
            progress(index, total, run_id)
    db_after = _validate_sources_unchanged(context)
    n_queries = sum(record["n_queries"] for record in records)
    if n_queries != expected_queries:
        raise AssertionError("executed query count differs from catalog")
    if [record["run_id"] for record in records] != run_ids:
        raise AssertionError("executed pair order differs from cohort order")

    selection = context.cohort_entry["selection"]
    return {
        "artifact_type": artifact_type,
        "artifact_version": KUZU_COHORT_ARTIFACT_VERSION,
        "status": status,
        "complete": complete,
        "source_run": context.source_run,
        "cohort": {
            "key": context.cohort_key,
            "manifest": {
                "path": str(context.manifest_path),
                "sha256": context.manifest_sha256,
            },
            "registered_target_size": selection["target_size"],
            "registered_selected_run_ids": context.selected_run_ids,
            "registered_selected_run_ids_sha256": selection[
                "selected_run_ids_sha256"
            ],
            "executed_run_ids": run_ids,
            "executed_run_ids_sha256": canonical_digest(run_ids),
        },
        "sources": {
            "database": {
                "path": str(context.inputs.db_path),
                "sha256": context.source_hashes_before["database"],
                "fingerprint_before": context.inputs.source_before,
                "fingerprint_after": db_after,
            },
            "deployment_artifact": {
                "path": str(context.inputs.deployment_artifact_path),
                "sha256": context.source_hashes_before["deployment"],
            },
            "downstream_artifact": {
                "path": str(context.downstream_path),
                "sha256": context.source_hashes_before["downstream"],
            },
        },
        "protocol": {
            "execution_backend": execution_backend,
            "execution_mode": mode,
            "kuzu_version_required": REGISTERED_KUZU_VERSION,
            "query_catalog": "registered schema-eligible deployment Q1-Q4",
            "selection": (
                "exact manifest order; no resampling, replacement, skip, "
                "or offline fallback"
            ),
            "validation": (
                "per-query Kuzu answer count/hash/Jaccard/drift/state and "
                "exact pair aggregate agreement with downstream artifact"
            ),
        },
        "execution": {
            "n_pairs_expected": len(run_ids),
            "n_pairs_completed": len(records),
            "n_graphs_materialized": 2 * len(records),
            "n_query_instances_checked": n_queries,
            "n_answer_sets_checked": 2 * n_queries,
            "n_mismatches": 0,
        },
        "runtime": {
            **runtime_versions(),
            "kuzu": actual_kuzu_version,
        },
        "per_pair": records,
    }


def _validate_explicit_subset(
    context: KuzuCohortContext,
    run_ids: Sequence[str],
    *,
    label: str,
) -> list[str]:
    run_ids = list(run_ids)
    if not run_ids:
        raise ValueError(f"{label} requires explicit run IDs")
    if len(run_ids) != len(set(run_ids)):
        raise ValueError(f"{label} run IDs contain duplicates")
    selected_positions = {
        run_id: index
        for index, run_id in enumerate(context.selected_run_ids)
    }
    if any(run_id not in selected_positions for run_id in run_ids):
        raise ValueError(f"{label} run ID is outside the registered cohort")
    if run_ids != sorted(
        run_ids,
        key=lambda run_id: selected_positions[run_id],
    ):
        raise ValueError(f"{label} run IDs do not preserve manifest order")
    return run_ids


def run_kuzu_cohort(
    context: KuzuCohortContext,
    *,
    mode: str = "complete",
    smoke_run_ids: Sequence[str] | None = None,
    progress: Callable[[int, int, str], None] | None = None,
) -> dict:
    """Generate an official artifact using the registered manifest and Kuzu."""
    if context.manifest_sha256 != REGISTERED_COHORT_MANIFEST_SHA256:
        raise ValueError(
            "official Kuzu execution requires the registered manifest SHA"
        )
    if mode == "complete":
        if smoke_run_ids is not None:
            raise ValueError("complete mode does not accept a run-ID subset")
        run_ids = list(context.selected_run_ids)
        artifact_type = KUZU_COHORT_ARTIFACT_TYPE
        status = "pass"
        complete = True
        enforce_query_count = True
    elif mode == "smoke":
        run_ids = _validate_explicit_subset(
            context,
            smoke_run_ids or (),
            label="smoke",
        )
        artifact_type = KUZU_COHORT_SMOKE_ARTIFACT_TYPE
        status = "smoke_pass"
        complete = False
        enforce_query_count = False
    else:
        raise ValueError(f"unsupported execution mode: {mode}")
    return _run_kuzu_cohort(
        context,
        mode=mode,
        run_ids=run_ids,
        artifact_type=artifact_type,
        status=status,
        complete=complete,
        execution_backend="kuzu_cypher",
        enforce_registered_query_count=enforce_query_count,
        graph_factory=KuzuGraph,
        progress=progress,
    )


def _run_kuzu_cohort_for_test(
    context: KuzuCohortContext,
    *,
    run_ids: Sequence[str] | None = None,
    graph_factory: Callable = KuzuGraph,
) -> dict:
    """Exercise fixtures without producing an official provenance artifact."""
    selected = _validate_explicit_subset(
        context,
        run_ids or context.selected_run_ids,
        label="test",
    )
    return _run_kuzu_cohort(
        context,
        mode="test",
        run_ids=selected,
        artifact_type=KUZU_COHORT_TEST_ARTIFACT_TYPE,
        status="test_pass",
        complete=False,
        execution_backend="test_injected_executor",
        enforce_registered_query_count=False,
        graph_factory=graph_factory,
    )
