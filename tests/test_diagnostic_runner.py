import pytest

from graphguard.diagnostic_runner import (
    cluster_bootstrap_mean,
    evaluate_pair,
    summarize_records,
    validate_authoritative_pairs,
)


def _edge(subject, relation, obj):
    return {
        "subject_entity_id": subject,
        "subject_name": subject,
        "relation": relation,
        "object_entity_id": obj,
        "object_name": obj,
    }


PAIR = {
    "run_id": "run-1",
    "document_id": "doc-1",
    "intervention_id": "iv-1",
    "cause_family": "prompt",
    "semantic_class": "presentation",
    "operator": "reorder",
    "base_event_id": "base-1",
    "cf_event_id": "cf-1",
}


def test_validate_authoritative_pairs_accepts_matching_witness():
    audit = validate_authoritative_pairs(
        [PAIR],
        {"base-1": "doc-1", "cf-1": "doc-1"},
        {"run-1": [("edge-1", "cf-1")]},
    )
    assert audit["n_pairs"] == 1
    assert audit["n_pairs_with_matched_edge_witness"] == 1
    assert audit["witness_mismatches"] == 0


def test_validate_authoritative_pairs_rejects_witness_mismatch():
    with pytest.raises(ValueError, match="disagrees"):
        validate_authoritative_pairs(
            [PAIR],
            {"base-1": "doc-1", "cf-1": "doc-1", "wrong": "doc-1"},
            {"run-1": [("edge-1", "wrong")]},
        )


def test_validate_authoritative_pairs_checks_every_witness():
    with pytest.raises(ValueError, match="edge-later-wrong"):
        validate_authoritative_pairs(
            [PAIR],
            {"base-1": "doc-1", "cf-1": "doc-1", "wrong": "doc-1"},
            {
                "run-1": [
                    ("edge-first-correct", "cf-1"),
                    ("edge-later-wrong", "wrong"),
                ]
            },
        )


def test_validate_authoritative_pairs_rejects_missing_witness_edge():
    with pytest.raises(ValueError, match="does not exist"):
        validate_authoritative_pairs(
            [PAIR],
            {"base-1": "doc-1", "cf-1": "doc-1"},
            {"run-1": [("edge-missing", None)]},
        )


def test_validate_authoritative_pairs_rejects_cross_document_endpoint():
    with pytest.raises(ValueError, match="counterfactual event.*doc-2"):
        validate_authoritative_pairs(
            [PAIR],
            {"base-1": "doc-1", "cf-1": "doc-2"},
            {},
        )


def test_evaluate_pair_uses_graph_metric_for_edge_identity():
    base = [_edge("h", "r1", "a"), _edge("h", "r2", "b")]
    counterfactual = [*base, _edge("h", "r3", "c")]
    record = evaluate_pair(
        PAIR,
        base,
        counterfactual,
        base_relation_ids={"r1", "r2", "r3"},
    )

    assert record["graph_jaccard"] == pytest.approx(2 / 3)
    identity = record["queries"]["diagnostic.edge_identity"]
    assert identity["answer_jaccard"] == pytest.approx(
        record["graph_jaccard"]
    )
    assert identity["query_drift"] == pytest.approx(record["graph_drift"])
    fanout = record["queries"]["diagnostic.fanout_join"]
    assert fanout["n_base_answers"] == 1
    assert fanout["n_cf_answers"] == 3
    assert fanout["answer_jaccard"] == pytest.approx(1 / 3)


def test_edge_identity_preserves_bucket_aware_graph_metric():
    base = [_edge("person", "P19", "place")]
    counterfactual = [_edge("person", "person_origin", "place")]
    record = evaluate_pair(
        PAIR,
        base,
        counterfactual,
        base_relation_ids={"P19"},
    )

    identity = record["queries"]["diagnostic.edge_identity"]
    assert record["graph_jaccard"] == 1.0
    assert identity["answer_metric"] == "canonicalized_edge_jaccard"
    assert identity["answer_jaccard"] == 1.0
    assert identity["query_drift"] == 0.0


def test_cluster_bootstrap_is_document_clustered_and_deterministic():
    observations = [
        ("doc-a", 0.0),
        ("doc-a", 1.0),
        ("doc-b", 2.0),
    ]
    first = cluster_bootstrap_mean(
        observations, n_bootstrap=100, seed=7
    )
    second = cluster_bootstrap_mean(
        reversed(observations), n_bootstrap=100, seed=7
    )
    assert first == second
    assert first["n"] == 3
    assert first["n_documents"] == 2
    assert first["mean"] == pytest.approx(1.0)


def test_cluster_bootstrap_resamples_whole_unequal_clusters():
    result = cluster_bootstrap_mean(
        [
            ("doc-large", 0.0),
            ("doc-large", 0.0),
            ("doc-small", 10.0),
        ],
        n_bootstrap=200,
        seed=11,
        alpha=0.2,
    )

    # Whole-document resampling has a 10.0 outcome when doc-small is selected
    # twice. Pair-wise resampling has a different upper-decile distribution.
    assert result["ci_low"] == 0.0
    assert result["ci_high"] == 10.0


def test_summarize_records_keeps_all_pairs_and_groups():
    base = [_edge("h", "r1", "a"), _edge("h", "r2", "b")]
    counterfactual = [*base, _edge("h", "r3", "c")]
    first = evaluate_pair(
        PAIR,
        base,
        counterfactual,
        base_relation_ids={"r1", "r2", "r3"},
    )
    second_pair = {
        **PAIR,
        "run_id": "run-2",
        "document_id": "doc-2",
        "cause_family": "schema",
        "semantic_class": "semantic",
    }
    second = evaluate_pair(
        second_pair,
        base,
        base,
        base_relation_ids={"r1", "r2", "r3"},
    )
    summary = summarize_records(
        [first, second],
        n_bootstrap=100,
        seed=3,
    )
    result = summary["diagnostic.fanout_join"]
    assert result["n"] == 2
    assert result["n_documents"] == 2
    assert set(result["by_cause_family"]) == {"prompt", "schema"}
    assert set(result["by_semantic_class"]) == {
        "presentation", "semantic"
    }
