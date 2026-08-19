"""Actual-Kuzu Q1--Q4 evaluation for the external-toolchain checkpoints.

The external extractors emit document-local entity surfaces and public schema
labels, while the deployment workload uses benchmark entity identifiers and
relation identifiers.  This module applies one declared, output-independent
canonicalizer to every endpoint, executes a shared gold-instantiated query
catalog in Kuzu, and checks every answer against the deterministic executor.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import statistics
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from graphguard.deployment_runner import (
    FAMILY_TO_QUERY_ID,
    _query_id,
    _set_digest,
    build_catalog,
)
from graphguard.kuzu_executor import KuzuGraph, kuzu_version
from graphguard.qa import build_queries, execute, jaccard
from graphguard.sqlite_snapshot import sha256_file


ARTIFACT_TYPE = "graphguard.external_toolchain_q1q4_kuzu"
ARTIFACT_VERSION = 1
QUERY_DRIFT_TAU = 0.30
CONDITIONS = (
    "base",
    "schema_reorder",
    "schema_rename",
    "prompt_para",
    "evidence_reorder",
    "resample",
)
AXES = CONDITIONS[1:]
ANSWER_STATES = (
    "both_empty",
    "base_only",
    "cf_only",
    "both_nonempty",
)
EXTERNAL_RELATION_RENAMES = {
    "country": "sovereign_state",
    "located_in": "situated_in",
    "headquarters_location": "hq_place",
    "place_of_birth": "birthplace",
    "place_of_death": "deathplace",
    "employer": "works_for",
    "part_of": "component_of",
    "member_of": "affiliated_with",
    "publication_date": "released_on",
    "performer": "performed_by",
    "author": "written_by",
    "director": "directed_by",
}
EXTERNAL_RELATION_RENAME_INVERSE = {
    renamed: base for base, renamed in EXTERNAL_RELATION_RENAMES.items()
}


def normalize_surface(value: Any) -> str:
    """Return the declared case-insensitive whitespace-normalized surface."""
    return " ".join(str(value or "").lower().split())


@dataclass(frozen=True)
class EntityResolution:
    key: str
    status: str


class DocumentEntityResolver:
    """Resolve one document's declared names without manual matching."""

    def __init__(self, name_to_ids: Mapping[str, set[str]]):
        self._name_to_ids = {
            name: frozenset(ids)
            for name, ids in name_to_ids.items()
            if name and ids
        }

    def resolve(self, surface: Any) -> EntityResolution:
        name = normalize_surface(surface)
        exact = set(self._name_to_ids.get(name, ()))
        if len(exact) == 1:
            return EntityResolution(next(iter(exact)), "exact")
        if len(exact) > 1:
            return EntityResolution(f"name:{name}", "ambiguous")
        return EntityResolution(f"name:{name}", "unlinked")


def _read_only_connection(db_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(
        f"file:{db_path.resolve()}?mode=ro",
        uri=True,
    )
    connection.row_factory = sqlite3.Row
    return connection


def _load_database_context(
    db_path: Path,
    documents: set[str],
) -> tuple[
    dict[str, DocumentEntityResolver],
    dict[str, str],
    set[str],
    dict[str, set[tuple[str, str, str]]],
]:
    connection = _read_only_connection(db_path)
    try:
        connection.execute("BEGIN")
        schema_row = connection.execute(
            """
            SELECT relation_types_json
            FROM schemas
            WHERE schema_id='docred_full'
            """
        ).fetchone()
        if schema_row is None:
            raise ValueError("missing docred_full schema")
        relations = json.loads(schema_row["relation_types_json"])
        label_to_id = {
            normalize_surface(relation["label"]): str(relation["id"])
            for relation in relations
        }
        allowed_relation_ids = {
            str(relation["id"]) for relation in relations
        }

        name_maps: dict[str, dict[str, set[str]]] = defaultdict(
            lambda: defaultdict(set)
        )
        for row in connection.execute(
            """
            SELECT document_id, entity_id, canonical_name, aliases_json
            FROM entities
            ORDER BY document_id, entity_id
            """
        ):
            document_id = row["document_id"]
            if document_id not in documents:
                continue
            aliases = json.loads(row["aliases_json"] or "[]")
            for value in [row["canonical_name"], *aliases]:
                name = normalize_surface(value)
                if name:
                    name_maps[document_id][name].add(row["entity_id"])

        gold_by_document: dict[
            str, set[tuple[str, str, str]]
        ] = defaultdict(set)
        for row in connection.execute(
            """
            SELECT document_id, head_entity_id, relation_base, tail_entity_id
            FROM gold_edges
            WHERE head_entity_id IS NOT NULL
              AND relation_base IS NOT NULL
              AND tail_entity_id IS NOT NULL
            ORDER BY document_id, gold_edge_id
            """
        ):
            document_id = row["document_id"]
            if document_id not in documents:
                continue
            relation = str(row["relation_base"])
            if relation not in allowed_relation_ids:
                continue
            gold_by_document[document_id].add(
                (
                    str(row["head_entity_id"]),
                    relation,
                    str(row["tail_entity_id"]),
                )
            )
    finally:
        connection.close()

    missing_resolvers = sorted(documents - set(name_maps))
    if missing_resolvers:
        raise ValueError(
            f"documents missing entity namespaces: {missing_resolvers}"
        )
    missing_gold = sorted(documents - set(gold_by_document))
    if missing_gold:
        raise ValueError(f"documents missing gold edges: {missing_gold}")
    return (
        {
            document_id: DocumentEntityResolver(names)
            for document_id, names in name_maps.items()
        },
        label_to_id,
        allowed_relation_ids,
        dict(gold_by_document),
    )


def load_checkpoint(path: Path) -> dict[tuple[str, str], dict]:
    """Load one canonical 100-document by six-condition checkpoint."""
    records: dict[tuple[str, str], dict] = {}
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        if not line.strip():
            continue
        record = json.loads(line)
        key = (str(record["doc"]), str(record["condition"]))
        if key in records:
            raise ValueError(f"{path}:{line_number}: duplicate {key}")
        records[key] = record
    documents = {document for document, _ in records}
    expected = {
        (document, condition)
        for document in documents
        for condition in CONDITIONS
    }
    missing = sorted(expected - set(records))
    extra = sorted(set(records) - expected)
    if missing or extra:
        raise ValueError(
            f"{path}: non-rectangular checkpoint; "
            f"{len(missing)=}, {len(extra)=}"
        )
    return records


def canonicalize_edges(
    record: Mapping[str, Any],
    resolver: DocumentEntityResolver,
    label_to_id: Mapping[str, str],
) -> tuple[set[tuple[str, str, str]] | None, dict[str, Any]]:
    """Map one external endpoint into the benchmark identifier namespace."""
    raw_edges = record.get("edges")
    if raw_edges is None:
        return None, {
            "status": "extraction_error",
            "raw_edges": 0,
            "canonical_edges": 0,
            "entity_resolution": {
                status: 0
                for status in ("exact", "ambiguous", "unlinked")
            },
            "off_schema_relations": 0,
        }

    counts: Counter[str] = Counter()
    canonical: set[tuple[str, str, str]] = set()
    off_schema = 0
    for raw_edge in raw_edges:
        if not isinstance(raw_edge, (list, tuple)) or len(raw_edge) != 3:
            raise ValueError(
                f"{record.get('doc')}/{record.get('condition')}: "
                f"malformed edge {raw_edge!r}"
            )
        subject, relation, obj = raw_edge
        subject_resolution = resolver.resolve(subject)
        object_resolution = resolver.resolve(obj)
        counts[subject_resolution.status] += 1
        counts[object_resolution.status] += 1
        relation_label = normalize_surface(relation).replace(" ", "_")
        relation_label = EXTERNAL_RELATION_RENAME_INVERSE.get(
            relation_label,
            relation_label,
        )
        relation_id = label_to_id.get(
            relation_label,
            label_to_id.get(normalize_surface(relation)),
        )
        if relation_id is None:
            off_schema += 1
            relation_id = f"label:{relation_label}"
        canonical.add(
            (
                subject_resolution.key,
                relation_id,
                object_resolution.key,
            )
        )
    return canonical, {
        "status": "ok",
        "raw_edges": len(raw_edges),
        "canonical_edges": len(canonical),
        "entity_resolution": {
            status: counts[status]
            for status in ("exact", "ambiguous", "unlinked")
        },
        "off_schema_relations": off_schema,
    }


def _answer_state(base_answers: set, cf_answers: set) -> str:
    if not base_answers and not cf_answers:
        return "both_empty"
    if base_answers and not cf_answers:
        return "base_only"
    if cf_answers and not base_answers:
        return "cf_only"
    return "both_nonempty"


def _execute_endpoint(
    *,
    endpoint_id: str,
    edges: set[tuple[str, str, str]],
    queries: Sequence[tuple[str, dict]],
    graph_factory=KuzuGraph,
) -> tuple[str, dict[str, set], dict[str, Any]]:
    answers: dict[str, set] = {}
    mismatches: list[dict[str, Any]] = []
    with graph_factory(edges) as graph:
        for query in queries:
            family, parameters_with_gold = query
            parameters = {
                key: value
                for key, value in parameters_with_gold.items()
                if key != "gold"
            }
            query_id = _query_id(family, parameters)
            offline_answers = execute(edges, query)
            kuzu_answers = graph.execute((family, parameters))
            if offline_answers != kuzu_answers:
                mismatches.append(
                    {
                        "endpoint_id": endpoint_id,
                        "query_id": query_id,
                        "family": FAMILY_TO_QUERY_ID[family],
                        "offline_answer_sha256": _set_digest(
                            offline_answers
                        ),
                        "kuzu_answer_sha256": _set_digest(kuzu_answers),
                        "offline_answer_count": len(offline_answers),
                        "kuzu_answer_count": len(kuzu_answers),
                    }
                )
            answers[query_id] = kuzu_answers
    return endpoint_id, answers, {
        "n_queries": len(queries),
        "n_answer_sets": len(queries),
        "mismatches": mismatches,
    }


def _sum_mapping_audits(audits: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    rows = list(audits)
    entity_counts = {
        status: sum(
            int(row["entity_resolution"][status])
            for row in rows
            if row["status"] == "ok"
        )
        for status in ("exact", "ambiguous", "unlinked")
    }
    total_endpoints = sum(entity_counts.values())
    linked = entity_counts["exact"]
    return {
        "n_endpoints": len(rows),
        "n_successful_endpoints": sum(row["status"] == "ok" for row in rows),
        "n_error_endpoints": sum(
            row["status"] == "extraction_error" for row in rows
        ),
        "raw_edges": sum(int(row["raw_edges"]) for row in rows),
        "canonical_edges": sum(int(row["canonical_edges"]) for row in rows),
        "entity_resolution": entity_counts,
        "linked_endpoint_rate": (
            linked / total_endpoints if total_endpoints else 0.0
        ),
        "off_schema_relations": sum(
            int(row["off_schema_relations"]) for row in rows
        ),
    }


def _summarize_axis(records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    if not records:
        raise ValueError("cannot summarize an empty external-query axis")
    max_drifts = [float(record["max_query_drift"]) for record in records]
    mean_drifts = [float(record["mean_query_drift"]) for record in records]
    state_counts = {
        state: sum(int(record["answer_state_counts"][state]) for record in records)
        for state in ANSWER_STATES
    }
    n_query_evaluations = sum(state_counts.values())
    return {
        "n_pairs": len(records),
        "n_documents": len({record["document_id"] for record in records}),
        "n_query_evaluations": n_query_evaluations,
        "mean_pair_max_query_drift": statistics.mean(max_drifts),
        "median_pair_max_query_drift": statistics.median(max_drifts),
        "mean_pair_mean_query_drift": statistics.mean(mean_drifts),
        "violation_tau": QUERY_DRIFT_TAU,
        "violation_comparator": ">",
        "violation_rate": sum(
            drift > QUERY_DRIFT_TAU for drift in max_drifts
        )
        / len(max_drifts),
        "active_pair_rate": sum(
            record["n_active_queries"] > 0 for record in records
        )
        / len(records),
        "active_query_rate": (
            1.0 - state_counts["both_empty"] / n_query_evaluations
            if n_query_evaluations
            else 0.0
        ),
        "answer_state_counts": state_counts,
    }


def analyze_external_toolchains(
    *,
    db_path: str | Path,
    checkpoints: Mapping[str, str | Path],
    workers: int = 1,
    graph_factory=KuzuGraph,
) -> dict[str, Any]:
    """Execute and summarize the shared external-toolchain Q1--Q4 workload."""
    if workers <= 0:
        raise ValueError("workers must be positive")
    db_path = Path(db_path)
    checkpoint_paths = {
        toolchain: Path(path) for toolchain, path in checkpoints.items()
    }
    loaded = {
        toolchain: load_checkpoint(path)
        for toolchain, path in checkpoint_paths.items()
    }
    document_sets = {
        toolchain: {document for document, _ in records}
        for toolchain, records in loaded.items()
    }
    if len({frozenset(documents) for documents in document_sets.values()}) != 1:
        raise ValueError(f"toolchain document cohorts differ: {document_sets}")
    documents = next(iter(document_sets.values()))
    resolvers, label_to_id, allowed_relations, gold = _load_database_context(
        db_path,
        documents,
    )

    catalogs: dict[str, dict[str, Any]] = {}
    queries_by_document: dict[str, list[tuple[str, dict]]] = {}
    for document_id in sorted(documents):
        catalog, queries = build_catalog(
            document_id,
            "docred_full",
            gold[document_id],
            allowed_relations,
        )
        if not queries:
            raise ValueError(f"{document_id}: empty Q1-Q4 catalog")
        catalogs[document_id] = catalog
        queries_by_document[document_id] = queries

    all_toolchain_results: dict[str, Any] = {}
    all_mismatches: list[dict[str, Any]] = []
    total_materialized = 0
    total_queries = 0
    total_answer_sets = 0

    for toolchain, records in loaded.items():
        canonical_edges: dict[
            tuple[str, str], set[tuple[str, str, str]] | None
        ] = {}
        mapping_audits: dict[tuple[str, str], dict[str, Any]] = {}
        for key, record in records.items():
            edges, audit = canonicalize_edges(
                record,
                resolvers[key[0]],
                label_to_id,
            )
            canonical_edges[key] = edges
            mapping_audits[key] = audit

        jobs = []
        for (document_id, condition), edges in canonical_edges.items():
            if edges is None:
                continue
            endpoint_id = f"{toolchain}:{document_id}:{condition}"
            jobs.append(
                {
                    "endpoint_id": endpoint_id,
                    "document_id": document_id,
                    "condition": condition,
                    "edges": edges,
                    "queries": queries_by_document[document_id],
                }
            )

        endpoint_answers: dict[tuple[str, str], dict[str, set]] = {}
        endpoint_audits: list[dict[str, Any]] = []
        if workers == 1:
            completed = [
                _execute_endpoint(
                    endpoint_id=job["endpoint_id"],
                    edges=job["edges"],
                    queries=job["queries"],
                    graph_factory=graph_factory,
                )
                for job in jobs
            ]
        else:
            completed = []
            with ThreadPoolExecutor(max_workers=workers) as executor:
                futures = {
                    executor.submit(
                        _execute_endpoint,
                        endpoint_id=job["endpoint_id"],
                        edges=job["edges"],
                        queries=job["queries"],
                        graph_factory=graph_factory,
                    ): job
                    for job in jobs
                }
                for future in as_completed(futures):
                    completed.append(future.result())

        endpoint_lookup = {
            job["endpoint_id"]: (job["document_id"], job["condition"])
            for job in jobs
        }
        for endpoint_id, answers, audit in completed:
            key = endpoint_lookup[endpoint_id]
            endpoint_answers[key] = answers
            endpoint_audits.append(audit)
            all_mismatches.extend(audit["mismatches"])
            total_materialized += 1
            total_queries += int(audit["n_queries"])
            total_answer_sets += int(audit["n_answer_sets"])

        per_pair: list[dict[str, Any]] = []
        by_axis: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for document_id in sorted(documents):
            base_edges = canonical_edges[(document_id, "base")]
            if base_edges is None:
                continue
            base_answers = endpoint_answers[(document_id, "base")]
            queries = queries_by_document[document_id]
            for condition in AXES:
                cf_edges = canonical_edges[(document_id, condition)]
                if cf_edges is None:
                    continue
                cf_answers = endpoint_answers[(document_id, condition)]
                query_records = []
                state_counts: Counter[str] = Counter()
                for family, parameters_with_gold in queries:
                    parameters = {
                        key: value
                        for key, value in parameters_with_gold.items()
                        if key != "gold"
                    }
                    query_id = _query_id(family, parameters)
                    base_set = base_answers[query_id]
                    cf_set = cf_answers[query_id]
                    similarity = jaccard(base_set, cf_set)
                    state = _answer_state(base_set, cf_set)
                    state_counts[state] += 1
                    query_records.append(
                        {
                            "query_id": query_id,
                            "family": FAMILY_TO_QUERY_ID[family],
                            "base_answer_count": len(base_set),
                            "base_answer_sha256": _set_digest(base_set),
                            "cf_answer_count": len(cf_set),
                            "cf_answer_sha256": _set_digest(cf_set),
                            "answer_state": state,
                            "query_drift": 1.0 - similarity,
                        }
                    )
                drifts = [
                    float(record["query_drift"])
                    for record in query_records
                ]
                pair_record = {
                    "pair_id": hashlib.sha256(
                        (
                            f"{toolchain}\0{document_id}\0"
                            f"base\0{condition}"
                        ).encode("utf-8")
                    ).hexdigest(),
                    "toolchain": toolchain,
                    "document_id": document_id,
                    "axis": condition,
                    "query_catalog_id": catalogs[document_id]["catalog_id"],
                    "n_queries": len(query_records),
                    "n_active_queries": len(query_records)
                    - state_counts["both_empty"],
                    "mean_query_drift": statistics.mean(drifts),
                    "max_query_drift": max(drifts),
                    "violation": max(drifts) > QUERY_DRIFT_TAU,
                    "answer_state_counts": {
                        state: state_counts[state]
                        for state in ANSWER_STATES
                    },
                    "queries": query_records,
                }
                per_pair.append(pair_record)
                by_axis[condition].append(pair_record)

        axis_summary = {
            axis: _summarize_axis(by_axis[axis])
            for axis in AXES
        }
        all_toolchain_results[toolchain] = {
            "source_checkpoint": {
                "path": str(checkpoint_paths[toolchain]),
                "bytes": checkpoint_paths[toolchain].stat().st_size,
                "sha256": sha256_file(checkpoint_paths[toolchain]),
                "records": len(records),
            },
            "mapping": _sum_mapping_audits(mapping_audits.values()),
            "execution": {
                "n_endpoints_materialized": len(jobs),
                "n_query_instances": sum(
                    audit["n_queries"] for audit in endpoint_audits
                ),
                "n_answer_sets": sum(
                    audit["n_answer_sets"] for audit in endpoint_audits
                ),
                "n_mismatches": sum(
                    len(audit["mismatches"]) for audit in endpoint_audits
                ),
            },
            "summary": axis_summary,
            "per_pair": sorted(
                per_pair,
                key=lambda record: (
                    record["document_id"],
                    record["axis"],
                ),
            ),
        }

    query_family_counts = Counter()
    for queries in queries_by_document.values():
        query_family_counts.update(family for family, _ in queries)
    catalog_payload = "\n".join(
        catalogs[document_id]["catalog_id"]
        for document_id in sorted(catalogs)
    ).encode("utf-8")
    return {
        "artifact_type": ARTIFACT_TYPE,
        "artifact_version": ARTIFACT_VERSION,
        "source_database": {
            "path": str(db_path),
            "bytes": db_path.stat().st_size,
            "sha256": sha256_file(db_path),
        },
        "protocol": {
            "cohort": (
                "shared first 100 DocRED validation documents; a pair is "
                "excluded only when base or counterfactual extraction failed"
            ),
            "query_workload": (
                "shared gold-instantiated deployment Q1-Q4, constructed "
                "independently of either toolchain's predicted edges"
            ),
            "query_namespace": (
                "benchmark entity identifiers and docred_full relation ids"
            ),
            "entity_linking": (
                "case-insensitive exact match against declared benchmark "
                "canonical names and aliases; ambiguous and unlinked surfaces "
                "remain name keyed"
            ),
            "relation_linking": (
                "declared external rename inversion, then public docred_full "
                "relation label to relation id"
            ),
            "empty_answers": {
                "both_empty_query_drift": 0.0,
                "one_empty_query_drift": 1.0,
                "pairs_filtered_for_empty_answers": False,
            },
            "pair_metric": "maximum Q1-Q4 answer-set Jaccard drift",
            "contract_violation": {
                "metric": "pair maximum query drift",
                "comparator": ">",
                "tau": QUERY_DRIFT_TAU,
                "alpha": 0.20,
            },
            "execution": (
                "actual Kuzu Cypher for every successful endpoint; exact "
                "answer-set parity against graphguard.qa.execute"
            ),
        },
        "query_catalogs": {
            "n_documents": len(catalogs),
            "n_queries": sum(len(queries) for queries in queries_by_document.values()),
            "family_counts": {
                FAMILY_TO_QUERY_ID[family]: query_family_counts[family]
                for family in FAMILY_TO_QUERY_ID
            },
            "catalog_ids_sha256": hashlib.sha256(
                catalog_payload
            ).hexdigest(),
            "catalogs": {
                document_id: catalogs[document_id]
                for document_id in sorted(catalogs)
            },
        },
        "kuzu_version": kuzu_version(),
        "parity": {
            "n_endpoints_materialized": total_materialized,
            "n_query_instances": total_queries,
            "n_answer_sets": total_answer_sets,
            "n_mismatches": len(all_mismatches),
            "mismatches": all_mismatches,
            "status": "pass" if not all_mismatches else "fail",
        },
        "toolchains": all_toolchain_results,
    }


def write_artifact(path: str | Path, artifact: Mapping[str, Any]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            artifact,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
