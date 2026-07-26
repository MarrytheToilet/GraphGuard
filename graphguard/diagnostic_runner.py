"""Full-run evaluation for the graph-wide diagnostic query workload.

This runner consumes already-materialized base/counterfactual extraction events.
It never calls an LLM and never mutates a run database.
"""

from __future__ import annotations

import json
import random
import sqlite3
import statistics
from collections import defaultdict
from dataclasses import asdict
from pathlib import Path
from typing import Iterable, Mapping, Sequence

from graphguard.contracts import metrics as M
from graphguard.diagnostic_queries import (
    answer_jaccard,
    execute_diagnostic,
)
from graphguard.query_catalog import DIAGNOSTIC_QUERIES


ARTIFACT_TYPE = "graphguard.diagnostic_amplification"
ARTIFACT_VERSION = 2
AMP_EPS = 0.05


def _row_value(row, key: str):
    return row[key]


def validate_authoritative_pairs(
    pairs: Sequence,
    event_documents: Mapping[str, str],
    witnesses: Mapping[str, Sequence[tuple[str, str | None]]],
) -> dict:
    """Validate explicit pair endpoints and matched-edge witnesses.

    Each witness records a non-null ``matched_edge_id`` and the event that owns
    that edge. Pairs without a witness are valid: empty or all-new
    counterfactual graphs can have no matched edge. Every present witness must
    exist and belong to ``cf_event_id``.
    """
    run_ids: set[str] = set()
    witnessed = 0
    for pair in pairs:
        run_id = _row_value(pair, "run_id")
        document_id = _row_value(pair, "document_id")
        base_event_id = _row_value(pair, "base_event_id")
        cf_event_id = _row_value(pair, "cf_event_id")
        if run_id in run_ids:
            raise ValueError(f"duplicate run_id: {run_id}")
        run_ids.add(run_id)
        if not base_event_id or base_event_id not in event_documents:
            raise ValueError(
                f"{run_id}: missing base extraction event {base_event_id!r}"
            )
        if not cf_event_id or cf_event_id not in event_documents:
            raise ValueError(
                f"{run_id}: missing counterfactual event {cf_event_id!r}"
            )
        if base_event_id == cf_event_id:
            raise ValueError(f"{run_id}: base and counterfactual endpoints match")
        if event_documents[base_event_id] != document_id:
            raise ValueError(
                f"{run_id}: base event {base_event_id!r} belongs to document "
                f"{event_documents[base_event_id]!r}, not {document_id!r}"
            )
        if event_documents[cf_event_id] != document_id:
            raise ValueError(
                f"{run_id}: counterfactual event {cf_event_id!r} belongs to "
                f"document {event_documents[cf_event_id]!r}, not "
                f"{document_id!r}"
            )
        run_witnesses = witnesses.get(run_id, ())
        if run_witnesses:
            witnessed += 1
        for matched_edge_id, witness_event_id in run_witnesses:
            if witness_event_id is None:
                raise ValueError(
                    f"{run_id}: matched-edge witness {matched_edge_id!r} "
                    "does not exist"
                )
            if witness_event_id != cf_event_id:
                raise ValueError(
                    f"{run_id}: cf_event_id {cf_event_id!r} disagrees with "
                    f"matched-edge witness {matched_edge_id!r} from event "
                    f"{witness_event_id!r}"
                )
    return {
        "n_pairs": len(pairs),
        "n_unique_run_ids": len(run_ids),
        "n_pairs_with_matched_edge_witness": witnessed,
        "n_pairs_without_matched_edge_witness": len(pairs) - witnessed,
        "witness_mismatches": 0,
        "missing_event_ids": 0,
        "duplicate_run_ids": 0,
    }


def cluster_bootstrap_mean(
    observations: Iterable[tuple[str, float]],
    *,
    n_bootstrap: int,
    seed: int,
    alpha: float = 0.05,
) -> dict:
    """Document-cluster bootstrap for a pair-weighted population mean."""
    values_by_document: dict[str, list[float]] = defaultdict(list)
    for document_id, value in observations:
        values_by_document[document_id].append(float(value))
    documents = sorted(values_by_document)
    values = [
        value
        for document_id in documents
        for value in values_by_document[document_id]
    ]
    if not values:
        raise ValueError("cannot bootstrap an empty observation set")
    if n_bootstrap <= 0:
        raise ValueError("n_bootstrap must be positive")
    if not 0.0 < alpha < 1.0:
        raise ValueError("alpha must be in (0, 1)")

    rng = random.Random(seed)
    bootstrap_means = []
    for _ in range(n_bootstrap):
        sampled_values = [
            value
            for _ in documents
            for value in values_by_document[
                documents[rng.randrange(len(documents))]
            ]
        ]
        bootstrap_means.append(statistics.mean(sampled_values))
    bootstrap_means.sort()
    low_index = min(
        n_bootstrap - 1,
        int(n_bootstrap * alpha / 2),
    )
    high_index = min(
        n_bootstrap - 1,
        int(n_bootstrap * (1 - alpha / 2)),
    )
    return {
        "n": len(values),
        "n_documents": len(documents),
        "mean": statistics.mean(values),
        "ci_low": bootstrap_means[low_index],
        "ci_high": bootstrap_means[high_index],
        "alpha": alpha,
        "n_bootstrap": n_bootstrap,
        "seed": seed,
    }


def evaluate_pair(
    pair,
    base_edges: Sequence,
    cf_edges: Sequence,
    *,
    base_relation_ids: set[str] | None,
    amp_eps: float = AMP_EPS,
) -> dict:
    """Evaluate every diagnostic query on one authoritative event pair."""
    if amp_eps <= 0:
        raise ValueError("amp_eps must be positive")

    base_triples, cf_triples = M.paired_triples(
        base_edges,
        cf_edges,
        base_relation_ids=base_relation_ids,
    )
    base_triples = frozenset(base_triples)
    cf_triples = frozenset(cf_triples)
    graph_similarity = M.edge_jaccard(
        base_edges,
        cf_edges,
        base_relation_ids=base_relation_ids,
    )
    graph_drift = 1.0 - graph_similarity

    query_results = {}
    for specification in DIAGNOSTIC_QUERIES:
        base_answers = execute_diagnostic(
            specification.canonical_id, base_triples
        )
        cf_answers = execute_diagnostic(
            specification.canonical_id, cf_triples
        )
        if specification.canonical_id == "diagnostic.edge_identity":
            answer_similarity = graph_similarity
            answer_metric = "canonicalized_edge_jaccard"
        else:
            answer_similarity = answer_jaccard(base_answers, cf_answers)
            answer_metric = "exact_answer_set_jaccard"
        query_drift = 1.0 - answer_similarity
        query_results[specification.canonical_id] = {
            "n_base_answers": len(base_answers),
            "n_cf_answers": len(cf_answers),
            "answer_metric": answer_metric,
            "answer_jaccard": answer_similarity,
            "query_drift": query_drift,
            "amplification": query_drift / (graph_drift + amp_eps),
        }

    return {
        "run_id": _row_value(pair, "run_id"),
        "document_id": _row_value(pair, "document_id"),
        "intervention_id": _row_value(pair, "intervention_id"),
        "cause_family": _row_value(pair, "cause_family"),
        "semantic_class": _row_value(pair, "semantic_class"),
        "operator": _row_value(pair, "operator"),
        "base_event_id": _row_value(pair, "base_event_id"),
        "cf_event_id": _row_value(pair, "cf_event_id"),
        "graph_jaccard": graph_similarity,
        "graph_drift": graph_drift,
        "queries": query_results,
    }


def _descriptive_group(records: Sequence[dict], query_id: str) -> dict:
    query_drifts = [
        record["queries"][query_id]["query_drift"] for record in records
    ]
    graph_drifts = [record["graph_drift"] for record in records]
    amplification = [
        record["queries"][query_id]["amplification"] for record in records
    ]
    query_drift_mean = statistics.mean(query_drifts)
    graph_drift_mean = statistics.mean(graph_drifts)
    return {
        "n": len(records),
        "n_documents": len({record["document_id"] for record in records}),
        "query_drift_mean": query_drift_mean,
        "graph_drift_mean": graph_drift_mean,
        "amplification_mean_per_pair": statistics.mean(amplification),
        "amplification_ratio_of_means_damped": (
            query_drift_mean / (graph_drift_mean + AMP_EPS)
        ),
    }


def summarize_records(
    records: Sequence[dict],
    *,
    n_bootstrap: int,
    seed: int,
) -> dict:
    """Build complete-query summaries without truncating pair observations."""
    if not records:
        raise ValueError("cannot summarize zero pair records")
    summary = {}
    for specification in DIAGNOSTIC_QUERIES:
        query_id = specification.canonical_id
        overall = _descriptive_group(records, query_id)
        overall["amplification_document_cluster_ci"] = cluster_bootstrap_mean(
            (
                (
                    record["document_id"],
                    record["queries"][query_id]["amplification"],
                )
                for record in records
            ),
            n_bootstrap=n_bootstrap,
            seed=seed,
        )
        grouped = {}
        for field in ("cause_family", "semantic_class"):
            groups: dict[str, list[dict]] = defaultdict(list)
            for record in records:
                groups[record[field]].append(record)
            grouped[f"by_{field}"] = {
                group: _descriptive_group(group_records, query_id)
                for group, group_records in sorted(groups.items())
            }
        overall.update(grouped)
        summary[query_id] = overall
    return summary


def _read_only_connection(db_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(
        f"file:{db_path.resolve()}?mode=ro",
        uri=True,
    )
    connection.row_factory = sqlite3.Row
    return connection


def analyze_database(
    db_path: str | Path,
    *,
    n_bootstrap: int = 1000,
    seed: int = 0,
) -> dict:
    """Read one run DB and return a complete versioned diagnostic artifact."""
    db_path = Path(db_path)
    connection = _read_only_connection(db_path)
    try:
        pairs = connection.execute(
            """
            SELECT cfr.run_id, cfr.document_id, cfr.intervention_id,
                   cfr.base_event_id, cfr.cf_event_id,
                   COALESCE(ic.cause_family, 'unknown') AS cause_family,
                   COALESCE(ic.semantic_class, 'unknown') AS semantic_class,
                   COALESCE(ic.operator, 'unknown') AS operator
            FROM counterfactual_runs AS cfr
            LEFT JOIN intervention_candidates AS ic
              ON ic.intervention_id = cfr.intervention_id
            WHERE cfr.status='ok'
            ORDER BY cfr.document_id, cfr.run_id
            """
        ).fetchall()
        event_documents = {
            row["event_id"]: row["document_id"]
            for row in connection.execute(
                "SELECT event_id, document_id FROM extraction_events"
            )
        }
        witnesses: dict[str, list[tuple[str, str | None]]] = defaultdict(list)
        for row in connection.execute(
            """
            SELECT eo.run_id, eo.matched_edge_id,
                   matched.event_id AS matched_event_id
            FROM edge_outcomes AS eo
            JOIN counterfactual_runs AS cfr ON cfr.run_id=eo.run_id
            LEFT JOIN extracted_edges AS matched
              ON matched.edge_id=eo.matched_edge_id
            WHERE cfr.status='ok'
              AND eo.matched_edge_id IS NOT NULL
              AND eo.matched_edge_id<>''
            ORDER BY eo.rowid
            """
        ):
            witnesses[row["run_id"]].append(
                (row["matched_edge_id"], row["matched_event_id"])
            )
        pairing_audit = validate_authoritative_pairs(
            pairs, event_documents, witnesses
        )

        required_events = {
            event_id
            for pair in pairs
            for event_id in (pair["base_event_id"], pair["cf_event_id"])
        }
        edges_by_event: dict[str, list] = {
            event_id: [] for event_id in required_events
        }
        for edge in connection.execute(
            """
            SELECT event_id, subject_entity_id, subject_name, relation,
                   object_entity_id, object_name
            FROM extracted_edges
            ORDER BY rowid
            """
        ):
            if edge["event_id"] in edges_by_event:
                edges_by_event[edge["event_id"]].append(edge)

        event_schema = {
            row["event_id"]: row["schema_id"]
            for row in connection.execute(
                "SELECT event_id, schema_id FROM extraction_events"
            )
        }
        schema_relations = {
            row["schema_id"]: {
                relation["id"]
                for relation in json.loads(row["relation_types_json"])
            }
            for row in connection.execute(
                "SELECT schema_id, relation_types_json FROM schemas"
            )
        }

        records = []
        missing_base_schema = 0
        for pair in pairs:
            base_event_id = pair["base_event_id"]
            schema_id = event_schema.get(base_event_id)
            base_relation_ids = schema_relations.get(schema_id)
            if base_relation_ids is None:
                missing_base_schema += 1
            records.append(
                evaluate_pair(
                    pair,
                    edges_by_event[base_event_id],
                    edges_by_event[pair["cf_event_id"]],
                    base_relation_ids=base_relation_ids,
                )
            )
    finally:
        connection.close()

    pairing_audit["n_pairs_missing_base_schema"] = missing_base_schema
    pairing_audit["n_empty_base_graphs"] = sum(
        not edges_by_event[record["base_event_id"]] for record in records
    )
    pairing_audit["n_empty_cf_graphs"] = sum(
        not edges_by_event[record["cf_event_id"]] for record in records
    )
    return {
        "artifact_type": ARTIFACT_TYPE,
        "artifact_version": ARTIFACT_VERSION,
        "source_run": db_path.stem,
        "pairing": pairing_audit,
        "metrics": {
            "graph_drift": "1 - canonicalized typed-edge Jaccard",
            "query_drift": (
                "D1: 1 - canonicalized bucket-aware typed-edge Jaccard; "
                "D2-D5: 1 - exact answer-set Jaccard"
            ),
            "amplification": "query_drift / (graph_drift + 0.05)",
            "amplification_epsilon": AMP_EPS,
            "aggregation": "mean of complete per-pair ratios",
            "confidence_interval": (
                "document-cluster bootstrap over complete per-pair ratios"
            ),
        },
        "query_catalog": [asdict(spec) for spec in DIAGNOSTIC_QUERIES],
        "summary": summarize_records(
            records,
            n_bootstrap=n_bootstrap,
            seed=seed,
        ),
        "per_pair": records,
    }
