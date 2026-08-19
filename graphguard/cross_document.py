"""BC5CDR joint-context extraction and provenance-aware query utilities.

The primary GraphGuard lineage databases deliberately retain document-local
entity identifiers.  This module reconstructs the BC5CDR MeSH identifiers from
the registered PubTator source and uses them only in an isolated, hash-bound
cross-document experiment.  Historical lineage databases are never migrated.
"""

from __future__ import annotations

import gc
import hashlib
import json
import random
import shutil
import sqlite3
import statistics
import tempfile
from collections import defaultdict
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path
from typing import Iterable, Mapping, Sequence

from graphguard.data.load_cdr import (
    _char_span_to_token_span,
    _parse_pubtator,
    _sent_split,
    _tokenize,
)
from graphguard.qa import f1, jaccard


DESIGN_ID = "graphguard-cross-document-cdr-20260811"
CONDITIONS = (
    "joint_ab_seed7",
    "joint_ba_seed7",
    "joint_ab_seed13",
)
QUERY_FAMILIES = ("crossdoc_fanout", "crossdoc_shared_tail")


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_digest(value: object) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _read_json(path: str | Path) -> dict:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _readonly_connection(path: str | Path) -> sqlite3.Connection:
    connection = sqlite3.connect(
        f"file:{Path(path).resolve()}?mode=ro",
        uri=True,
    )
    connection.row_factory = sqlite3.Row
    return connection


def _entity_number(entity_id: str) -> int:
    try:
        return int(entity_id.rsplit("::e", 1)[1])
    except (IndexError, ValueError) as exc:
        raise ValueError(f"unexpected CDR entity identifier: {entity_id}") from exc


def _loader_visible_mesh_clusters(raw_document: Mapping) -> list[str]:
    """Reproduce the current loader's accepted mention and cluster order."""
    sentence_spans = _sent_split(str(raw_document["text"]))
    sentence_tokens = [
        _tokenize(sentence_text)
        for _, _, sentence_text in sentence_spans
    ]
    ordered: list[str] = []
    seen: set[str] = set()
    for start, end, _text, _entity_type, mesh_field in raw_document["mentions"]:
        token_span = _char_span_to_token_span(
            int(start),
            int(end),
            sentence_spans,
            sentence_tokens,
        )
        if token_span is None:
            continue
        for mesh_id in str(mesh_field).split("|"):
            if not mesh_id or mesh_id == "-1" or mesh_id in seen:
                continue
            seen.add(mesh_id)
            ordered.append(mesh_id)
    return ordered


@dataclass(frozen=True)
class CDRInputs:
    document_ids: tuple[str, ...]
    documents: dict[str, dict]
    local_to_mesh: dict[str, str]
    mesh_registry: dict[str, dict]
    gold_by_document: dict[str, frozenset[tuple[str, str, str, str]]]
    base_by_document: dict[str, frozenset[tuple[str, str, str, str]]]
    base_event_by_document: dict[str, str]
    mapping_audit: dict


def load_cdr_inputs(
    *,
    raw_path: str | Path,
    db_path: str | Path,
    samples_path: str | Path,
    run_id: str = "cdr__deepseek-v4-flash__300d",
) -> CDRInputs:
    """Load the registered 300-document CDR slice and recover MeSH keys."""
    sample_manifest = _read_json(samples_path)
    try:
        sampled_ids = tuple(sample_manifest["runs"][run_id]["document_ids"])
    except (KeyError, TypeError) as exc:
        raise ValueError(f"sample manifest has no run {run_id}") from exc
    if len(sampled_ids) != len(set(sampled_ids)):
        raise ValueError("sample manifest contains duplicate CDR documents")

    raw_documents = list(_parse_pubtator(Path(raw_path)))
    if len(raw_documents) < len(sampled_ids):
        raise ValueError("raw CDR source is shorter than the registered sample")

    connection = _readonly_connection(db_path)
    try:
        document_rows = {
            row["document_id"]: dict(row)
            for row in connection.execute(
                "SELECT document_id, title, raw_text, split FROM documents "
                "ORDER BY document_id"
            )
            if row["document_id"] in sampled_ids
        }
        if set(document_rows) != set(sampled_ids):
            missing = sorted(set(sampled_ids) - set(document_rows))
            raise ValueError(f"sampled CDR documents missing from DB: {missing}")

        sentences_by_doc: dict[str, list[dict]] = defaultdict(list)
        for row in connection.execute(
            "SELECT sentence_id, document_id, sentence_index, text "
            "FROM sentences ORDER BY document_id, sentence_index"
        ):
            if row["document_id"] in document_rows:
                sentences_by_doc[row["document_id"]].append(dict(row))

        entities_by_doc: dict[str, list[dict]] = defaultdict(list)
        for row in connection.execute(
            "SELECT entity_id, document_id, canonical_name, aliases_json, "
            "entity_type FROM entities ORDER BY document_id, entity_id"
        ):
            if row["document_id"] in document_rows:
                item = dict(row)
                item["aliases"] = json.loads(item.pop("aliases_json") or "[]")
                entities_by_doc[row["document_id"]].append(item)

        local_to_mesh: dict[str, str] = {}
        mesh_registry: dict[str, dict] = {}
        documents: dict[str, dict] = {}
        for raw_index, document_id in enumerate(sampled_ids):
            raw_document = raw_documents[raw_index]
            expected_title = str(raw_document["pmid"] or f"cdr_{raw_index}")
            if document_rows[document_id]["title"] != expected_title:
                raise ValueError(
                    f"raw/DB document order mismatch at {raw_index}: "
                    f"{document_id}"
                )
            mesh_ids = _loader_visible_mesh_clusters(raw_document)
            entities = sorted(
                entities_by_doc[document_id],
                key=lambda row: _entity_number(row["entity_id"]),
            )
            if len(mesh_ids) != len(entities):
                raise ValueError(
                    f"raw/DB entity count mismatch for {document_id}: "
                    f"{len(mesh_ids)} != {len(entities)}"
                )
            for entity, mesh_id in zip(entities, mesh_ids):
                local_to_mesh[entity["entity_id"]] = mesh_id
                registry = mesh_registry.setdefault(
                    mesh_id,
                    {
                        "mesh_id": mesh_id,
                        "types": set(),
                        "names": set(),
                        "documents": set(),
                    },
                )
                if entity.get("entity_type"):
                    registry["types"].add(entity["entity_type"])
                registry["names"].add(entity["canonical_name"])
                registry["names"].update(entity["aliases"])
                registry["documents"].add(document_id)
                entity["mesh_id"] = mesh_id
            documents[document_id] = {
                **document_rows[document_id],
                "sentences": sentences_by_doc[document_id],
                "entities": entities,
            }

        gold_by_document: dict[
            str, set[tuple[str, str, str, str]]
        ] = defaultdict(set)
        unmapped_gold = 0
        for row in connection.execute(
            "SELECT document_id, head_entity_id, relation_base, tail_entity_id "
            "FROM gold_edges ORDER BY rowid"
        ):
            document_id = row["document_id"]
            if document_id not in document_rows:
                continue
            head = local_to_mesh.get(row["head_entity_id"])
            tail = local_to_mesh.get(row["tail_entity_id"])
            if head is None or tail is None:
                unmapped_gold += 1
                continue
            gold_by_document[document_id].add(
                (head, row["relation_base"], tail, document_id)
            )

        ranked_base_events = connection.execute(
            """
            WITH ranked AS (
              SELECT document_id, base_event_id, created_at, run_id,
                     ROW_NUMBER() OVER (
                       PARTITION BY document_id
                       ORDER BY created_at DESC, run_id DESC
                     ) AS row_number
              FROM counterfactual_runs
              WHERE status = 'ok' AND base_event_id IS NOT NULL
            )
            SELECT document_id, base_event_id
            FROM ranked WHERE row_number = 1
            ORDER BY document_id
            """
        ).fetchall()
        base_event_by_document = {
            row["document_id"]: row["base_event_id"]
            for row in ranked_base_events
            if row["document_id"] in document_rows
        }
        if set(base_event_by_document) != set(sampled_ids):
            missing = sorted(set(sampled_ids) - set(base_event_by_document))
            raise ValueError(f"CDR documents without registered base event: {missing}")

        event_ids = tuple(sorted(set(base_event_by_document.values())))
        placeholders = ",".join("?" for _ in event_ids)
        base_by_document: dict[
            str, set[tuple[str, str, str, str]]
        ] = defaultdict(set)
        base_rows = 0
        mapped_base_rows = 0
        for row in connection.execute(
            "SELECT event_id, document_id, subject_entity_id, relation, "
            "object_entity_id FROM extracted_edges "
            f"WHERE event_id IN ({placeholders}) ORDER BY rowid",
            event_ids,
        ):
            base_rows += 1
            subject = local_to_mesh.get(row["subject_entity_id"])
            obj = local_to_mesh.get(row["object_entity_id"])
            if subject is None or obj is None or not row["relation"]:
                continue
            mapped_base_rows += 1
            base_by_document[row["document_id"]].add(
                (subject, row["relation"], obj, row["document_id"])
            )
    finally:
        connection.close()

    serial_registry = {
        mesh_id: {
            "mesh_id": mesh_id,
            "types": sorted(item["types"]),
            "names": sorted(name for name in item["names"] if name),
            "documents": sorted(item["documents"]),
        }
        for mesh_id, item in mesh_registry.items()
    }
    repeated = sum(
        len(item["documents"]) >= 2 for item in serial_registry.values()
    )
    documents_with_repeated = sum(
        any(
            len(serial_registry[entity["mesh_id"]]["documents"]) >= 2
            for entity in documents[document_id]["entities"]
        )
        for document_id in sampled_ids
    )
    mapping_audit = {
        "n_documents": len(sampled_ids),
        "n_local_entities": len(local_to_mesh),
        "n_unique_mesh_ids": len(serial_registry),
        "n_repeated_mesh_ids": repeated,
        "n_documents_with_repeated_mesh": documents_with_repeated,
        "unmapped_gold_rows": unmapped_gold,
        "base_edge_rows": base_rows,
        "mapped_base_edge_rows": mapped_base_rows,
        "base_edge_mapping_rate": (
            mapped_base_rows / base_rows if base_rows else 0.0
        ),
        "base_event_ids_sha256": canonical_digest(base_event_by_document),
    }
    return CDRInputs(
        document_ids=sampled_ids,
        documents=documents,
        local_to_mesh=local_to_mesh,
        mesh_registry=serial_registry,
        gold_by_document={
            document_id: frozenset(gold_by_document[document_id])
            for document_id in sampled_ids
        },
        base_by_document={
            document_id: frozenset(base_by_document[document_id])
            for document_id in sampled_ids
        },
        base_event_by_document=base_event_by_document,
        mapping_audit=mapping_audit,
    )


def execute_cross_document_query(
    edges: Iterable[tuple[str, str, str, str]],
    family: str,
) -> set[tuple[str, str, str]]:
    """Execute one source-document-constrained query over a packet graph."""
    cid_edges = sorted(
        set(edge for edge in edges if len(edge) == 4 and edge[1] == "CID")
    )
    answers: set[tuple[str, str, str]] = set()
    if family == "crossdoc_fanout":
        by_head: dict[str, list[tuple[str, str]]] = defaultdict(list)
        for head, _relation, tail, source_document in cid_edges:
            by_head[head].append((tail, source_document))
        for head, branches in by_head.items():
            for first, second in combinations(branches, 2):
                tail_a, document_a = first
                tail_b, document_b = second
                if document_a == document_b or tail_a == tail_b:
                    continue
                disease_a, disease_b = sorted((tail_a, tail_b))
                answers.add((head, disease_a, disease_b))
        return answers
    if family == "crossdoc_shared_tail":
        by_tail: dict[str, list[tuple[str, str]]] = defaultdict(list)
        for head, _relation, tail, source_document in cid_edges:
            by_tail[tail].append((head, source_document))
        for tail, branches in by_tail.items():
            for first, second in combinations(branches, 2):
                head_a, document_a = first
                head_b, document_b = second
                if document_a == document_b or head_a == head_b:
                    continue
                chemical_a, chemical_b = sorted((head_a, head_b))
                answers.add((chemical_a, chemical_b, tail))
        return answers
    raise KeyError(f"unknown cross-document query family: {family}")


def localize_edges(
    edges: Iterable[tuple[str, str, str, str]],
) -> set[tuple[str, str, str, str]]:
    """Document-scope entity keys for the no-global-link negative control."""
    return {
        (
            f"{source_document}::{subject}",
            relation,
            f"{source_document}::{obj}",
            source_document,
        )
        for subject, relation, obj, source_document in edges
    }


def build_cross_document_cohort(
    inputs: CDRInputs,
    *,
    n_packets: int = 100,
) -> list[dict]:
    """Select output-independent, document-disjoint cross-document packets."""
    candidates: list[dict] = []
    for document_a, document_b in combinations(inputs.document_ids, 2):
        gold_edges = set(inputs.gold_by_document[document_a]) | set(
            inputs.gold_by_document[document_b]
        )
        answers = {
            family: sorted(execute_cross_document_query(gold_edges, family))
            for family in QUERY_FAMILIES
        }
        if not any(answers.values()):
            continue
        rank = canonical_digest(
            [DESIGN_ID, document_a, document_b, "cohort-rank"]
        )
        candidates.append(
            {
                "rank": rank,
                "documents": [document_a, document_b],
                "gold_answers": answers,
            }
        )
    candidates.sort(key=lambda item: (item["rank"], item["documents"]))

    selected: list[dict] = []
    used_documents: set[str] = set()
    for candidate in candidates:
        if any(doc in used_documents for doc in candidate["documents"]):
            continue
        packet_id = "packet-" + canonical_digest(
            [DESIGN_ID, *candidate["documents"]]
        )[:12]
        selected.append(
            {
                "packet_id": packet_id,
                "documents": candidate["documents"],
                "rank": candidate["rank"],
                "gold_answers": candidate["gold_answers"],
                "active_queries": [
                    family
                    for family in QUERY_FAMILIES
                    if candidate["gold_answers"][family]
                ],
                "base_event_ids": {
                    document_id: inputs.base_event_by_document[document_id]
                    for document_id in candidate["documents"]
                },
            }
        )
        used_documents.update(candidate["documents"])
        if len(selected) == n_packets:
            break
    if len(selected) != n_packets:
        raise ValueError(
            f"only {len(selected)} disjoint cross-document packets are "
            f"available; requested {n_packets}"
        )
    return selected


def packet_edges(
    inputs: CDRInputs,
    packet: Mapping,
    *,
    source: str,
) -> set[tuple[str, str, str, str]]:
    if source == "gold":
        by_document = inputs.gold_by_document
    elif source == "cached_base":
        by_document = inputs.base_by_document
    else:
        raise KeyError(source)
    return set().union(
        *(by_document[document_id] for document_id in packet["documents"])
    )


def render_joint_prompt(
    inputs: CDRInputs,
    packet: Mapping,
    *,
    order: str,
) -> str:
    """Render one joint prompt; only document block order changes AB vs BA."""
    if order not in {"ab", "ba"}:
        raise ValueError(order)
    document_ids = list(packet["documents"])
    if order == "ba":
        document_ids.reverse()
    packet_mesh = sorted(
        {
            entity["mesh_id"]
            for document_id in packet["documents"]
            for entity in inputs.documents[document_id]["entities"]
        }
    )
    registry_lines = []
    for mesh_id in packet_mesh:
        registry = inputs.mesh_registry[mesh_id]
        names = "; ".join(registry["names"])
        types = "/".join(registry["types"])
        present = ", ".join(
            doc for doc in registry["documents"] if doc in packet["documents"]
        )
        registry_lines.append(
            f"- {mesh_id} | type={types} | names={names} | documents={present}"
        )
    document_blocks = []
    for document_id in document_ids:
        sentences = inputs.documents[document_id]["sentences"]
        rendered = "\n".join(
            f"[{index}] {sentence['text']}"
            for index, sentence in enumerate(sentences, start=1)
        )
        document_blocks.append(
            f"### Document {document_id}\n{rendered}"
        )
    return f"""You are an information extraction system. Extract typed entity-pair relations from both documents in one joint pass.

## Instructions
- Extract only relations explicitly supported by sentences in the source document recorded for that edge.
- A strongly implied relation is allowed, but cite the best supporting sentence IDs from that source document.
- Use only the declared MeSH IDs and relation types. Do not invent identifiers or relation types.
- CID is directed from a Chemical to a Disease. Use OTHER only for an explicitly supported relation that does not fit CID.
- Preserve evidence provenance: every edge must name exactly one source document and its 1-based sentence IDs.
- Return strictly valid JSON and no prose or markdown.

## Relation schema
- CID (chemical_induces_disease): the Chemical induces, causes, or is associated with onset of the Disease.
- OTHER: an explicitly supported entity-pair relation that does not fit CID.

## Global MeSH entity registry
{chr(10).join(registry_lines)}

## Documents
{chr(10).join(document_blocks)}

## Response JSON schema
{{
  "edges": [
    {{
      "subject_mesh_id": "<declared MeSH ID>",
      "relation": "CID or OTHER",
      "object_mesh_id": "<declared MeSH ID>",
      "source_document_id": "<one document ID above>",
      "evidence_sentence_ids": [1],
      "confidence": 0.0
    }}
  ]
}}

Return JSON only.
"""


def normalize_joint_response(
    parsed: object,
    inputs: CDRInputs,
    packet: Mapping,
) -> tuple[set[tuple[str, str, str, str]], dict]:
    """Fail closed on undeclared IDs, provenance, relation, and evidence."""
    audit = {
        "raw_edges": 0,
        "accepted_edges": 0,
        "invalid_shape": 0,
        "undeclared_entity": 0,
        "invalid_relation": 0,
        "invalid_provenance": 0,
        "invalid_evidence": 0,
        "invalid_cid_direction": 0,
    }
    if not isinstance(parsed, dict) or not isinstance(parsed.get("edges"), list):
        audit["invalid_shape"] += 1
        return set(), audit
    allowed_documents = set(packet["documents"])
    entities_by_document = {
        document_id: {
            entity["mesh_id"]: entity
            for entity in inputs.documents[document_id]["entities"]
        }
        for document_id in allowed_documents
    }
    accepted: set[tuple[str, str, str, str]] = set()
    for raw_edge in parsed["edges"]:
        audit["raw_edges"] += 1
        if not isinstance(raw_edge, dict):
            audit["invalid_shape"] += 1
            continue
        subject = str(raw_edge.get("subject_mesh_id", "")).strip()
        obj = str(raw_edge.get("object_mesh_id", "")).strip()
        relation = str(raw_edge.get("relation", "")).strip().upper()
        source_document = str(
            raw_edge.get("source_document_id", "")
        ).strip()
        if source_document not in allowed_documents:
            audit["invalid_provenance"] += 1
            continue
        source_entities = entities_by_document[source_document]
        if subject not in source_entities or obj not in source_entities:
            audit["undeclared_entity"] += 1
            continue
        if relation not in {"CID", "OTHER"}:
            audit["invalid_relation"] += 1
            continue
        evidence = raw_edge.get("evidence_sentence_ids")
        sentence_count = len(inputs.documents[source_document]["sentences"])
        if (
            not isinstance(evidence, list)
            or not evidence
            or any(
                not isinstance(index, int)
                or isinstance(index, bool)
                or index < 1
                or index > sentence_count
                for index in evidence
            )
        ):
            audit["invalid_evidence"] += 1
            continue
        if relation == "CID":
            subject_types = {source_entities[subject].get("entity_type")}
            object_types = {source_entities[obj].get("entity_type")}
            if "Chemical" not in subject_types or "Disease" not in object_types:
                audit["invalid_cid_direction"] += 1
                continue
        accepted.add((subject, relation, obj, source_document))
    audit["accepted_edges"] = len(accepted)
    return accepted, audit


class CrossDocumentKuzuGraph:
    """One Kuzu materialization for a packet-indexed provenance graph."""

    def __init__(
        self,
        edges_by_packet: Mapping[
            str, Iterable[tuple[str, str, str, str]]
        ],
    ):
        import kuzu

        self._directory = Path(tempfile.mkdtemp(prefix="graphguard-crossdoc-"))
        self._database = None
        self.connection = None
        try:
            self._database = kuzu.Database(str(self._directory / "db"))
            self.connection = kuzu.Connection(self._database)
            self.connection.execute(
                "CREATE NODE TABLE Entity(key STRING, packet STRING, "
                "mesh STRING, PRIMARY KEY(key))"
            )
            self.connection.execute(
                "CREATE REL TABLE Rel(FROM Entity TO Entity, label STRING, "
                "packet STRING, source_document STRING)"
            )
            materialized = []
            for packet_id, edges in sorted(edges_by_packet.items()):
                for subject, relation, obj, source_document in sorted(set(edges)):
                    materialized.append(
                        (packet_id, subject, relation, obj, source_document)
                    )
            nodes = sorted(
                {
                    (packet_id, node)
                    for packet_id, subject, _relation, obj, _source in materialized
                    for node in (subject, obj)
                }
            )
            for packet_id, mesh_id in nodes:
                key = f"{packet_id}\x1f{mesh_id}"
                self.connection.execute(
                    "CREATE (e:Entity {key:$key, packet:$packet, mesh:$mesh})",
                    parameters={
                        "key": key,
                        "packet": packet_id,
                        "mesh": mesh_id,
                    },
                )
            for packet_id, subject, relation, obj, source_document in materialized:
                self.connection.execute(
                    "MATCH (a:Entity {key:$subject}), (b:Entity {key:$object}) "
                    "CREATE (a)-[:Rel {label:$label, packet:$packet, "
                    "source_document:$source_document}]->(b)",
                    parameters={
                        "subject": f"{packet_id}\x1f{subject}",
                        "object": f"{packet_id}\x1f{obj}",
                        "label": relation,
                        "packet": packet_id,
                        "source_document": source_document,
                    },
                )
        except BaseException:
            self.close()
            raise

    def execute(self, packet_id: str, family: str) -> set[tuple[str, str, str]]:
        if family == "crossdoc_fanout":
            result = self.connection.execute(
                "MATCH (h:Entity)-[e1:Rel]->(d1:Entity), "
                "(h)-[e2:Rel]->(d2:Entity) "
                "WHERE h.packet=$packet AND e1.packet=$packet "
                "AND e2.packet=$packet AND e1.label='CID' "
                "AND e2.label='CID' "
                "AND e1.source_document <> e2.source_document "
                "AND d1.mesh < d2.mesh "
                "RETURN DISTINCT h.mesh, d1.mesh, d2.mesh",
                parameters={"packet": packet_id},
            )
            return {tuple(row) for row in result}
        if family == "crossdoc_shared_tail":
            result = self.connection.execute(
                "MATCH (c1:Entity)-[e1:Rel]->(d:Entity), "
                "(c2:Entity)-[e2:Rel]->(d) "
                "WHERE d.packet=$packet AND e1.packet=$packet "
                "AND e2.packet=$packet AND e1.label='CID' "
                "AND e2.label='CID' "
                "AND e1.source_document <> e2.source_document "
                "AND c1.mesh < c2.mesh "
                "RETURN DISTINCT c1.mesh, c2.mesh, d.mesh",
                parameters={"packet": packet_id},
            )
            return {tuple(row) for row in result}
        raise KeyError(family)

    def close(self) -> None:
        if getattr(self, "connection", None) is not None:
            del self.connection
        if getattr(self, "_database", None) is not None:
            del self._database
        gc.collect()
        shutil.rmtree(self._directory, ignore_errors=True)

    def __enter__(self) -> "CrossDocumentKuzuGraph":
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()


def _percentile(values: Sequence[float], probability: float) -> float:
    if not values:
        raise ValueError("cannot take percentile of an empty sample")
    ordered = sorted(values)
    index = (len(ordered) - 1) * probability
    low = int(index)
    high = min(low + 1, len(ordered) - 1)
    fraction = index - low
    return ordered[low] * (1 - fraction) + ordered[high] * fraction


def bootstrap_mean_ci(
    values: Sequence[float],
    *,
    draws: int = 10_000,
    seed: int = 20260811,
) -> list[float]:
    if not values:
        return [0.0, 0.0]
    if len(values) == 1:
        return [float(values[0]), float(values[0])]
    rng = random.Random(seed)
    samples = []
    for _ in range(draws):
        samples.append(
            statistics.mean(rng.choice(values) for _ in range(len(values)))
        )
    return [_percentile(samples, 0.025), _percentile(samples, 0.975)]


def graph_drifts(
    base_edges: set[tuple[str, str, str, str]],
    changed_edges: set[tuple[str, str, str, str]],
) -> tuple[float, float]:
    semantic_base = {(s, r, o) for s, r, o, _doc in base_edges}
    semantic_changed = {(s, r, o) for s, r, o, _doc in changed_edges}
    return (
        1.0 - jaccard(semantic_base, semantic_changed),
        1.0 - jaccard(base_edges, changed_edges),
    )


def macro_query_metrics(
    edges: set[tuple[str, str, str, str]],
    gold_edges: set[tuple[str, str, str, str]],
) -> dict:
    per_family = {}
    active_precision = []
    active_recall = []
    active_f1 = []
    for family in QUERY_FAMILIES:
        predicted = execute_cross_document_query(edges, family)
        gold = execute_cross_document_query(gold_edges, family)
        true_positive = len(predicted & gold)
        precision = true_positive / len(predicted) if predicted else 0.0
        recall = true_positive / len(gold) if gold else 0.0
        score = f1(predicted, gold)
        per_family[family] = {
            "answers": sorted(predicted),
            "gold_answers": sorted(gold),
            "active": bool(gold),
            "precision": precision,
            "recall": recall,
            "f1": score,
        }
        if gold:
            active_precision.append(precision)
            active_recall.append(recall)
            active_f1.append(score)
    return {
        "macro_precision": (
            statistics.mean(active_precision) if active_precision else 0.0
        ),
        "macro_recall": (
            statistics.mean(active_recall) if active_recall else 0.0
        ),
        "macro_f1": statistics.mean(active_f1) if active_f1 else 0.0,
        "active_query_families": len(active_f1),
        "per_family": per_family,
    }


def graph_quality(
    edges: set[tuple[str, str, str, str]],
    gold_edges: set[tuple[str, str, str, str]],
) -> dict:
    semantic = {(s, r, o) for s, r, o, _doc in edges}
    gold_semantic = {(s, r, o) for s, r, o, _doc in gold_edges}
    return {
        "semantic_f1": f1(semantic, gold_semantic),
        "provenance_f1": f1(edges, gold_edges),
    }


def query_drift(
    base_edges: set[tuple[str, str, str, str]],
    changed_edges: set[tuple[str, str, str, str]],
    gold_edges: set[tuple[str, str, str, str]],
) -> dict:
    per_family = {}
    active = []
    for family in QUERY_FAMILIES:
        gold = execute_cross_document_query(gold_edges, family)
        base = execute_cross_document_query(base_edges, family)
        changed = execute_cross_document_query(changed_edges, family)
        drift = 1.0 - jaccard(base, changed)
        per_family[family] = {
            "active": bool(gold),
            "base_answers": sorted(base),
            "changed_answers": sorted(changed),
            "drift": drift,
            "both_empty": not base and not changed,
        }
        if gold:
            active.append(drift)
    return {
        "max_active_drift": max(active) if active else 0.0,
        "mean_active_drift": statistics.mean(active) if active else 0.0,
        "per_family": per_family,
    }


def summarize_records(per_packet: Sequence[dict]) -> dict:
    """Aggregate packet-level records without treating queries as IID rows."""
    comparisons = {}
    for label in ("order", "seed"):
        records = [packet["comparisons"][label] for packet in per_packet]
        comparisons[label] = {}
        for metric in (
            "semantic_graph_drift",
            "provenance_graph_drift",
            "max_query_drift",
            "mean_query_drift",
        ):
            values = [float(record[metric]) for record in records]
            comparisons[label][metric] = {
                "mean": statistics.mean(values),
                "median": statistics.median(values),
                "ci95": bootstrap_mean_ci(values),
            }
        comparisons[label]["graph_violation_rate_tau_0.20"] = statistics.mean(
            record["provenance_graph_drift"] > 0.20 for record in records
        )
        comparisons[label]["query_violation_rate_tau_0.30"] = statistics.mean(
            record["max_query_drift"] > 0.30 for record in records
        )
        comparisons[label]["per_family"] = {}
        for family in QUERY_FAMILIES:
            active_records = [
                record["per_family"][family]
                for record in records
                if record["per_family"][family]["active"]
            ]
            family_drifts = [
                float(record["drift"]) for record in active_records
            ]
            comparisons[label]["per_family"][family] = {
                "n_active_packets": len(active_records),
                "mean_drift": (
                    statistics.mean(family_drifts) if family_drifts else 0.0
                ),
                "ci95": (
                    bootstrap_mean_ci(family_drifts, seed=20260814)
                    if family_drifts else [0.0, 0.0]
                ),
                "both_empty_rate": (
                    statistics.mean(record["both_empty"] for record in active_records)
                    if active_records else 0.0
                ),
            }

    excess = {}
    for metric in (
        "semantic_graph_drift",
        "provenance_graph_drift",
        "max_query_drift",
        "mean_query_drift",
    ):
        values = [
            float(packet["comparisons"]["order"][metric])
            - float(packet["comparisons"]["seed"][metric])
            for packet in per_packet
        ]
        excess[metric] = {
            "mean": statistics.mean(values),
            "median": statistics.median(values),
            "ci95": bootstrap_mean_ci(values, seed=20260812),
        }

    quality = {}
    for condition in ("cached_union", *CONDITIONS):
        query_records = [
            packet["conditions"][condition]["query_quality"]
            for packet in per_packet
        ]
        graph_records = [
            packet["conditions"][condition]["graph_quality"]
            for packet in per_packet
        ]
        values = [float(record["macro_f1"]) for record in query_records]
        quality[condition] = {
            "mean_macro_query_precision": statistics.mean(
                float(record["macro_precision"]) for record in query_records
            ),
            "mean_macro_query_recall": statistics.mean(
                float(record["macro_recall"]) for record in query_records
            ),
            "mean_macro_query_f1": statistics.mean(values),
            "ci95": bootstrap_mean_ci(values, seed=20260813),
            "mean_semantic_graph_f1": statistics.mean(
                float(record["semantic_f1"]) for record in graph_records
            ),
            "mean_provenance_graph_f1": statistics.mean(
                float(record["provenance_f1"]) for record in graph_records
            ),
            "per_family": {},
        }
        for family in QUERY_FAMILIES:
            active_records = [
                record["per_family"][family]
                for record in query_records
                if record["per_family"][family]["active"]
            ]
            quality[condition]["per_family"][family] = {
                "n_active_packets": len(active_records),
                "nonempty_answer_rate": (
                    statistics.mean(bool(record["answers"]) for record in active_records)
                    if active_records else 0.0
                ),
                "mean_precision": (
                    statistics.mean(record["precision"] for record in active_records)
                    if active_records else 0.0
                ),
                "mean_recall": (
                    statistics.mean(record["recall"] for record in active_records)
                    if active_records else 0.0
                ),
                "mean_f1": (
                    statistics.mean(record["f1"] for record in active_records)
                    if active_records else 0.0
                ),
            }
    paired_quality_difference = [
        float(packet["conditions"]["joint_ab_seed7"]["query_quality"]["macro_f1"])
        - float(packet["conditions"]["cached_union"]["query_quality"]["macro_f1"])
        for packet in per_packet
    ]
    return {
        "n_packets": len(per_packet),
        "comparisons": comparisons,
        "order_minus_seed": excess,
        "query_quality": quality,
        "joint_ab_minus_cached_union_query_f1": {
            "mean": statistics.mean(paired_quality_difference),
            "ci95": bootstrap_mean_ci(
                paired_quality_difference,
                seed=20260815,
            ),
        },
    }
