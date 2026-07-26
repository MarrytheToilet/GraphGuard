"""Gold-grounded downstream metrics for audited deployment Q1--Q4 artifacts."""

from __future__ import annotations

import json
import sqlite3
import statistics
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from graphguard.deployment_runner import (
    ARTIFACT_TYPE,
    FAMILY_TO_QUERY_ID,
    _query_id,
    _set_digest,
    build_catalog,
)
from graphguard.deployment_parity import (
    PARITY_ARTIFACT_TYPE,
    PARITY_ARTIFACT_VERSION,
    select_pairs,
)
from graphguard.qa import execute, f1, jaccard
from graphguard.sqlite_snapshot import (
    database_fingerprint,
    require_quiescent_snapshot,
    require_stable_quiescent_snapshot,
    sha256_file,
)


DOWNSTREAM_ARTIFACT_TYPE = "graphguard.deployment_q1q4_downstream"
DOWNSTREAM_ARTIFACT_VERSION = 1
REGISTERED_KUZU_VERSION = "0.11.3"


@dataclass
class FormalInputs:
    db_path: Path
    deployment_artifact_path: Path
    deployment_artifact: dict
    pairs_by_run_id: dict[str, dict]
    queries_by_catalog: dict[str, list[tuple[str, dict]]]
    edges_by_event: dict[str, set[tuple[str, str, str]]]
    gold_by_document: dict[str, set[tuple[str, str, str]]]
    source_before: dict
    source_after: dict


def _read_only_connection(db_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(
        f"file:{db_path.resolve()}?mode=ro",
        uri=True,
    )
    connection.row_factory = sqlite3.Row
    return connection


def load_formal_inputs(
    db_path: str | Path,
    deployment_artifact_path: str | Path,
) -> FormalInputs:
    """Reconstruct and validate the exact inputs registered by an artifact."""
    db_path = Path(db_path)
    artifact_path = Path(deployment_artifact_path)
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    if artifact.get("artifact_type") != ARTIFACT_TYPE:
        raise ValueError(f"not a deployment artifact: {artifact_path}")

    source_before = database_fingerprint(db_path)
    require_quiescent_snapshot(source_before)
    if (
        source_before["main"]["sha256"]
        != artifact["source_database"]["sha256"]
    ):
        raise ValueError("source database hash differs from deployment artifact")

    required_events = {
        event_id
        for pair in artifact["per_pair"]
        for event_id in (pair["base_event_id"], pair["cf_event_id"])
    }
    edges_by_event: dict[
        str, set[tuple[str, str, str]]
    ] = {event_id: set() for event_id in required_events}
    gold_by_document: dict[
        str, set[tuple[str, str, str]]
    ] = defaultdict(set)
    schema_relations = {}

    connection = _read_only_connection(db_path)
    try:
        connection.execute("BEGIN")
        for row in connection.execute(
            """
            SELECT event_id, subject_entity_id, relation, object_entity_id
            FROM extracted_edges
            WHERE subject_entity_id IS NOT NULL
              AND relation IS NOT NULL
              AND object_entity_id IS NOT NULL
            ORDER BY rowid
            """
        ):
            if row["event_id"] in edges_by_event:
                edges_by_event[row["event_id"]].add(
                    (
                        row["subject_entity_id"],
                        row["relation"],
                        row["object_entity_id"],
                    )
                )
        for row in connection.execute(
            """
            SELECT document_id, head_entity_id, relation_base, tail_entity_id
            FROM gold_edges
            WHERE head_entity_id IS NOT NULL
              AND relation_base IS NOT NULL
              AND tail_entity_id IS NOT NULL
            ORDER BY rowid
            """
        ):
            gold_by_document[row["document_id"]].add(
                (
                    row["head_entity_id"],
                    row["relation_base"],
                    row["tail_entity_id"],
                )
            )
        for row in connection.execute(
            "SELECT schema_id, relation_types_json FROM schemas"
        ):
            schema_relations[row["schema_id"]] = {
                relation["id"]
                for relation in json.loads(row["relation_types_json"])
            }
    finally:
        connection.close()

    source_after = database_fingerprint(db_path)
    require_stable_quiescent_snapshot(source_before, source_after)

    queries_by_catalog = {}
    for catalog_id, recorded in artifact["query_catalogs"].items():
        schema_id = recorded["base_schema_id"]
        if schema_id not in schema_relations:
            raise ValueError(f"missing schema {schema_id}")
        rebuilt, queries = build_catalog(
            recorded["document_id"],
            schema_id,
            gold_by_document.get(recorded["document_id"], set()),
            schema_relations[schema_id],
        )
        if rebuilt != recorded:
            raise ValueError(f"query catalog mismatch: {catalog_id}")
        queries_by_catalog[catalog_id] = queries

    pairs_by_run_id = {}
    for pair in artifact["per_pair"]:
        run_id = pair["run_id"]
        if run_id in pairs_by_run_id:
            raise ValueError(f"duplicate run ID in artifact: {run_id}")
        pairs_by_run_id[run_id] = pair

    return FormalInputs(
        db_path=db_path,
        deployment_artifact_path=artifact_path,
        deployment_artifact=artifact,
        pairs_by_run_id=pairs_by_run_id,
        queries_by_catalog=queries_by_catalog,
        edges_by_event=edges_by_event,
        gold_by_document=dict(gold_by_document),
        source_before=source_before,
        source_after=source_after,
    )


def _extraction_quality(
    predicted: set[tuple[str, str, str]],
    gold: set[tuple[str, str, str]],
) -> tuple[float, float]:
    true_positive = len(predicted & gold)
    recall = true_positive / len(gold) if gold else 0.0
    precision = true_positive / len(predicted) if predicted else 0.0
    return recall, precision


def _query_identifier(query: tuple[str, dict]) -> str:
    family, parameters = query
    return _query_id(
        family,
        {
            key: value
            for key, value in parameters.items()
            if key != "gold"
        },
    )


def _validate_query_inventory(
    pair: dict,
    queries: list[tuple[str, dict]],
) -> dict[str, dict]:
    """Require the formal pair to contain exactly the rebuilt query catalog."""
    expected_families = set(FAMILY_TO_QUERY_ID.values())
    if set(pair["families"]) != expected_families:
        raise ValueError(
            f"{pair['run_id']}: formal family inventory mismatch"
        )
    actual_by_family: dict[str, list[str]] = defaultdict(list)
    for query in queries:
        actual_by_family[FAMILY_TO_QUERY_ID[query[0]]].append(
            _query_identifier(query)
        )

    expected_by_id = {}
    for family_id in FAMILY_TO_QUERY_ID.values():
        if family_id not in pair["families"]:
            raise ValueError(
                f"{pair['run_id']}: missing family {family_id}"
            )
        family = pair["families"][family_id]
        actual_ids = actual_by_family.get(family_id, [])
        actual_eligible = bool(actual_ids)
        if family["eligible"] is not actual_eligible:
            raise ValueError(
                f"{pair['run_id']}/{family_id}: eligibility mismatch"
            )
        if family["n_queries"] != len(actual_ids):
            raise ValueError(
                f"{pair['run_id']}/{family_id}: query count mismatch"
            )
        formal_queries = family["queries"]
        formal_ids = [record["query_id"] for record in formal_queries]
        if len(formal_ids) != len(set(formal_ids)):
            raise ValueError(
                f"{pair['run_id']}/{family_id}: duplicate formal query"
            )
        if set(formal_ids) != set(actual_ids):
            raise ValueError(
                f"{pair['run_id']}/{family_id}: query inventory mismatch"
            )
        expected_by_id.update(
            (record["query_id"], record) for record in formal_queries
        )
    return expected_by_id


def _answer_state(base_answers: set, cf_answers: set) -> str:
    if not base_answers and not cf_answers:
        return "both_empty"
    if base_answers and not cf_answers:
        return "base_only"
    if cf_answers and not base_answers:
        return "cf_only"
    return "both_nonempty"


def evaluate_utility_pair(
    inputs: FormalInputs,
    pair: dict,
    *,
    base_executor: Callable[[tuple[str, dict]], set] | None = None,
    cf_executor: Callable[[tuple[str, dict]], set] | None = None,
) -> dict | None:
    """Evaluate F1 and gold-free answer drift on one registered pair.

    Optional executors let the caller substitute actual Kuzu execution.  Every
    returned answer set is checked against the formal deployment artifact.
    """
    base_edges = inputs.edges_by_event[pair["base_event_id"]]
    cf_edges = inputs.edges_by_event[pair["cf_event_id"]]
    queries = inputs.queries_by_catalog[pair["query_catalog_id"]]
    expected_by_id = _validate_query_inventory(pair, queries)
    if not queries:
        return None

    per_query = []
    for query in queries:
        family = query[0]
        query_id = _query_identifier(query)
        expected = expected_by_id.get(query_id)
        if expected is None:
            raise ValueError(f"{pair['run_id']}: missing query {query_id}")
        base_answers = (
            base_executor(query)
            if base_executor is not None
            else execute(base_edges, query)
        )
        cf_answers = (
            cf_executor(query)
            if cf_executor is not None
            else execute(cf_edges, query)
        )
        if len(base_answers) != expected["base_answer_count"]:
            raise ValueError(
                f"{pair['run_id']}/{query_id}: "
                "base answer count mismatch"
            )
        if len(cf_answers) != expected["cf_answer_count"]:
            raise ValueError(
                f"{pair['run_id']}/{query_id}: "
                "cf answer count mismatch"
            )
        if _set_digest(base_answers) != expected["base_answer_sha256"]:
            raise ValueError(
                f"{pair['run_id']}/{query_id}: base answer hash mismatch"
            )
        if _set_digest(cf_answers) != expected["cf_answer_sha256"]:
            raise ValueError(
                f"{pair['run_id']}/{query_id}: cf answer hash mismatch"
            )
        gold_answers = query[1]["gold"]
        f1_base = f1(base_answers, gold_answers)
        f1_cf = f1(cf_answers, gold_answers)
        answer_jaccard = jaccard(base_answers, cf_answers)
        answer_drift = 1.0 - answer_jaccard
        if abs(answer_jaccard - expected["answer_jaccard"]) > 1e-12:
            raise ValueError(
                f"{pair['run_id']}/{query_id}: "
                "answer Jaccard mismatch"
            )
        if abs(answer_drift - expected["query_drift"]) > 1e-12:
            raise ValueError(
                f"{pair['run_id']}/{query_id}: query drift mismatch"
            )
        answer_state = _answer_state(base_answers, cf_answers)
        if answer_state != expected["answer_state"]:
            raise ValueError(
                f"{pair['run_id']}/{query_id}: answer state mismatch"
            )
        per_query.append(
            {
                "query_id": query_id,
                "family": FAMILY_TO_QUERY_ID[family],
                "f1_base": f1_base,
                "f1_cf": f1_cf,
                "delta_f1_abs": abs(f1_base - f1_cf),
                "delta_f1_signed": f1_base - f1_cf,
                "answer_drift": answer_drift,
                "base_answer_nonempty": bool(base_answers),
                "cf_answer_nonempty": bool(cf_answers),
            }
        )

    by_family: dict[str, list[dict]] = defaultdict(list)
    for query_record in per_query:
        by_family[query_record["family"]].append(query_record)
    family_records = {}
    for query_id in FAMILY_TO_QUERY_ID.values():
        rows = by_family.get(query_id, [])
        if not rows:
            family_records[query_id] = {
                "eligible": False,
                "n_queries": 0,
            }
            continue
        family_records[query_id] = {
            "eligible": True,
            "n_queries": len(rows),
            "mean_delta_f1_abs": statistics.mean(
                row["delta_f1_abs"] for row in rows
            ),
            "mean_delta_f1_signed": statistics.mean(
                row["delta_f1_signed"] for row in rows
            ),
            "mean_answer_drift": statistics.mean(
                row["answer_drift"] for row in rows
            ),
            "max_answer_drift": max(
                row["answer_drift"] for row in rows
            ),
            "has_nonempty_answer": any(
                row["base_answer_nonempty"]
                or row["cf_answer_nonempty"]
                for row in rows
            ),
        }

    gold_graph = inputs.gold_by_document.get(pair["document_id"], set())
    recall_base, precision_base = _extraction_quality(base_edges, gold_graph)
    recall_cf, precision_cf = _extraction_quality(cf_edges, gold_graph)
    return {
        "run_id": pair["run_id"],
        "document_id": pair["document_id"],
        "intervention_id": pair["intervention_id"],
        "cause_family": pair["cause_family"],
        "semantic_class": pair["semantic_class"],
        "operator": pair["operator"],
        "target_type": pair["target_type"],
        "target_id": pair["target_id"],
        "base_event_id": pair["base_event_id"],
        "cf_event_id": pair["cf_event_id"],
        "query_catalog_id": pair["query_catalog_id"],
        "graph_drift": pair["graph_drift"],
        "n_queries": len(per_query),
        "mean_f1_base": statistics.mean(
            row["f1_base"] for row in per_query
        ),
        "mean_f1_cf": statistics.mean(
            row["f1_cf"] for row in per_query
        ),
        "mean_delta_f1_abs": statistics.mean(
            row["delta_f1_abs"] for row in per_query
        ),
        "mean_delta_f1_signed": statistics.mean(
            row["delta_f1_signed"] for row in per_query
        ),
        "max_answer_drift": max(
            row["answer_drift"] for row in per_query
        ),
        "mean_answer_drift": statistics.mean(
            row["answer_drift"] for row in per_query
        ),
        "delta_recall_abs": abs(recall_base - recall_cf),
        "delta_precision_abs": abs(precision_base - precision_cf),
        "families": family_records,
        "per_query": per_query,
    }


def load_kuzu_parity_evidence(
    inputs: FormalInputs,
    parity_artifact_path: str | Path,
    *,
    selection_seed: int = 0,
    selection_min_pairs: int = 20,
    selection_max_pairs: int | None = None,
    expected_kuzu_version: str = REGISTERED_KUZU_VERSION,
) -> dict:
    """Validate and compactly register the formal Kuzu parity evidence."""
    parity_path = Path(parity_artifact_path)
    parity = json.loads(parity_path.read_text(encoding="utf-8"))
    if parity.get("artifact_type") != PARITY_ARTIFACT_TYPE:
        raise ValueError(f"not a Kuzu parity artifact: {parity_path}")
    if parity.get("artifact_version") != PARITY_ARTIFACT_VERSION:
        raise ValueError(f"unsupported Kuzu parity version: {parity_path}")
    if parity.get("kuzu_version") != expected_kuzu_version:
        raise ValueError("Kuzu parity version mismatch")
    if (
        parity.get("status") != "pass"
        or parity.get("n_mismatches") != 0
        or parity.get("mismatches") != []
    ):
        raise ValueError(f"Kuzu parity did not pass: {parity_path}")
    deployment_sha256 = sha256_file(inputs.deployment_artifact_path)
    if (
        parity["deployment_artifact"]["sha256"]
        != deployment_sha256
    ):
        raise ValueError("Kuzu parity references another deployment artifact")
    if (
        parity["source_database"]["sha256"]
        != inputs.source_before["main"]["sha256"]
    ):
        raise ValueError("Kuzu parity references another source database")
    if parity["source_run"] != inputs.deployment_artifact["source_run"]:
        raise ValueError("Kuzu parity source run mismatch")
    selected, expected_selection = select_pairs(
        inputs.deployment_artifact["per_pair"],
        seed=selection_seed,
        min_pairs=selection_min_pairs,
        max_pairs=selection_max_pairs,
    )
    if parity["selection"] != expected_selection:
        raise ValueError("Kuzu parity selection mismatch")
    n_queries = sum(
        len(inputs.queries_by_catalog[pair["query_catalog_id"]])
        for pair in selected
    )
    expected_counts = {
        "n_graph_pairs_materialized": len(selected),
        "n_query_instances_checked": n_queries,
        "n_answer_sets_checked": 2 * n_queries,
    }
    for field, expected in expected_counts.items():
        if parity.get(field) != expected:
            raise ValueError(f"Kuzu parity {field} mismatch")
    return {
        "path": str(parity_path),
        "sha256": sha256_file(parity_path),
        "artifact_type": parity["artifact_type"],
        "artifact_version": parity["artifact_version"],
        "status": parity["status"],
        "kuzu_version": parity["kuzu_version"],
        "n_graph_pairs_materialized": parity[
            "n_graph_pairs_materialized"
        ],
        "n_query_instances_checked": parity[
            "n_query_instances_checked"
        ],
        "n_answer_sets_checked": parity["n_answer_sets_checked"],
        "n_mismatches": parity["n_mismatches"],
        "selection_sha256": parity["selection"]["selection_sha256"],
        "selection_policy": {
            "seed": selection_seed,
            "min_pairs": selection_min_pairs,
            "max_pairs": selection_max_pairs,
        },
    }


def build_downstream_artifact(inputs: FormalInputs) -> dict:
    records = []
    for pair in inputs.deployment_artifact["per_pair"]:
        record = evaluate_utility_pair(inputs, pair)
        if record is not None:
            # Pair/family aggregates are sufficient for every registered
            # downstream analysis. Exact answer hashes remain in the source
            # deployment artifact and are revalidated above.
            record.pop("per_query")
            records.append(record)
    return {
        "artifact_type": DOWNSTREAM_ARTIFACT_TYPE,
        "artifact_version": DOWNSTREAM_ARTIFACT_VERSION,
        "source_run": inputs.deployment_artifact["source_run"],
        "source_database": {
            "path": str(inputs.db_path),
            "sha256": inputs.source_before["main"]["sha256"],
            "fingerprint_before": inputs.source_before,
            "fingerprint_after": inputs.source_after,
        },
        "deployment_artifact": {
            "path": str(inputs.deployment_artifact_path),
            "sha256": sha256_file(inputs.deployment_artifact_path),
        },
        "protocol": {
            "execution_backend": "offline_set_semantics",
            "execution_validation": (
                "exact answer count, hash, Jaccard, state, and query-drift "
                "agreement with the formal deployment artifact"
            ),
            "query_catalog": (
                "formal schema-eligible deployment Q1-Q4 artifact"
            ),
            "query_utility": (
                "F1 against complete schema-eligible gold answer sets"
            ),
            "harm_label_directional": (
                "mean(f1_base - f1_cf) > 0.05"
            ),
            "divergence_label_absolute": (
                "mean(abs(f1_base - f1_cf)) > 0.05"
            ),
            "decision_signals": (
                "canonical graph drift and max exact answer-set drift"
            ),
        },
        "population": {
            "n_authoritative_pairs": len(
                inputs.deployment_artifact["per_pair"]
            ),
            "n_pairs_with_nonempty_workload": len(records),
            "n_pairs_without_workload": (
                len(inputs.deployment_artifact["per_pair"]) - len(records)
            ),
            "n_query_evaluations": sum(
                record["n_queries"] for record in records
            ),
        },
        "per_pair": records,
    }
