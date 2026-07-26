#!/usr/bin/env python3
"""Build the canonical label-blind cohorts for RQ8 and RQ10."""

from __future__ import annotations

import argparse
import json
import random
import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from graphguard.deployment_cohorts import (  # noqa: E402
    COHORT_ARTIFACT_TYPE,
    COHORT_ARTIFACT_VERSION,
    canonical_digest,
    seeded_anchor_sample,
    select_anchored_cohort,
)
from graphguard.deployment_downstream import (  # noqa: E402
    DOWNSTREAM_ARTIFACT_TYPE,
)
from graphguard.deployment_runner import ARTIFACT_TYPE  # noqa: E402
from graphguard import qa  # noqa: E402
from graphguard.sqlite_snapshot import (  # noqa: E402
    database_fingerprint,
    require_quiescent_snapshot,
    require_stable_quiescent_snapshot,
    runtime_versions,
    sha256_file,
)


RQ8_RUN = "docred__deepseek-v4-flash__300d"
RQ10_RUNS = (
    "docred__deepseek-v4-flash__300d",
    "redocred__deepseek-v4-flash__300d",
    "scierc__deepseek-v4-flash__100d",
    "cdr__deepseek-v4-flash__300d",
)
SEED = 0
RQ8_TARGET = 4000
RQ10_TARGET = 300
RQ10_ANCHOR_DIGESTS = {
    "docred__deepseek-v4-flash__300d": (
        "70d7d33dc380edc1a43b1ff7d7e498c146b3892eb3a7a47ea9ad03d16a4e2d7e"
    ),
    "redocred__deepseek-v4-flash__300d": (
        "d2dbe3558d06ea6d0d018e2aead6dac755d0f7738811c9e2a34e95b09315ba0d"
    ),
    "scierc__deepseek-v4-flash__100d": (
        "ab04dd4937829df0f204ea82a60acb5a619a915a6ec95f165ac13bdda33e5c59"
    ),
    "cdr__deepseek-v4-flash__300d": (
        "42baf4e85ece5d5be6c9d7de16c53bcdbd68d15c47e0eb0394edaca8681a5ebf"
    ),
}
IMPLEMENTATION_FILES = (
    "graphguard/deployment_cohorts.py",
    "graphguard/deployment_downstream.py",
    "graphguard/deployment_runner.py",
    "graphguard/sqlite_snapshot.py",
    "scripts/build_deployment_cohorts.py",
)


def git_commit() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _source_paths(run: str) -> tuple[Path, Path, Path]:
    downstream = (
        ROOT / "reports" / "cross_run"
        / f"deployment_downstream_{run}.json"
    )
    deployment = (
        ROOT / "reports" / "cross_run"
        / f"deployment_q1q4_{run}.json"
    )
    db = ROOT / "data" / "processed" / "runs" / run / f"{run}.db"
    return downstream, deployment, db


def _load_registered_population(run: str) -> dict:
    downstream_path, deployment_path, db_path = _source_paths(run)
    downstream = _read_json(downstream_path)
    deployment = _read_json(deployment_path)
    if downstream.get("artifact_type") != DOWNSTREAM_ARTIFACT_TYPE:
        raise ValueError(f"not a downstream artifact: {downstream_path}")
    if deployment.get("artifact_type") != ARTIFACT_TYPE:
        raise ValueError(f"not a deployment artifact: {deployment_path}")
    if downstream["source_run"] != run or deployment["source_run"] != run:
        raise ValueError(f"source-run mismatch for {run}")
    if (
        downstream["deployment_artifact"]["sha256"]
        != sha256_file(deployment_path)
    ):
        raise ValueError(f"downstream/deployment SHA mismatch for {run}")

    before = database_fingerprint(db_path)
    require_quiescent_snapshot(before)
    if downstream["source_database"]["sha256"] != before["main"]["sha256"]:
        raise ValueError(f"downstream/source DB SHA mismatch for {run}")
    eligible_ids = [record["run_id"] for record in downstream["per_pair"]]
    authoritative_ids = {
        record["run_id"] for record in deployment["per_pair"]
    }
    after = database_fingerprint(db_path)
    require_stable_quiescent_snapshot(before, after)
    return {
        "run": run,
        "downstream_path": downstream_path,
        "downstream_sha256": sha256_file(downstream_path),
        "deployment_path": deployment_path,
        "deployment_sha256": sha256_file(deployment_path),
        "db_path": db_path,
        "db_fingerprint_before": before,
        "db_fingerprint_after": after,
        "eligible_ids": eligible_ids,
        "authoritative_ids": authoritative_ids,
    }


def _status_ok_run_ids(db_path: Path) -> list[str]:
    connection = sqlite3.connect(
        f"file:{db_path.resolve()}?mode=ro",
        uri=True,
    )
    try:
        return [
            row[0]
            for row in connection.execute(
                "SELECT run_id FROM counterfactual_runs "
                "WHERE status='ok' ORDER BY rowid"
            )
        ]
    finally:
        connection.close()


def _source_record(source: dict) -> dict:
    return {
        "source_run": source["run"],
        "downstream_artifact": {
            "path": source["downstream_path"].relative_to(ROOT).as_posix(),
            "sha256": source["downstream_sha256"],
        },
        "deployment_artifact": {
            "path": source["deployment_path"].relative_to(ROOT).as_posix(),
            "sha256": source["deployment_sha256"],
        },
        "source_database": {
            "path": source["db_path"].relative_to(ROOT).as_posix(),
            "sha256": source["db_fingerprint_before"]["main"]["sha256"],
            "fingerprint_before": source["db_fingerprint_before"],
            "fingerprint_after": source["db_fingerprint_after"],
        },
        "n_authoritative_pairs": len(source["authoritative_ids"]),
        "n_registered_eligible_pairs": len(source["eligible_ids"]),
    }


def _rq10_anchor_run_ids(db_path: Path) -> list[str]:
    """Rebuild the pre-specified N=300 sample without running Kuzu."""
    connection = sqlite3.connect(
        f"file:{db_path.resolve()}?mode=ro",
        uri=True,
    )
    try:
        edges, gold, runs = qa.load_data(connection)
    finally:
        connection.close()
    random.Random(SEED).shuffle(runs)
    selected = []
    for run_id, base_event, cf_event, doc_id, _family, _intervention in runs:
        if (
            not cf_event
            or base_event not in edges
            or cf_event not in edges
            or not qa.build_queries(gold.get(doc_id, set()))
        ):
            continue
        selected.append(run_id)
        if len(selected) == RQ10_TARGET:
            break
    if len(selected) != RQ10_TARGET:
        raise ValueError(f"{db_path}: cannot reconstruct N=300 anchor")
    return selected


def build_manifest() -> dict:
    sources = {
        run: _load_registered_population(run)
        for run in RQ10_RUNS
    }
    rq8_source = sources[RQ8_RUN]
    ordered_status_ok = _status_ok_run_ids(rq8_source["db_path"])
    rq8_anchor = seeded_anchor_sample(
        ordered_status_ok,
        target_size=RQ8_TARGET,
        seed=SEED,
    )
    rq8_selection = select_anchored_cohort(
        rq8_source["eligible_ids"],
        rq8_anchor,
        target_size=RQ8_TARGET,
        seed=SEED,
        authoritative_run_ids=rq8_source["authoritative_ids"],
    )

    rq10 = {}
    for run in RQ10_RUNS:
        source = sources[run]
        anchor_ids = _rq10_anchor_run_ids(source["db_path"])
        anchor_digest = canonical_digest(anchor_ids)
        if anchor_digest != RQ10_ANCHOR_DIGESTS[run]:
            raise ValueError(
                f"{run}: pre-specified anchor digest mismatch: "
                f"{anchor_digest}"
            )
        selection = select_anchored_cohort(
            source["eligible_ids"],
            anchor_ids,
            target_size=RQ10_TARGET,
            seed=SEED,
            authoritative_run_ids=source["authoritative_ids"],
        )
        rq10[run] = {
            "purpose": "RQ10 actual Kuzu N=300 release-gate cohort",
            "source": _source_record(source),
            "selection_anchor": {
                "method": (
                    "random.Random(0).shuffle over query-eligible "
                    "counterfactual runs; take first 300"
                ),
                "n_pairs": len(anchor_ids),
                "run_ids_sha256": anchor_digest,
            },
            "selection": selection,
        }

    return {
        "artifact_type": COHORT_ARTIFACT_TYPE,
        "artifact_version": COHORT_ARTIFACT_VERSION,
        "protocol": {
            "selection_is_label_blind": True,
            "anchor_rule": (
                "retain pre-specified cohort IDs that remain in the registered "
                "schema-eligible workload; replace only excluded IDs"
            ),
            "replacement_rule": (
                "ascending SHA256(f'{seed}:{run_id}'), then run_id"
            ),
            "seed": SEED,
        },
        "cohorts": {
            "rq8_docred_n4000": {
                "purpose": (
                    "RQ8 registered schema-eligible N=4000 anchored cohort"
                ),
                "source": _source_record(rq8_source),
                "selection_anchor": {
                    "method": (
                        "random.Random(0).sample over status='ok' "
                        "counterfactual_runs in SQLite rowid order"
                    ),
                    "population_size": len(ordered_status_ok),
                    "population_run_ids_sha256": canonical_digest(
                        ordered_status_ok
                    ),
                    "run_ids_sha256": canonical_digest(rq8_anchor),
                },
                "selection": rq8_selection,
            },
            "rq10_n300": rq10,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--out",
        type=Path,
        default=(
            ROOT / "reports" / "cross_run"
            / "deployment_cohorts.json"
        ),
    )
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    if args.out.exists() and not args.overwrite:
        raise FileExistsError(
            f"{args.out} exists; choose a new path or pass --overwrite"
        )

    artifact = build_manifest()
    artifact["implementation"] = {
        "base_git_commit": git_commit(),
        "source_state": "working_tree_content_hashes",
        "file_sha256": {
            path: sha256_file(ROOT / path)
            for path in IMPLEMENTATION_FILES
        },
        "runtime": runtime_versions(),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.out.with_suffix(args.out.suffix + ".tmp")
    temporary.write_text(
        json.dumps(
            artifact,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    temporary.replace(args.out)
    rq8 = artifact["cohorts"]["rq8_docred_n4000"]["selection"]
    print(
        f"[done] RQ8: {rq8['n_retained']} retained, "
        f"{rq8['n_replacements']} replacements"
    )
    for run, entry in artifact["cohorts"]["rq10_n300"].items():
        selection = entry["selection"]
        print(
            f"[done] RQ10 {run}: {selection['n_retained']} retained, "
            f"{selection['n_replacements']} replacements"
        )
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
