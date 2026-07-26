from graphguard.query_catalog import (
    ALL_QUERIES,
    DIAGNOSTIC_QUERIES,
    by_legacy_artifact_id,
    by_paper_id,
)


def test_paper_ids_are_unique_and_cover_q1_to_q7():
    paper_ids = [spec.paper_id for spec in ALL_QUERIES if spec.paper_id]
    assert paper_ids == [f"Q{i}" for i in range(1, 8)]
    assert len(paper_ids) == len(set(paper_ids))


def test_legacy_ids_are_provenance_aliases_not_paper_ids():
    assert all(spec.paper_id is None for spec in DIAGNOSTIC_QUERIES)
    assert by_legacy_artifact_id("Q3_join").canonical_id == (
        "diagnostic.fanout_join"
    )
    assert by_legacy_artifact_id("Q5_short_paths").canonical_id == (
        "diagnostic.short_connectivity"
    )


def test_same_join_word_does_not_collapse_distinct_semantics():
    assert by_paper_id("Q3").canonical_id == "deployment.shared_tail_join"
    diagnostic_join = by_legacy_artifact_id("Q3_join")
    assert diagnostic_join.canonical_id == "diagnostic.fanout_join"
    assert "canonical unordered pairs" in diagnostic_join.answer
    assert "traversal order" in diagnostic_join.legacy_behavior
    assert "different tuple" in diagnostic_join.legacy_behavior


def test_top_degree_records_deterministic_spec_and_legacy_uncertainty():
    top_degree = by_legacy_artifact_id("Q4_top_degree")
    assert "distinct-neighbor degree" in top_degree.answer
    assert "canonical entity keys" in top_degree.answer
    assert "cannot be recovered" in top_degree.legacy_behavior
