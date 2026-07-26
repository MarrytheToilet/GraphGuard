import pytest

from graphguard.diagnostic_queries import (
    answer_jaccard,
    edge_identity_answers,
    fanout_join_answers,
    short_connectivity_answers,
    top_undirected_degree_answers,
    two_hop_endpoint_answers,
)


HEAD = "docred-validation-000000-Skai_TV::e0"
BASE = [
    (HEAD, "P131", "docred-validation-000000-Skai_TV::e2"),
    (HEAD, "P361", "docred-validation-000000-Skai_TV::e3"),
    (HEAD, "P463", "docred-validation-000000-Skai_TV::e8"),
    (HEAD, "P17", "docred-validation-000000-Skai_TV::e9"),
]
COUNTERFACTUAL = [
    (HEAD, "P17", "docred-validation-000000-Skai_TV::e9"),
    (HEAD, "P131", "docred-validation-000000-Skai_TV::e2"),
    (HEAD, "P361", "docred-validation-000000-Skai_TV::e3"),
    (HEAD, "P463", "docred-validation-000000-Skai_TV::e8"),
    (HEAD, "P577", "docred-validation-000000-Skai_TV::e4"),
]

def test_edge_identity_preserves_relation_types_and_removes_duplicates():
    triples = [
        ("a", "r1", "b"),
        ("a", "r1", "b"),
        ("a", "r2", "b"),
    ]
    assert edge_identity_answers(triples) == frozenset({
        ("a", "r1", "b"),
        ("a", "r2", "b"),
    })


def test_two_hop_returns_untyped_ordered_endpoints_and_excludes_cycles():
    triples = [
        ("a", "r1", "middle"),
        ("a", "direct", "c"),
        ("middle", "r2", "c"),
        ("middle", "r3", "c"),
        ("c", "back", "a"),
    ]
    assert two_hop_endpoint_answers(triples) == frozenset({
        ("a", "c"),
        ("middle", "a"),
        ("c", "middle"),
    })


def test_fanout_join_is_invariant_to_input_order_and_duplicates():
    expected = fanout_join_answers(BASE)
    assert fanout_join_answers(list(reversed(BASE))) == expected
    assert fanout_join_answers([BASE[2], *BASE, BASE[0]]) == expected


def test_fanout_join_never_pairs_branches_from_different_heads():
    other_head = "docred-validation-000000-Skai_TV::e1"
    triples = [
        (HEAD, "P17", "tail-a"),
        (HEAD, "P31", "tail-b"),
        (other_head, "P131", "tail-c"),
        (other_head, "P361", "tail-d"),
    ]

    assert fanout_join_answers(triples) == frozenset({
        (HEAD, ("P17", "tail-a"), ("P31", "tail-b")),
        (other_head, ("P131", "tail-c"), ("P361", "tail-d")),
    })


def test_fanout_join_excludes_same_relation_with_different_tails():
    triples = [
        (HEAD, "P17", "tail-a"),
        (HEAD, "P17", "tail-b"),
        (HEAD, "P31", "tail-c"),
    ]

    assert fanout_join_answers(triples) == frozenset({
        (HEAD, ("P17", "tail-a"), ("P31", "tail-c")),
        (HEAD, ("P17", "tail-b"), ("P31", "tail-c")),
    })


def test_top_undirected_degree_is_simple_and_breaks_ties_canonically():
    triples = [
        ("hub", "r1", "b"),
        ("hub", "r2", "b"),
        ("hub", "r3", "c"),
        ("hub", "r4", "d"),
        ("self", "r5", "self"),
    ]
    assert top_undirected_degree_answers(triples, k=3) == frozenset({
        "hub", "b", "c"
    })
    assert top_undirected_degree_answers(reversed(triples), k=3) == frozenset({
        "hub", "b", "c"
    })


def test_top_undirected_degree_does_not_count_parallel_edges_repeatedly():
    triples = [
        ("a", "r1", "x"),
        ("a", "r2", "y"),
        ("b", "r1", "u"),
        ("b", "r2", "v"),
        ("c", "r1", "w"),
        ("c", "r2", "w"),
        ("c", "r3", "w"),
        ("c", "r4", "w"),
    ]
    assert top_undirected_degree_answers(triples, k=2) == frozenset({
        "a", "b"
    })


def test_top_undirected_degree_retains_self_loop_only_entity_at_degree_zero():
    assert top_undirected_degree_answers(
        [("self", "r", "self")], k=1
    ) == frozenset({"self"})


def test_top_undirected_degree_does_not_count_self_loop_at_cutoff():
    triples = [
        ("a", "loop", "a"),
        ("b", "r", "c"),
    ]
    assert top_undirected_degree_answers(triples, k=2) == frozenset({
        "b", "c"
    })


def test_short_connectivity_is_undirected_unordered_and_bounded_to_two_hops():
    triples = [
        ("center", "r", "a"),
        ("center", "r", "b"),
        ("b", "r", "far"),
        ("far", "r", "outside"),
    ]
    assert short_connectivity_answers(triples) == frozenset({
        ("a", "b"),
        ("a", "center"),
        ("b", "center"),
        ("b", "far"),
        ("center", "far"),
        ("far", "outside"),
        ("b", "outside"),
    })


def test_skai_tv_corrected_fanout_overlap():
    base_answers = fanout_join_answers(BASE)
    counterfactual_answers = fanout_join_answers(COUNTERFACTUAL)

    assert len(base_answers) == 6
    assert len(counterfactual_answers) == 10
    assert base_answers < counterfactual_answers
    assert answer_jaccard(base_answers, counterfactual_answers) == pytest.approx(
        0.6
    )
