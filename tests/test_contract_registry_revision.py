from graphguard.contracts import REGISTRY
from graphguard.contracts import metrics as M
from graphguard.contracts.runner import _query_similarity


def _edge(subject, relation, obj, subject_id=None, object_id=None):
    return {
        "subject_name": subject,
        "relation": relation,
        "object_name": obj,
        "subject_entity_id": subject_id,
        "object_entity_id": object_id,
    }


def test_revision_query_contracts_are_registered():
    expected = {
        "K4b": "Q5",
        "K4c": "Q6",
        "K4d": "Q7",
    }
    for contract_id, query_id in expected.items():
        contract = REGISTRY[contract_id]
        assert contract.query_scoped
        assert contract.query_id == query_id
        assert contract.threshold == 0.70
        assert contract.alpha == 0.20


def test_k4_uses_canonical_d3_and_is_order_invariant():
    contract = REGISTRY["K4"]
    assert contract.query_scoped
    assert contract.query_id == "D3"
    assert contract.threshold == 0.70

    base = [
        _edge("A", "r2", "C", "a", "c"),
        _edge("A", "r1", "B", "a", "b"),
        _edge("A", "r3", "D", "a", "d"),
    ]
    counterfactual = [
        _edge("A", "r1", "B", "a", "b"),
        _edge("A", "r2", "C", "a", "c"),
    ]
    expected = _query_similarity(
        base, counterfactual, base_relation_ids=None, query_id="D3"
    )
    assert expected == 1 / 3
    assert expected == _query_similarity(
        list(reversed(base)),
        list(reversed(counterfactual)),
        base_relation_ids=None,
        query_id="D3",
    )


def test_k5_registry_matches_paper_definition():
    contract = REGISTRY["K5"]
    assert contract.metric_fn is M.recall_difference
    assert contract.direction == "max"
    assert contract.threshold == 0.20
    assert contract.alpha == 0.20
    assert contract.needs_gold


def test_identifier_first_pair_canonicalization_with_surface_fallback():
    base = [_edge("United States", "P17", "Paris", "e-us", "e-paris")]
    # The declared alias has no identifier on the counterfactual side. It is
    # still resolved to the base identifier through the paired alias fallback.
    counterfactual = [_edge("the U.S.", "P17", "Paris", None, "e-paris")]
    assert M.edge_jaccard(base, counterfactual, base_relation_ids={"P17"}) == 1.0


def test_k5_gold_recall_prefers_identifiers_and_supports_unlinked_fallback():
    gold = [{
        "head_entity_id": "e-us",
        "head_name": "United States",
        "relation_base": "P17",
        "tail_entity_id": "e-paris",
        "tail_name": "Paris",
    }]
    linked = [_edge("unrelated surface", "P17", "Paris", "e-us", "e-paris")]
    unlinked_alias = [_edge("the U.S.", "P17", "Paris", None, "e-paris")]
    assert M.gold_recall(linked, gold) == 1.0
    assert M.gold_recall(unlinked_alias, gold) == 1.0


def test_registered_revision_queries_execute_on_paired_views():
    base = [
        _edge("A", "r1", "B", "a", "b"),
        _edge("B", "r2", "C", "b", "c"),
        _edge("A", "r3", "D", "a", "d"),
    ]
    same = list(base)
    missing_path = [
        _edge("A", "r3", "D", "a", "d"),
    ]
    for query_id in ("Q5", "Q6", "Q7"):
        assert _query_similarity(
            base, same, base_relation_ids=None, query_id=query_id
        ) == 1.0
    assert _query_similarity(
        base, missing_path, base_relation_ids=None, query_id="Q5"
    ) == 0.0
