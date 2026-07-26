import pytest

from graphguard.deployment_runner import (
    FAMILY_TO_QUERY_ID,
    build_catalog,
    evaluate_pair,
    summarize_records,
)
from graphguard.deployment_parity import select_pairs
from graphguard.kuzu_executor import KuzuGraph
from graphguard.qa import build_queries, execute


PAIR = {
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
    "base_linked_row_count": 2,
    "cf_linked_row_count": 2,
}


def test_build_queries_merges_join_parameters_before_cap():
    gold = set()
    for index in range(7):
        gold.add((f"a-{index}", "r-left", f"tail-{index}"))
        gold.add((f"b-{index}", "r-right", f"tail-{index}"))
    # A second gold answer for the first parameter tuple must not consume a
    # second cap slot.
    gold.add(("a-0", "r-left", "tail-extra"))
    gold.add(("b-0", "r-right", "tail-extra"))

    joins = [
        query for query in build_queries(gold) if query[0] == "join"
    ]

    assert len(joins) == 6
    assert joins[0][1]["gold"] == {"tail-0", "tail-extra"}
    assert [query[1]["h1"] for query in joins] == [
        f"a-{index}" for index in range(6)
    ]


def test_build_queries_enumerates_all_shared_tail_branch_pairs():
    gold = {
        (f"head-{index}", f"r-{index}", "shared")
        for index in range(4)
    }

    joins = [
        query for query in build_queries(gold) if query[0] == "join"
    ]

    assert len(joins) == 6
    assert {
        (
            query[1]["h1"],
            query[1]["r1"],
            query[1]["h2"],
            query[1]["r2"],
        )
        for query in joins
    } == {
        (
            f"head-{left}",
            f"r-{left}",
            f"head-{right}",
            f"r-{right}",
        )
        for left in range(4)
        for right in range(left + 1, 4)
    }
    assert all(query[1]["gold"] == {"shared"} for query in joins)


def test_build_queries_merges_twohop_parameters_before_cap():
    gold = set()
    for index in range(9):
        gold.add((f"head-{index}", f"r1-{index}", f"mid-{index}"))
        gold.add((f"mid-{index}", "r2", f"tail-{index}"))
    gold.update(
        {
            ("head-0", "r1-0", "mid-extra"),
            ("mid-extra", "r2", "tail-extra"),
        }
    )

    twohop = [
        query for query in build_queries(gold) if query[0] == "twohop"
    ]

    assert len(twohop) == 8
    assert twohop[0][1]["gold"] == {"tail-0", "tail-extra"}
    assert [query[1]["h"] for query in twohop] == [
        f"head-{index}" for index in range(8)
    ]


def test_build_queries_filters_to_base_schema_relations():
    gold = {
        ("a", "declared", "b"),
        ("a", "outside", "c"),
        ("b", "declared", "d"),
    }
    queries = build_queries(gold, allowed_relations={"declared"})

    assert queries
    assert all(
        relation != "outside"
        for _, parameters in queries
        for relation in (
            parameters.get("r"),
            parameters.get("r1"),
            parameters.get("r2"),
        )
    )


def test_catalog_has_unique_stable_query_ids_and_schema_counts():
    gold = {
        ("a", "r", "x"),
        ("b", "r", "x"),
        ("a", "outside", "z"),
    }
    catalog, queries = build_catalog(
        "doc",
        "schema",
        gold,
        {"r"},
    )

    query_ids = [entry["query_id"] for entry in catalog["queries"]]
    assert len(query_ids) == len(set(query_ids))
    assert catalog["raw_gold_edge_count"] == 3
    assert catalog["eligible_gold_edge_count"] == 2
    assert catalog["excluded_gold_edge_count"] == 1
    assert len(queries) == len(query_ids)


def test_pair_aggregation_keeps_empty_answers_and_ineligible_family():
    query = (
        "lookup",
        {"h": "missing", "r": "r", "gold": {"gold-tail"}},
    )
    record = evaluate_pair(
        {**PAIR, "base_linked_row_count": 1},
        base_edges={("a", "r", "b")},
        cf_edges={("a", "r", "c")},
        all_base_edge_count=2,
        all_cf_edge_count=2,
        catalog_id="catalog",
        queries=[query],
    )

    lookup = record["families"]["deployment.lookup"]
    assert lookup["eligible"] is True
    assert lookup["mean_query_drift"] == 0.0
    assert lookup["answer_state_counts"]["both_empty"] == 1
    assert (
        record["families"]["deployment.typed_two_hop"]["eligible"]
        is False
    )
    assert record["base_edge_counts"]["excluded_unlinked_rows"] == 1


def test_summary_is_pair_weighted_and_family_specific():
    first = evaluate_pair(
        PAIR,
        base_edges={("a", "r", "x")},
        cf_edges={("a", "r", "y")},
        all_base_edge_count=1,
        all_cf_edge_count=1,
        catalog_id="catalog",
        queries=[
            ("lookup", {"h": "a", "r": "r", "gold": {"x"}}),
            ("lookup", {"h": "missing", "r": "r", "gold": {"z"}}),
        ],
    )
    second_pair = {
        **PAIR,
        "run_id": "run-2",
        "document_id": "doc-2",
    }
    second = evaluate_pair(
        second_pair,
        base_edges={("a", "r", "x")},
        cf_edges={("a", "r", "x")},
        all_base_edge_count=1,
        all_cf_edge_count=1,
        catalog_id="catalog",
        queries=[
            ("lookup", {"h": "a", "r": "r", "gold": {"x"}}),
        ],
    )

    summary = summarize_records(
        [first, second],
        n_bootstrap=100,
        seed=0,
    )
    lookup = summary["deployment.lookup"]
    assert lookup["n_pairs_total"] == 2
    assert lookup["n_pairs"] == 2
    assert lookup["n_pairs_ineligible"] == 0
    assert lookup["n_query_evaluations"] == 3
    assert lookup["query_drift_mean_per_pair"] == pytest.approx(0.25)
    assert lookup["query_drift_mean_per_instance"] == pytest.approx(1 / 3)
    twohop = summary["deployment.typed_two_hop"]
    assert twohop["status"] == "not_applicable"
    assert twohop["n_pairs_total"] == 2
    assert twohop["n_pairs_ineligible"] == 2


@pytest.mark.parametrize(
    ("query", "edges"),
    [
        (
            ("lookup", {"h": "a'quoted", "r": 'r"quoted', "gold": set()}),
            {("a'quoted", 'r"quoted', "tail")},
        ),
        (
            ("neighbor", {"h": "a", "gold": set()}),
            {("a", "r1", "x"), ("a", "r2", "y")},
        ),
        (
            (
                "join",
                {
                    "h1": "a",
                    "r1": "r1",
                    "h2": "b",
                    "r2": "r2",
                    "gold": set(),
                },
            ),
            {
                ("a", "r1", "x"),
                ("b", "r2", "x"),
                ("a", "r1", "y"),
                ("b", "r2", "y"),
            },
        ),
        (
            (
                "twohop",
                {"h": "a", "r1": "r1", "r2": "r2", "gold": set()},
            ),
            {
                ("a", "r1", "x"),
                ("a", "r1", "y"),
                ("x", "r2", "z"),
                ("y", "r2", "z"),
                ("y", "r2", "w"),
            },
        ),
    ],
)
def test_offline_executor_exactly_matches_kuzu(query, edges):
    expected = execute(edges, query)
    with KuzuGraph(edges) as graph:
        actual = graph.execute(query)
    assert actual == expected


def test_query_catalog_family_mapping_is_complete():
    assert set(FAMILY_TO_QUERY_ID) == {
        "lookup",
        "neighbor",
        "join",
        "twohop",
    }


def test_parity_selection_enforces_min_max_contract():
    with pytest.raises(ValueError, match="cannot exceed"):
        select_pairs([], seed=0, min_pairs=2, max_pairs=1)
    with pytest.raises(ValueError, match="fewer than"):
        select_pairs([], seed=0, min_pairs=1)


def test_parity_selection_covers_rename_and_coarse_variants():
    query = ("lookup", {"h": "a", "r": "r", "gold": {"x"}})
    records = []
    for index, variant in enumerate(("rename", "coarse")):
        pair = {
            **PAIR,
            "run_id": f"run-{index}",
            "target_type": "schema",
            "target_id": variant,
        }
        records.append(
            evaluate_pair(
                pair,
                base_edges={("a", "r", "x")},
                cf_edges={("a", "r", "x")},
                all_base_edge_count=1,
                all_cf_edge_count=1,
                catalog_id="catalog",
                queries=[query],
            )
        )

    selected, audit = select_pairs(
        records,
        seed=0,
        min_pairs=2,
        max_pairs=2,
    )

    assert len(selected) == 2
    assert "schema_variant:rename" in audit["covered_tokens"]
    assert "schema_variant:coarse" in audit["covered_tokens"]
