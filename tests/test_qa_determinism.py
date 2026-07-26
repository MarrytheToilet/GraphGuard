import sqlite3

from graphguard.db.database import _backfill_cf_event_ids
from graphguard.qa import (
    build_queries,
    entity_pair_jaccard,
    graph_jaccard,
    load_data,
)


def test_build_queries_uses_canonical_order_for_capped_families():
    gold = set()
    for index in range(8, -1, -1):
        tail = f"tail-{index}"
        gold.add((f"head-b-{index}", "r", tail))
        gold.add((f"head-a-{index}", "r", tail))
    gold.update({
        ("path-z", "r1", "mid-z"),
        ("mid-z", "r2", "end-z"),
        ("path-a", "r1", "mid-a"),
        ("mid-a", "r2", "end-a"),
    })

    queries = build_queries(gold)
    joins = [params for family, params in queries if family == "join"]
    two_hops = [
        params for family, params in queries if family == "twohop"
    ]

    assert [row["gold"] for row in joins] == [
        {f"tail-{index}"} for index in range(6)
    ]
    assert joins[0]["h1"] == "head-a-0"
    assert joins[0]["h2"] == "head-b-0"
    assert two_hops[0] == {
        "h": "path-a",
        "r1": "r1",
        "r2": "r2",
        "gold": {"end-a"},
    }


def test_graph_jaccard_is_typed_but_canonicalizes_declared_schema_variants():
    base = {("alice", "P17", "france")}

    # A relation flip on the same ordered endpoints is real typed-edge drift.
    flipped = {("alice", "P19", "france")}
    assert entity_pair_jaccard(base, flipped) == 1.0
    assert graph_jaccard(base, flipped) == 0.0

    # The IDs emitted by the declared presentation-only rename and coarse
    # schema variants project back to the base semantic relation.
    renamed = {("alice", "located_in_country", "france")}
    coarse = {("alice", "location", "france")}
    assert graph_jaccard(base, renamed) == 1.0
    assert graph_jaccard(base, coarse) == 1.0


def _qa_connection():
    con = sqlite3.connect(":memory:")
    con.row_factory = sqlite3.Row
    con.executescript(
        """
        CREATE TABLE extracted_edges (
          edge_id TEXT, event_id TEXT, document_id TEXT,
          subject_entity_id TEXT, relation TEXT, object_entity_id TEXT
        );
        CREATE TABLE gold_edges (
          document_id TEXT, head_entity_id TEXT,
          relation_base TEXT, tail_entity_id TEXT
        );
        CREATE TABLE counterfactual_runs (
          run_id TEXT, base_event_id TEXT, cf_event_id TEXT,
          intervention_id TEXT, document_id TEXT, status TEXT
        );
        CREATE TABLE edge_outcomes (
          run_id TEXT, matched_edge_id TEXT
        );
        CREATE TABLE intervention_candidates (
          intervention_id TEXT, cause_family TEXT
        );
        """
    )
    return con


def test_load_data_keeps_empty_cf_graph_and_prefers_matched_event_witness():
    con = _qa_connection()
    con.executemany(
        "INSERT INTO extracted_edges VALUES (?,?,?,?,?,?)",
        [
            ("base::0", "base", "doc", "a", "r", "b"),
            ("right::0", "right", "doc", "a", "r", "c"),
            ("wrong::0", "wrong", "doc", "a", "r", "d"),
        ],
    )
    con.execute(
        "INSERT INTO intervention_candidates VALUES (?,?)", ("iv", "schema")
    )
    con.executemany(
        "INSERT INTO counterfactual_runs VALUES (?,?,?,?,?,?)",
        [
            ("with-match", "base", "wrong", "iv", "doc", "ok"),
            ("empty-cf", "base", "empty", "iv", "doc", "ok"),
        ],
    )
    con.execute(
        "INSERT INTO edge_outcomes VALUES (?,?)", ("with-match", "right::0")
    )

    edges, _, runs = load_data(con)
    by_run = {row[0]: row for row in runs}

    assert by_run["with-match"][2] == "right"
    assert by_run["empty-cf"][2] == "empty"
    assert "empty" in edges
    assert edges["empty"] == set()


def test_cf_event_backfill_repairs_legacy_ambiguity_without_matched_edge_loss():
    con = sqlite3.connect(":memory:")
    con.row_factory = sqlite3.Row
    con.executescript(
        """
        CREATE TABLE extraction_events (
          event_id TEXT, document_id TEXT, schema_id TEXT, prompt_id TEXT,
          model_id TEXT, temperature REAL, seed INTEGER, token_input INTEGER,
          token_output INTEGER, latency_ms INTEGER, created_at TEXT
        );
        CREATE TABLE counterfactual_runs (
          run_id TEXT, document_id TEXT, schema_id TEXT, prompt_id TEXT,
          model_id TEXT, temperature REAL, seed INTEGER, token_input INTEGER,
          token_output INTEGER, latency_ms INTEGER, created_at TEXT,
          cf_event_id TEXT
        );
        CREATE TABLE edge_outcomes (
          run_id TEXT, matched_edge_id TEXT
        );
        """
    )
    common = ("doc", "schema", "prompt", "model", 0.0, 0)
    con.executemany(
        "INSERT INTO extraction_events VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        [
            ("right", *common, 10, 20, 30, "2026-01-01T00:00:01"),
            ("wrong", *common, 11, 21, 31, "2026-01-01T00:00:01"),
            ("empty", *common, 12, 22, 32, "2026-01-01T00:00:01"),
        ],
    )
    con.executemany(
        "INSERT INTO counterfactual_runs VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        [
            (
                "with-match", *common, 10, 20, 30,
                "2026-01-01T00:00:01", "wrong",
            ),
            (
                "without-match", *common, 12, 22, 32,
                "2026-01-01T00:00:01", None,
            ),
        ],
    )
    con.execute(
        "INSERT INTO edge_outcomes VALUES (?,?)", ("with-match", "right::0")
    )

    _backfill_cf_event_ids(con)
    resolved = dict(
        con.execute(
            "SELECT run_id, cf_event_id FROM counterfactual_runs"
        ).fetchall()
    )

    assert resolved == {
        "with-match": "right",
        "without-match": "empty",
    }
