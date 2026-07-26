"""Auditable full-run evaluation of the deployment Q1--Q4 workload.

The runner reads already-materialized lineage databases in SQLite read-only
mode.  It does not call an LLM, mutate a run database, or execute Kuzu during
the full-population pass.  A separate parity check validates the shared
offline set semantics against the fixed Cypher templates.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import statistics
from collections import defaultdict
from dataclasses import asdict
from pathlib import Path
from typing import Mapping, Sequence

from graphguard.diagnostic_runner import (
    cluster_bootstrap_mean,
    validate_authoritative_pairs,
)
from graphguard.qa import build_queries, execute, graph_jaccard, jaccard
from graphguard.query_catalog import DEPLOYMENT_QUERIES


ARTIFACT_TYPE = "graphguard.deployment_q1q4_amplification"
ARTIFACT_VERSION = 1
AMP_EPS = 0.05
FAMILY_TO_QUERY_ID = {
    "lookup": "deployment.lookup",
    "neighbor": "deployment.neighbor",
    "join": "deployment.shared_tail_join",
    "twohop": "deployment.typed_two_hop",
}


def _read_only_connection(db_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(
        f"file:{db_path.resolve()}?mode=ro",
        uri=True,
    )
    connection.row_factory = sqlite3.Row
    return connection


def _canonical_json(value) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _answer_payload(answers: set) -> list:
    """Return a stable JSON representation for scalar or tuple answers."""
    encoded = []
    for answer in answers:
        item = list(answer) if isinstance(answer, tuple) else answer
        encoded.append((_canonical_json(item), item))
    return [item for _, item in sorted(encoded)]


def _set_digest(answers: set) -> str:
    payload = _canonical_json(_answer_payload(answers)).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _query_parameters(query: tuple[str, dict]) -> dict:
    return {
        key: value
        for key, value in query[1].items()
        if key != "gold"
    }


def _query_id(family: str, parameters: Mapping) -> str:
    payload = _canonical_json(
        {
            "family": FAMILY_TO_QUERY_ID[family],
            "parameters": dict(parameters),
        }
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def build_catalog(
    document_id: str,
    schema_id: str,
    gold_edges: set[tuple[str, str, str]],
    allowed_relations: set[str],
) -> tuple[dict, list[tuple[str, dict]]]:
    """Build one schema-eligible, unique-parameter query catalog."""
    eligible_gold = {
        edge for edge in gold_edges if edge[1] in allowed_relations
    }
    queries = build_queries(
        gold_edges,
        allowed_relations=allowed_relations,
    )
    entries = []
    seen_ids = set()
    family_counts: dict[str, int] = defaultdict(int)
    for query in queries:
        family = query[0]
        parameters = _query_parameters(query)
        stable_id = _query_id(family, parameters)
        if stable_id in seen_ids:
            raise ValueError(
                f"{document_id}/{schema_id}: duplicate query {stable_id}"
            )
        seen_ids.add(stable_id)
        family_counts[family] += 1
        gold_answers = query[1]["gold"]
        entries.append(
            {
                "query_id": stable_id,
                "family": FAMILY_TO_QUERY_ID[family],
                "parameters": parameters,
                "gold_answer_count": len(gold_answers),
                "gold_answer_sha256": _set_digest(gold_answers),
            }
        )

    catalog_payload = {
        "document_id": document_id,
        "base_schema_id": schema_id,
        "base_schema_relation_count": len(allowed_relations),
        "base_schema_relation_ids": sorted(allowed_relations),
        "raw_gold_edge_count": len(gold_edges),
        "eligible_gold_edge_count": len(eligible_gold),
        "excluded_gold_edge_count": len(gold_edges) - len(eligible_gold),
        "family_query_counts": {
            FAMILY_TO_QUERY_ID[family]: family_counts.get(family, 0)
            for family in FAMILY_TO_QUERY_ID
        },
        "queries": entries,
    }
    catalog_id = hashlib.sha256(
        _canonical_json(catalog_payload).encode("utf-8")
    ).hexdigest()
    catalog_payload["catalog_id"] = catalog_id
    return catalog_payload, queries


def _evaluate_family(
    queries: Sequence[tuple[str, dict]],
    base_edges: set[tuple[str, str, str]],
    cf_edges: set[tuple[str, str, str]],
    *,
    graph_drift: float,
) -> dict:
    query_records = []
    for query in queries:
        family = query[0]
        parameters = _query_parameters(query)
        base_answers = execute(base_edges, query)
        cf_answers = execute(cf_edges, query)
        answer_similarity = jaccard(base_answers, cf_answers)
        query_records.append(
            {
                "query_id": _query_id(family, parameters),
                "base_answer_count": len(base_answers),
                "base_answer_sha256": _set_digest(base_answers),
                "cf_answer_count": len(cf_answers),
                "cf_answer_sha256": _set_digest(cf_answers),
                "answer_jaccard": answer_similarity,
                "query_drift": 1.0 - answer_similarity,
                "answer_state": (
                    "both_empty"
                    if not base_answers and not cf_answers
                    else "base_only"
                    if base_answers and not cf_answers
                    else "cf_only"
                    if cf_answers and not base_answers
                    else "both_nonempty"
                ),
            }
        )

    if not query_records:
        return {
            "eligible": False,
            "ineligible_reason": "no_schema_eligible_gold_query",
            "n_queries": 0,
            "queries": [],
        }

    drifts = [record["query_drift"] for record in query_records]
    family_drift = statistics.mean(drifts)
    return {
        "eligible": True,
        "ineligible_reason": None,
        "n_queries": len(query_records),
        "mean_query_drift": family_drift,
        "max_query_drift": max(drifts),
        "amplification": family_drift / (graph_drift + AMP_EPS),
        "answer_state_counts": {
            state: sum(
                record["answer_state"] == state for record in query_records
            )
            for state in (
                "both_empty",
                "base_only",
                "cf_only",
                "both_nonempty",
            )
        },
        "queries": query_records,
    }


def evaluate_pair(
    pair,
    *,
    base_edges: set[tuple[str, str, str]],
    cf_edges: set[tuple[str, str, str]],
    all_base_edge_count: int,
    all_cf_edge_count: int,
    catalog_id: str,
    queries: Sequence[tuple[str, dict]],
) -> dict:
    """Evaluate one authoritative pair with pair-then-family aggregation."""
    graph_similarity = graph_jaccard(base_edges, cf_edges)
    graph_drift = 1.0 - graph_similarity
    by_family: dict[str, list[tuple[str, dict]]] = defaultdict(list)
    for query in queries:
        by_family[query[0]].append(query)

    families = {}
    for family, query_id in FAMILY_TO_QUERY_ID.items():
        families[query_id] = _evaluate_family(
            by_family.get(family, ()),
            base_edges,
            cf_edges,
            graph_drift=graph_drift,
        )

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
        "base_schema_id": pair["base_schema_id"],
        "cf_schema_id": pair["cf_schema_id"],
        "query_catalog_id": catalog_id,
        "base_edge_counts": {
            "all_rows": all_base_edge_count,
            "linked_rows": pair["base_linked_row_count"],
            "deduplicated_typed_edges": len(base_edges),
            "excluded_unlinked_rows": (
                all_base_edge_count - pair["base_linked_row_count"]
            ),
        },
        "cf_edge_counts": {
            "all_rows": all_cf_edge_count,
            "linked_rows": pair["cf_linked_row_count"],
            "deduplicated_typed_edges": len(cf_edges),
            "excluded_unlinked_rows": (
                all_cf_edge_count - pair["cf_linked_row_count"]
            ),
        },
        "graph_jaccard": graph_similarity,
        "graph_drift": graph_drift,
        "families": families,
    }


def _descriptive_group(records: Sequence[dict], query_id: str) -> dict:
    eligible = [
        record for record in records
        if record["families"][query_id]["eligible"]
    ]
    if not eligible:
        return {
            "n_pairs_total": len(records),
            "n_pairs": 0,
            "n_pairs_ineligible": len(records),
            "n_documents": 0,
            "n_query_evaluations": 0,
            "status": "not_applicable",
        }

    pair_query_drifts = [
        record["families"][query_id]["mean_query_drift"]
        for record in eligible
    ]
    graph_drifts = [record["graph_drift"] for record in eligible]
    amplifications = [
        record["families"][query_id]["amplification"]
        for record in eligible
    ]
    instance_drifts = [
        query["query_drift"]
        for record in eligible
        for query in record["families"][query_id]["queries"]
    ]
    return {
        "status": "ok",
        "n_pairs_total": len(records),
        "n_pairs": len(eligible),
        "n_pairs_ineligible": len(records) - len(eligible),
        "n_documents": len(
            {record["document_id"] for record in eligible}
        ),
        "n_query_evaluations": len(instance_drifts),
        "answer_state_counts": {
            state: sum(
                record["families"][query_id]["answer_state_counts"][state]
                for record in eligible
            )
            for state in (
                "both_empty",
                "base_only",
                "cf_only",
                "both_nonempty",
            )
        },
        "query_drift_mean_per_pair": statistics.mean(pair_query_drifts),
        "query_drift_mean_per_instance": statistics.mean(instance_drifts),
        "graph_drift_mean": statistics.mean(graph_drifts),
        "amplification_mean_per_pair": statistics.mean(amplifications),
        "amplification_ratio_of_means_damped": (
            statistics.mean(pair_query_drifts)
            / (statistics.mean(graph_drifts) + AMP_EPS)
        ),
    }


def summarize_records(
    records: Sequence[dict],
    *,
    n_bootstrap: int,
    seed: int,
) -> dict:
    if not records:
        raise ValueError("cannot summarize zero pair records")
    summary = {}
    for query_id in FAMILY_TO_QUERY_ID.values():
        overall = _descriptive_group(records, query_id)
        if overall["status"] == "ok":
            overall["amplification_document_cluster_ci"] = (
                cluster_bootstrap_mean(
                    (
                        (
                            record["document_id"],
                            record["families"][query_id]["amplification"],
                        )
                        for record in records
                        if record["families"][query_id]["eligible"]
                    ),
                    n_bootstrap=n_bootstrap,
                    seed=seed,
                )
            )
        for field in ("cause_family", "semantic_class"):
            groups: dict[str, list[dict]] = defaultdict(list)
            for record in records:
                groups[record[field]].append(record)
            overall[f"by_{field}"] = {
                group: _descriptive_group(group_records, query_id)
                for group, group_records in sorted(groups.items())
            }
        summary[query_id] = overall
    return summary


def analyze_database(
    db_path: str | Path,
    *,
    n_bootstrap: int = 1000,
    seed: int = 0,
) -> dict:
    """Return a complete deployment Q1--Q4 artifact for one run DB."""
    db_path = Path(db_path)
    connection = _read_only_connection(db_path)
    try:
        # Keep every SELECT in one stable SQLite read snapshot.
        connection.execute("BEGIN")
        pairs = connection.execute(
            """
            SELECT cfr.run_id, cfr.document_id, cfr.intervention_id,
                   cfr.base_event_id, cfr.cf_event_id,
                   base.schema_id AS base_schema_id,
                   cf.schema_id AS cf_schema_id,
                   COALESCE(ic.cause_family, 'unknown') AS cause_family,
                   COALESCE(ic.semantic_class, 'unknown') AS semantic_class,
                   COALESCE(ic.operator, 'unknown') AS operator,
                   COALESCE(ic.target_type, 'unknown') AS target_type,
                   COALESCE(ic.target_id, 'unknown') AS target_id
            FROM counterfactual_runs AS cfr
            LEFT JOIN extraction_events AS base
              ON base.event_id=cfr.base_event_id
            LEFT JOIN extraction_events AS cf
              ON cf.event_id=cfr.cf_event_id
            LEFT JOIN intervention_candidates AS ic
              ON ic.intervention_id=cfr.intervention_id
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
            pairs,
            event_documents,
            witnesses,
        )

        schema_relations = {}
        for row in connection.execute(
            "SELECT schema_id, relation_types_json FROM schemas"
        ):
            schema_relations[row["schema_id"]] = {
                relation["id"]
                for relation in json.loads(row["relation_types_json"])
            }
        missing_schemas = sorted(
            {
                pair["base_schema_id"]
                for pair in pairs
                if pair["base_schema_id"] not in schema_relations
            }
        )
        if missing_schemas:
            raise ValueError(f"missing base schemas: {missing_schemas}")

        gold_by_document: dict[str, set[tuple[str, str, str]]] = defaultdict(
            set
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

        required_events = {
            event_id
            for pair in pairs
            for event_id in (pair["base_event_id"], pair["cf_event_id"])
        }
        edges_by_event: dict[
            str, set[tuple[str, str, str]]
        ] = {event_id: set() for event_id in required_events}
        edge_counts = {
            event_id: {"all_rows": 0, "linked_rows": 0}
            for event_id in required_events
        }
        for row in connection.execute(
            """
            SELECT event_id, subject_entity_id, relation, object_entity_id
            FROM extracted_edges
            ORDER BY rowid
            """
        ):
            event_id = row["event_id"]
            if event_id not in edges_by_event:
                continue
            edge_counts[event_id]["all_rows"] += 1
            if (
                row["subject_entity_id"] is None
                or row["relation"] is None
                or row["object_entity_id"] is None
            ):
                continue
            edge_counts[event_id]["linked_rows"] += 1
            edges_by_event[event_id].add(
                (
                    row["subject_entity_id"],
                    row["relation"],
                    row["object_entity_id"],
                )
            )

        catalogs = {}
        executable_catalogs = {}
        records = []
        for raw_pair in pairs:
            pair = dict(raw_pair)
            base_event_id = pair["base_event_id"]
            cf_event_id = pair["cf_event_id"]
            schema_id = pair["base_schema_id"]
            catalog_key = (pair["document_id"], schema_id)
            if catalog_key not in executable_catalogs:
                catalog, queries = build_catalog(
                    pair["document_id"],
                    schema_id,
                    gold_by_document.get(pair["document_id"], set()),
                    schema_relations[schema_id],
                )
                catalogs[catalog["catalog_id"]] = catalog
                executable_catalogs[catalog_key] = (
                    catalog["catalog_id"],
                    queries,
                )
            catalog_id, queries = executable_catalogs[catalog_key]
            pair["base_linked_row_count"] = edge_counts[base_event_id][
                "linked_rows"
            ]
            pair["cf_linked_row_count"] = edge_counts[cf_event_id][
                "linked_rows"
            ]
            records.append(
                evaluate_pair(
                    pair,
                    base_edges=edges_by_event[base_event_id],
                    cf_edges=edges_by_event[cf_event_id],
                    all_base_edge_count=edge_counts[base_event_id]["all_rows"],
                    all_cf_edge_count=edge_counts[cf_event_id]["all_rows"],
                    catalog_id=catalog_id,
                    queries=queries,
                )
            )
    finally:
        connection.close()

    pairing_audit.update(
        {
            "n_empty_base_graphs": sum(
                not edges_by_event[record["base_event_id"]]
                for record in records
            ),
            "n_empty_cf_graphs": sum(
                not edges_by_event[record["cf_event_id"]]
                for record in records
            ),
            "n_pairs_with_unlinked_base_rows": sum(
                record["base_edge_counts"]["excluded_unlinked_rows"] > 0
                for record in records
            ),
            "n_pairs_with_unlinked_cf_rows": sum(
                record["cf_edge_counts"]["excluded_unlinked_rows"] > 0
                for record in records
            ),
        }
    )
    return {
        "artifact_type": ARTIFACT_TYPE,
        "artifact_version": ARTIFACT_VERSION,
        "source_run": db_path.stem,
        "protocol": {
            "query_workload": (
                "gold-instantiated deployment Q1-Q4, restricted to relations "
                "declared by each pair's base schema"
            ),
            "query_identity": "canonical database parameter tuple",
            "query_caps": {
                "deployment.shared_tail_join": 6,
                "deployment.typed_two_hop": 8,
            },
            "cap_order": "merge unique parameters, sort, then cap",
            "query_relation_policy": (
                "fixed raw relation labels, matching deployed Kuzu Cypher"
            ),
            "graph_relation_policy": (
                "declared renames projected to base relations; coarse buckets "
                "matched to member relations"
            ),
            "edge_population": (
                "deduplicated typed triples with both endpoint identifiers, "
                "matching Kuzu ingestion"
            ),
            "empty_answers": {
                "both_empty_query_drift": 0.0,
                "one_empty_query_drift": 1.0,
                "ineligible_family": "NA",
            },
        },
        "pairing": pairing_audit,
        "metrics": {
            "graph_drift": "1 - canonicalized typed-edge Jaccard",
            "query_drift": "1 - exact answer-set Jaccard",
            "family_query_drift": (
                "mean query drift across unique instances within pair/family"
            ),
            "amplification": (
                "family_query_drift / (graph_drift + 0.05)"
            ),
            "amplification_epsilon": AMP_EPS,
            "primary_aggregation": "mean of eligible per-pair amplification",
            "confidence_interval": (
                "document-cluster bootstrap over eligible per-pair ratios"
            ),
            "bootstrap": {
                "n": n_bootstrap,
                "seed": seed,
                "alpha": 0.05,
            },
        },
        "query_templates": [asdict(spec) for spec in DEPLOYMENT_QUERIES],
        "query_catalogs": {
            catalog_id: catalog
            for catalog_id, catalog in sorted(catalogs.items())
        },
        "summary": summarize_records(
            records,
            n_bootstrap=n_bootstrap,
            seed=seed,
        ),
        "per_pair": records,
    }
