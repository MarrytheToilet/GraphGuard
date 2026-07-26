from pathlib import Path
import shutil

import pytest

from graphguard.deployment_evidence import (
    PRIMARY_RUNS,
    _decompress_bounded,
    _repo_path,
    _validate_selection,
    load_artifact_index,
    load_kuzu_evidence,
    validate_evidence_package,
)


ROOT = Path(__file__).resolve().parents[1]


def test_registered_evidence_package_validates():
    summary = validate_evidence_package(ROOT)

    assert set(summary) == set(PRIMARY_RUNS)
    assert all(row["kuzu_pairs"] == 300 for row in summary.values())
    assert sum(row["kuzu_queries"] for row in summary.values()) == 22306


def test_registered_kuzu_artifacts_are_complete_and_mismatch_free():
    index = load_artifact_index(ROOT)

    for run in PRIMARY_RUNS:
        artifact = load_kuzu_evidence(ROOT, run)
        assert artifact["status"] == "pass"
        assert artifact["complete"] is True
        assert artifact["execution"]["n_mismatches"] == 0
        assert index["entries"][f"kuzu:{run}"]["compression"] == "gzip"


def test_artifact_path_cannot_escape_repository(tmp_path):
    with pytest.raises(ValueError, match="escapes repository"):
        _repo_path(tmp_path, "../outside.json")


def test_bounded_gzip_rejects_registered_size_understatement():
    import gzip

    value = gzip.compress(b"too long", mtime=0)
    with pytest.raises(ValueError, match="exceeds registered size"):
        _decompress_bounded(
            value,
            expected_size=3,
            label="fixture",
        )


def test_selection_validator_rejects_duplicate_or_reordered_ids():
    valid = {
        "selected_run_ids": ["run-1", "run-2"],
        "retained_run_ids": ["run-1"],
        "replacement_run_ids": ["run-2"],
        "excluded": [{"run_id": "old"}],
        "target_size": 2,
        "n_anchor": 2,
        "n_retained": 1,
        "n_excluded": 1,
        "n_replacements": 1,
        "selected_run_ids_sha256": "",
    }
    from graphguard.deployment_cohorts import canonical_digest

    valid["selected_run_ids_sha256"] = canonical_digest(
        valid["selected_run_ids"]
    )
    assert _validate_selection(valid, "fixture") == ["run-1", "run-2"]

    duplicate = {**valid, "selected_run_ids": ["run-1", "run-1"]}
    duplicate["selected_run_ids_sha256"] = canonical_digest(
        duplicate["selected_run_ids"]
    )
    with pytest.raises(ValueError, match="not unique and complete"):
        _validate_selection(duplicate, "fixture")

    reordered = {
        **valid,
        "selected_run_ids": ["run-2", "run-1"],
    }
    reordered["selected_run_ids_sha256"] = canonical_digest(
        reordered["selected_run_ids"]
    )
    with pytest.raises(ValueError, match="order mismatch"):
        _validate_selection(reordered, "fixture")


def test_downstream_loader_requires_deployment_transport(tmp_path):
    run = "docred__deepseek-v4-flash__300d"
    required = (
        "scripts/package_deployment_evidence.py",
        "reports/cross_run/deployment_evidence.json",
        f"reports/cross_run/deployment_downstream_{run}.json.gz",
        f"reports/cross_run/deployment_q1q4_{run}__kuzu_parity.json",
    )
    for relative in required:
        source = ROOT / relative
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)

    from graphguard.deployment_evidence import load_downstream_evidence

    with pytest.raises(FileNotFoundError, match="transport artifact"):
        load_downstream_evidence(tmp_path, run)
