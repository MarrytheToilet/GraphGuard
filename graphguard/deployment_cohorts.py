"""Versioned, label-blind cohorts for formal downstream evaluation."""

from __future__ import annotations

import hashlib
import json
import random
from collections.abc import Sequence


COHORT_ARTIFACT_TYPE = "graphguard.deployment_q1q4_cohorts"
COHORT_ARTIFACT_VERSION = 1


def canonical_digest(value) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def replacement_rank(seed: int, run_id: str) -> str:
    """Return a deterministic, label-blind replacement rank."""
    return hashlib.sha256(f"{seed}:{run_id}".encode("utf-8")).hexdigest()


def legacy_random_sample(
    ordered_run_ids: Sequence[str],
    *,
    target_size: int,
    seed: int,
) -> list[str]:
    """Reconstruct the historical ``random.sample`` cohort selection."""
    if target_size <= 0:
        raise ValueError("target_size must be positive")
    if len(ordered_run_ids) < target_size:
        raise ValueError("legacy population is smaller than target_size")
    if len(ordered_run_ids) != len(set(ordered_run_ids)):
        raise ValueError("legacy population contains duplicate run IDs")
    return random.Random(seed).sample(list(ordered_run_ids), target_size)


def select_continuity_cohort(
    eligible_run_ids: Sequence[str],
    legacy_run_ids: Sequence[str],
    *,
    target_size: int,
    seed: int,
    authoritative_run_ids: set[str] | None = None,
) -> dict:
    """Retain a historical cohort and replace only newly ineligible pairs.

    Replacements are chosen without labels by SHA-256 rank over the remaining
    formal eligible population. Retained IDs preserve legacy order; replacement
    IDs are appended in their deterministic rank order.
    """
    eligible = list(eligible_run_ids)
    legacy = list(legacy_run_ids)
    if target_size <= 0:
        raise ValueError("target_size must be positive")
    if len(eligible) != len(set(eligible)):
        raise ValueError("eligible population contains duplicate run IDs")
    if len(legacy) != len(set(legacy)):
        raise ValueError("legacy cohort contains duplicate run IDs")
    if len(legacy) != target_size:
        raise ValueError("legacy cohort size differs from target_size")

    eligible_set = set(eligible)
    retained = [run_id for run_id in legacy if run_id in eligible_set]
    excluded_ids = [
        run_id for run_id in legacy if run_id not in eligible_set
    ]
    replacement_pool = [
        run_id for run_id in eligible if run_id not in set(legacy)
    ]
    replacement_pool.sort(
        key=lambda run_id: (replacement_rank(seed, run_id), run_id)
    )
    needed = target_size - len(retained)
    if len(replacement_pool) < needed:
        raise ValueError("formal eligible population cannot fill cohort")
    replacements = replacement_pool[:needed]
    selected = retained + replacements
    if len(selected) != target_size or len(selected) != len(set(selected)):
        raise AssertionError("cohort selection is not unique and complete")

    authoritative = authoritative_run_ids or set()
    excluded = [
        {
            "run_id": run_id,
            "reason": (
                "empty_formal_query_catalog"
                if run_id in authoritative
                else "not_in_authoritative_population"
            ),
        }
        for run_id in excluded_ids
    ]
    return {
        "target_size": target_size,
        "seed": seed,
        "selection_method": (
            "retain legacy IDs that remain formally eligible; append "
            "label-blind SHA256(seed:run_id)-ranked replacements"
        ),
        "replacement_rank": "SHA256(f'{seed}:{run_id}') ascending",
        "retained_order": "legacy cohort order",
        "replacement_order": "replacement rank, then run_id",
        "n_legacy": len(legacy),
        "n_retained": len(retained),
        "n_excluded": len(excluded),
        "n_replacements": len(replacements),
        "legacy_run_ids_sha256": canonical_digest(legacy),
        "retained_run_ids": retained,
        "excluded": excluded,
        "replacement_run_ids": replacements,
        "selected_run_ids": selected,
        "selected_run_ids_sha256": canonical_digest(selected),
    }
