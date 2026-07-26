from graphguard.query_catalog import (
    ALL_QUERIES,
    DIAGNOSTIC_QUERIES,
    by_paper_id,
)


def test_paper_ids_are_unique_and_cover_q1_to_q7():
    paper_ids = [spec.paper_id for spec in ALL_QUERIES if spec.paper_id]
    assert paper_ids == [f"Q{i}" for i in range(1, 8)]
    assert len(paper_ids) == len(set(paper_ids))


def test_diagnostic_ids_are_separate_from_paper_ids():
    assert all(spec.paper_id is None for spec in DIAGNOSTIC_QUERIES)


def test_same_join_word_does_not_collapse_distinct_semantics():
    assert by_paper_id("Q3").canonical_id == "deployment.shared_tail_join"
    diagnostic_join = next(
        spec
        for spec in DIAGNOSTIC_QUERIES
        if spec.canonical_id == "diagnostic.fanout_join"
    )
    assert diagnostic_join.canonical_id == "diagnostic.fanout_join"
    assert "canonical unordered pairs" in diagnostic_join.answer


def test_top_degree_records_deterministic_spec():
    top_degree = next(
        spec
        for spec in DIAGNOSTIC_QUERIES
        if spec.canonical_id == "diagnostic.top_undirected_degree"
    )
    assert "distinct-neighbor degree" in top_degree.answer
    assert "canonical entity keys" in top_degree.answer
