import pytest

from graphguard.deployment_cohorts import (
    canonical_digest,
    legacy_random_sample,
    replacement_rank,
    select_continuity_cohort,
)


def test_continuity_cohort_retains_and_replaces_without_labels():
    eligible = ["keep-a", "keep-b", "replacement-b", "replacement-a"]
    legacy = ["keep-a", "excluded", "keep-b"]

    result = select_continuity_cohort(
        eligible,
        legacy,
        target_size=3,
        seed=0,
        authoritative_run_ids={"keep-a", "keep-b", "excluded"},
    )

    expected_replacement = min(
        ("replacement-a", "replacement-b"),
        key=lambda run_id: (replacement_rank(0, run_id), run_id),
    )
    assert result["retained_run_ids"] == ["keep-a", "keep-b"]
    assert result["replacement_run_ids"] == [expected_replacement]
    assert result["selected_run_ids"] == [
        "keep-a",
        "keep-b",
        expected_replacement,
    ]
    assert result["excluded"] == [{
        "run_id": "excluded",
        "reason": "empty_formal_query_catalog",
    }]
    assert result["selected_run_ids_sha256"] == canonical_digest(
        result["selected_run_ids"]
    )


def test_continuity_cohort_marks_non_authoritative_exclusion():
    result = select_continuity_cohort(
        ["keep", "replacement"],
        ["keep", "missing"],
        target_size=2,
        seed=0,
        authoritative_run_ids={"keep"},
    )

    assert result["excluded"][0]["reason"] == (
        "not_in_authoritative_population"
    )


def test_continuity_cohort_is_independent_of_eligible_input_order():
    legacy = ["keep", "excluded"]
    first = select_continuity_cohort(
        ["keep", "a", "b", "c"],
        legacy,
        target_size=2,
        seed=7,
    )
    second = select_continuity_cohort(
        ["c", "b", "a", "keep"],
        legacy,
        target_size=2,
        seed=7,
    )

    assert first["selected_run_ids"] == second["selected_run_ids"]


@pytest.mark.parametrize(
    ("eligible", "legacy", "target", "message"),
    [
        (["a", "a"], ["a"], 1, "eligible population contains duplicate"),
        (["a"], ["a", "a"], 2, "legacy cohort contains duplicate"),
        (["a"], ["a"], 2, "legacy cohort size differs"),
        ([], ["missing"], 1, "cannot fill cohort"),
    ],
)
def test_continuity_cohort_rejects_invalid_inputs(
    eligible,
    legacy,
    target,
    message,
):
    with pytest.raises(ValueError, match=message):
        select_continuity_cohort(
            eligible,
            legacy,
            target_size=target,
            seed=0,
        )


def test_legacy_random_sample_reconstructs_seeded_selection():
    population = [f"run-{index}" for index in range(20)]

    first = legacy_random_sample(population, target_size=5, seed=0)
    second = legacy_random_sample(population, target_size=5, seed=0)

    assert first == second
    assert len(first) == len(set(first)) == 5


def test_legacy_random_sample_rejects_duplicate_population():
    with pytest.raises(ValueError, match="duplicate run IDs"):
        legacy_random_sample(["a", "a"], target_size=1, seed=0)
