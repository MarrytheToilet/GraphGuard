#!/usr/bin/env python3
"""Run the registered RQ10 cohorts with actual Kuzu Cypher execution."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from graphguard.deployment_kuzu_cohort import (  # noqa: E402
    REGISTERED_COHORT_MANIFEST_SHA256,
    REGISTERED_SMOKE_RUN_IDS,
    load_kuzu_cohort_context,
    run_kuzu_cohort,
    write_json_atomic,
)
from graphguard.sqlite_snapshot import sha256_file  # noqa: E402


RUNS = tuple(REGISTERED_SMOKE_RUN_IDS)
IMPLEMENTATION_FILES = (
    "graphguard/deployment_kuzu_cohort.py",
    "graphguard/deployment_cohorts.py",
    "graphguard/deployment_downstream.py",
    "graphguard/deployment_runner.py",
    "graphguard/kuzu_executor.py",
    "graphguard/qa.py",
    "graphguard/sqlite_snapshot.py",
    "scripts/run_deployment_kuzu_cohort.py",
)


def git_commit() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def implementation_provenance() -> dict:
    return {
        "base_git_commit": git_commit(),
        "source_state": "working_tree_content_hashes",
        "file_sha256": {
            path: sha256_file(ROOT / path)
            for path in IMPLEMENTATION_FILES
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--manifest",
        type=Path,
        default=(
            ROOT / "reports" / "cross_run"
            / "deployment_cohorts.json"
        ),
    )
    parser.add_argument("--runs", nargs="+", default=RUNS)
    parser.add_argument(
        "--mode",
        choices=("complete", "smoke"),
        default="complete",
    )
    parser.add_argument("--out-dir", type=Path)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    unknown = sorted(set(args.runs) - set(RUNS))
    if unknown:
        parser.error(f"unregistered source runs: {', '.join(unknown)}")
    if len(args.runs) != len(set(args.runs)):
        parser.error("--runs contains duplicates")
    out_dir = args.out_dir
    if out_dir is None:
        out_dir = (
            ROOT / "reports" / "cross_run"
            if args.mode == "complete"
            else Path("/tmp/graphguard-kuzu-smoke")
        )

    implementation = implementation_provenance()
    for run in args.runs:
        suffix = "" if args.mode == "complete" else "__smoke"
        output_path = (
            out_dir / f"deployment_kuzu_cohort_{run}{suffix}.json"
        )
        if output_path.exists() and not args.overwrite:
            raise FileExistsError(
                f"{output_path} exists; pass --overwrite to replace it"
            )
        context = load_kuzu_cohort_context(
            args.manifest,
            run,
            repo_root=ROOT,
            expected_manifest_sha256=REGISTERED_COHORT_MANIFEST_SHA256,
        )

        def progress(index: int, total: int, run_id: str) -> None:
            if index == 1 or index == total or index % 25 == 0:
                print(
                    f"[{run}] {index}/{total} pairs: {run_id}",
                    flush=True,
                )

        artifact = run_kuzu_cohort(
            context,
            mode=args.mode,
            smoke_run_ids=(
                REGISTERED_SMOKE_RUN_IDS[run]
                if args.mode == "smoke"
                else None
            ),
            progress=progress,
        )
        artifact["implementation"] = implementation
        write_json_atomic(
            output_path,
            artifact,
            overwrite=args.overwrite,
        )
        execution = artifact["execution"]
        print(
            f"[done] {run}: {execution['n_pairs_completed']} pairs, "
            f"{execution['n_query_instances_checked']} queries -> "
            f"{output_path}",
            flush=True,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
