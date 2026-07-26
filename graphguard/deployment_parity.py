"""Deterministic exact-answer parity checks for offline and Kuzu execution."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Mapping, Sequence

from graphguard.deployment_runner import (
    ARTIFACT_TYPE,
    FAMILY_TO_QUERY_ID,
    _set_digest,
)
from graphguard.kuzu_executor import KuzuGraph, kuzu_version
from graphguard.qa import execute
from graphguard.sqlite_snapshot import (
    database_fingerprint,
    require_quiescent_snapshot,
    require_stable_quiescent_snapshot,
    runtime_versions,
    sha256_file,
)


PARITY_ARTIFACT_TYPE = "graphguard.deployment_q1q4_kuzu_parity"
PARITY_ARTIFACT_VERSION = 1
QUERY_ID_TO_FAMILY = {
    query_id: family for family, query_id in FAMILY_TO_QUERY_ID.items()
}


def _selection_rank(seed: int, run_id: str) -> str:
    return hashlib.sha256(f"{seed}:{run_id}".encode("utf-8")).hexdigest()


def _coverage_tokens(record: Mapping) -> set[str]:
    tokens = {
        f"cause_family:{record['cause_family']}",
        f"semantic_class:{record['semantic_class']}",
        f"operator:{record['operator']}",
    }
    if record["base_edge_counts"]["deduplicated_typed_edges"] == 0:
        tokens.add("graph_state:empty_base")
    if record["cf_edge_counts"]["deduplicated_typed_edges"] == 0:
        tokens.add("graph_state:empty_cf")
    if record.get("target_type") == "schema":
        target_id = record.get("target_id", "unknown")
        variant = (
            target_id.split(":", 1)[0]
            if ":" in target_id
            else target_id
        )
        tokens.add(f"schema_variant:{variant}")
    for query_id, family in record["families"].items():
        if not family["eligible"]:
            continue
        tokens.add(f"query_family:{query_id}")
        for state, count in family["answer_state_counts"].items():
            if count:
                tokens.add(f"answer_state:{query_id}:{state}")
    return tokens


def select_pairs(
    records: Sequence[Mapping],
    *,
    seed: int,
    min_pairs: int,
    max_pairs: int | None = None,
) -> tuple[list[Mapping], dict]:
    """Greedily cover all observed strata, then fill deterministically."""
    if min_pairs <= 0:
        raise ValueError("min_pairs must be positive")
    if max_pairs is not None and max_pairs <= 0:
        raise ValueError("max_pairs must be positive when provided")
    if max_pairs is not None and min_pairs > max_pairs:
        raise ValueError("min_pairs cannot exceed max_pairs")
    candidates = [
        record
        for record in records
        if any(
            family["eligible"] for family in record["families"].values()
        )
    ]
    ordered = sorted(
        candidates,
        key=lambda record: (
            _selection_rank(seed, record["run_id"]),
            record["run_id"],
        ),
    )
    if len(ordered) < min_pairs:
        raise ValueError(
            f"only {len(ordered)} eligible pairs, fewer than {min_pairs=}"
        )
    token_by_run = {
        record["run_id"]: _coverage_tokens(record) for record in ordered
    }
    required = set().union(*token_by_run.values()) if ordered else set()
    uncovered = set(required)
    selected = []
    remaining = list(ordered)
    while uncovered:
        best = max(
            remaining,
            key=lambda record: (
                len(token_by_run[record["run_id"]] & uncovered),
                -ordered.index(record),
            ),
        )
        gain = token_by_run[best["run_id"]] & uncovered
        if not gain:
            raise ValueError(f"uncovered parity strata: {sorted(uncovered)}")
        if max_pairs is not None and len(selected) >= max_pairs:
            raise ValueError(
                f"{max_pairs=} cannot cover all observed parity strata"
            )
        selected.append(best)
        remaining.remove(best)
        uncovered -= gain

    selected_ids = {record["run_id"] for record in selected}
    for record in ordered:
        if len(selected) >= min_pairs:
            break
        if record["run_id"] not in selected_ids:
            if max_pairs is not None and len(selected) >= max_pairs:
                raise ValueError(f"cannot satisfy {min_pairs=} within {max_pairs=}")
            selected.append(record)
            selected_ids.add(record["run_id"])
    selected.sort(key=lambda record: record["run_id"])
    selection_payload = "\n".join(
        record["run_id"] for record in selected
    ).encode("utf-8")
    return selected, {
        "method": (
            "deterministic greedy coverage of observed query family, cause "
            "family, semantic class, operator, answer-state, and empty-graph "
            "strata; deterministic fill to min_pairs"
        ),
        "seed": seed,
        "min_pairs": min_pairs,
        "max_pairs": max_pairs,
        "n_candidate_pairs": len(candidates),
        "n_selected_pairs": len(selected),
        "required_coverage_tokens": sorted(required),
        "covered_tokens": sorted(
            set().union(
                *(token_by_run[record["run_id"]] for record in selected)
            )
        ),
        "selected_run_ids": [record["run_id"] for record in selected],
        "selection_sha256": hashlib.sha256(selection_payload).hexdigest(),
    }


def _artifact_queries(artifact: Mapping) -> dict[str, list[tuple[str, dict]]]:
    queries_by_catalog = {}
    for catalog_id, catalog in artifact["query_catalogs"].items():
        queries = []
        for entry in catalog["queries"]:
            family = QUERY_ID_TO_FAMILY[entry["family"]]
            queries.append((family, dict(entry["parameters"])))
        queries_by_catalog[catalog_id] = queries
    return queries_by_catalog


def validate_parity(
    db_path: str | Path,
    deployment_artifact_path: str | Path,
    *,
    seed: int = 0,
    min_pairs: int = 20,
    max_pairs: int | None = None,
) -> dict:
    """Compare exact answer sets on a deterministic real-data sample."""
    db_path = Path(db_path)
    artifact_path = Path(deployment_artifact_path)
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    if artifact.get("artifact_type") != ARTIFACT_TYPE:
        raise ValueError(
            f"not a deployment Q1-Q4 artifact: {artifact_path}"
        )
    source_before = database_fingerprint(db_path)
    require_quiescent_snapshot(source_before)
    expected_db_hash = artifact["source_database"]["sha256"]
    actual_db_hash = source_before["main"]["sha256"]
    if actual_db_hash != expected_db_hash:
        raise ValueError(
            f"source DB hash mismatch: {actual_db_hash} != {expected_db_hash}"
        )

    selected, selection = select_pairs(
        artifact["per_pair"],
        seed=seed,
        min_pairs=min_pairs,
        max_pairs=max_pairs,
    )
    required_events = {
        event_id
        for record in selected
        for event_id in (record["base_event_id"], record["cf_event_id"])
    }
    edges_by_event = {event_id: set() for event_id in required_events}
    connection = sqlite3.connect(
        f"file:{db_path.resolve()}?mode=ro",
        uri=True,
    )
    connection.row_factory = sqlite3.Row
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
    finally:
        connection.close()

    queries_by_catalog = _artifact_queries(artifact)
    mismatches = []
    n_query_instances = 0
    n_answer_sets = 0
    for record in selected:
        queries = queries_by_catalog[record["query_catalog_id"]]
        expected_by_id = {
            query_record["query_id"]: query_record
            for family in record["families"].values()
            for query_record in family["queries"]
        }
        base_edges = edges_by_event[record["base_event_id"]]
        cf_edges = edges_by_event[record["cf_event_id"]]
        with KuzuGraph(base_edges) as base_graph, KuzuGraph(
            cf_edges
        ) as cf_graph:
            for query in queries:
                family = query[0]
                parameters = query[1]
                query_payload = json.dumps(
                    {
                        "family": FAMILY_TO_QUERY_ID[family],
                        "parameters": parameters,
                    },
                    ensure_ascii=False,
                    separators=(",", ":"),
                    sort_keys=True,
                ).encode("utf-8")
                query_id = hashlib.sha256(query_payload).hexdigest()
                expected_record = expected_by_id[query_id]
                n_query_instances += 1
                for side, edges, graph in (
                    ("base", base_edges, base_graph),
                    ("cf", cf_edges, cf_graph),
                ):
                    offline_answers = execute(edges, query)
                    kuzu_answers = graph.execute(query)
                    n_answer_sets += 1
                    artifact_hash = expected_record[
                        f"{side}_answer_sha256"
                    ]
                    offline_hash = _set_digest(offline_answers)
                    kuzu_hash = _set_digest(kuzu_answers)
                    if (
                        offline_answers != kuzu_answers
                        or offline_hash != artifact_hash
                    ):
                        mismatches.append(
                            {
                                "run_id": record["run_id"],
                                "query_id": query_id,
                                "side": side,
                                "offline_answer_sha256": offline_hash,
                                "kuzu_answer_sha256": kuzu_hash,
                                "artifact_answer_sha256": artifact_hash,
                                "offline_answer_count": len(offline_answers),
                                "kuzu_answer_count": len(kuzu_answers),
                            }
                        )

    source_after = database_fingerprint(db_path)
    require_stable_quiescent_snapshot(source_before, source_after)
    return {
        "artifact_type": PARITY_ARTIFACT_TYPE,
        "artifact_version": PARITY_ARTIFACT_VERSION,
        "source_run": artifact["source_run"],
        "source_database": {
            "path": str(db_path),
            "sha256": actual_db_hash,
            "size_bytes": source_before["main"]["size_bytes"],
            "fingerprint_before": source_before,
            "fingerprint_after": source_after,
        },
        "deployment_artifact": {
            "path": str(artifact_path),
            "sha256": sha256_file(artifact_path),
        },
        "kuzu_version": kuzu_version(),
        "runtime": runtime_versions(),
        "selection": selection,
        "n_graph_pairs_materialized": len(selected),
        "n_query_instances_checked": n_query_instances,
        "n_answer_sets_checked": n_answer_sets,
        "n_mismatches": len(mismatches),
        "mismatches": mismatches,
        "status": "pass" if not mismatches else "fail",
    }
