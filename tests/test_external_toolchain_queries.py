import json
import sqlite3

import pytest

from graphguard.external_toolchain_queries import (
    DocumentEntityResolver,
    analyze_external_toolchains,
    canonicalize_edges,
    load_checkpoint,
)
from graphguard.qa import execute


class OfflineGraph:
    def __init__(self, edges):
        self.edges = set(edges)

    def execute(self, query):
        return execute(self.edges, query)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return None


def _make_db(path):
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        CREATE TABLE schemas (
          schema_id TEXT PRIMARY KEY,
          relation_types_json TEXT
        );
        CREATE TABLE entities (
          entity_id TEXT PRIMARY KEY,
          document_id TEXT,
          canonical_name TEXT,
          aliases_json TEXT
        );
        CREATE TABLE gold_edges (
          gold_edge_id TEXT PRIMARY KEY,
          document_id TEXT,
          head_entity_id TEXT,
          relation_base TEXT,
          tail_entity_id TEXT
        );
        """
    )
    connection.execute(
        "INSERT INTO schemas VALUES (?, ?)",
        (
            "docred_full",
            json.dumps(
                [
                    {"id": "P1", "label": "relation_one"},
                    {"id": "P2", "label": "relation_two"},
                ]
            ),
        ),
    )
    for document in ("doc-1", "doc-2"):
        for index, name in enumerate(("Alpha", "Beta", "Gamma")):
            connection.execute(
                "INSERT INTO entities VALUES (?, ?, ?, ?)",
                (
                    f"{document}::e{index}",
                    document,
                    name,
                    json.dumps([name, f"{name} alias"]),
                ),
            )
        gold = [
            ("e0", "P1", "e1"),
            ("e1", "P2", "e2"),
        ]
        for index, (head, relation, tail) in enumerate(gold):
            connection.execute(
                "INSERT INTO gold_edges VALUES (?, ?, ?, ?, ?)",
                (
                    f"{document}::g{index}",
                    document,
                    f"{document}::{head}",
                    relation,
                    f"{document}::{tail}",
                ),
            )
    connection.commit()
    connection.close()


def _write_checkpoint(path, changed=False):
    rows = []
    for document in ("doc-1", "doc-2"):
        for condition in (
            "base",
            "schema_reorder",
            "schema_rename",
            "prompt_para",
            "evidence_reorder",
            "resample",
        ):
            edges = [
                ["Alpha", "relation_one", "Beta"],
                ["Beta", "relation_two", "Gamma"],
            ]
            if changed and document == "doc-1" and condition != "base":
                edges = [["Alpha", "relation_one", "Gamma"]]
            rows.append(
                {
                    "doc": document,
                    "condition": condition,
                    "edges": edges,
                }
            )
    path.write_text(
        "".join(json.dumps(row) + "\n" for row in rows),
        encoding="utf-8",
    )


def test_resolver_keeps_ambiguous_and_unlinked_surfaces_name_keyed():
    resolver = DocumentEntityResolver(
        {
            "alpha": {"e1"},
            "alpha alias": {"e1"},
            "shared": {"e2", "e3"},
        }
    )

    assert resolver.resolve("Alpha").status == "exact"
    assert resolver.resolve("Alpha Alias LLC").status == "unlinked"
    assert resolver.resolve("shared").status == "ambiguous"
    assert resolver.resolve("unknown").status == "unlinked"
    assert resolver.resolve("shared").key == "name:shared"


def test_canonicalize_edges_maps_declared_names_and_relation_labels():
    resolver = DocumentEntityResolver(
        {"alpha": {"e1"}, "beta": {"e2"}}
    )
    edges, audit = canonicalize_edges(
        {
            "doc": "doc",
            "condition": "base",
            "edges": [["Alpha", "Relation One", "Beta"]],
        },
        resolver,
        {"relation one": "P1"},
    )

    assert edges == {("e1", "P1", "e2")}
    assert audit["entity_resolution"] == {
        "exact": 2,
        "ambiguous": 0,
        "unlinked": 0,
    }
    assert audit["off_schema_relations"] == 0


def test_canonicalize_edges_inverts_external_schema_rename():
    resolver = DocumentEntityResolver(
        {"alpha": {"e1"}, "beta": {"e2"}}
    )
    edges, audit = canonicalize_edges(
        {
            "doc": "doc",
            "condition": "schema_rename",
            "edges": [["Alpha", "sovereign_state", "Beta"]],
        },
        resolver,
        {"country": "P17"},
    )

    assert edges == {("e1", "P17", "e2")}
    assert audit["off_schema_relations"] == 0


def test_checkpoint_requires_complete_condition_grid(tmp_path):
    path = tmp_path / "cache.jsonl"
    path.write_text(
        json.dumps({"doc": "doc", "condition": "base", "edges": []}) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="non-rectangular"):
        load_checkpoint(path)


def test_shared_catalog_pair_aggregation_and_parity(tmp_path):
    db = tmp_path / "source.db"
    _make_db(db)
    langchain = tmp_path / "langchain.jsonl"
    neo4j = tmp_path / "neo4j.jsonl"
    _write_checkpoint(langchain, changed=True)
    _write_checkpoint(neo4j, changed=False)

    artifact = analyze_external_toolchains(
        db_path=db,
        checkpoints={"langchain": langchain, "neo4j": neo4j},
        graph_factory=OfflineGraph,
    )

    assert artifact["parity"]["status"] == "pass"
    assert artifact["query_catalogs"]["n_documents"] == 2
    assert artifact["query_catalogs"]["n_queries"] > 0
    assert (
        artifact["toolchains"]["langchain"]["summary"]["schema_reorder"][
            "n_pairs"
        ]
        == 2
    )
    assert (
        artifact["toolchains"]["langchain"]["summary"]["schema_reorder"][
            "violation_rate"
        ]
        == pytest.approx(0.5)
    )
    assert (
        artifact["toolchains"]["neo4j"]["summary"]["schema_reorder"][
            "violation_rate"
        ]
        == 0.0
    )
    assert all(
        record["query_catalog_id"]
        == artifact["query_catalogs"]["catalogs"][record["document_id"]][
            "catalog_id"
        ]
        for result in artifact["toolchains"].values()
        for record in result["per_pair"]
    )
