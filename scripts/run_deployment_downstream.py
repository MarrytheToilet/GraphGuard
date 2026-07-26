#!/usr/bin/env python3
"""Build canonical RQ8--RQ10 inputs from registered deployment artifacts."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from graphguard.deployment_downstream import (  # noqa: E402
    build_downstream_artifact,
    load_kuzu_parity_evidence,
    load_registered_inputs,
)
from graphguard.sqlite_snapshot import (  # noqa: E402
    runtime_versions,
    sha256_file,
)


RUNS = (
    "docred__deepseek-v4-flash__300d",
    "redocred__deepseek-v4-flash__300d",
    "scierc__deepseek-v4-flash__100d",
    "cdr__deepseek-v4-flash__300d",
)
IMPLEMENTATION_FILES = (
    "graphguard/deployment_downstream.py",
    "graphguard/deployment_parity.py",
    "graphguard/deployment_runner.py",
    "graphguard/diagnostic_runner.py",
    "graphguard/qa.py",
    "graphguard/query_catalog.py",
    "graphguard/interventions/schema.py",
    "graphguard/sqlite_snapshot.py",
    "scripts/run_deployment_downstream.py",
)


def git_commit() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", nargs="*", default=RUNS)
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=ROOT / "reports" / "cross_run",
    )
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    implementation = {
        relative_path: sha256_file(ROOT / relative_path)
        for relative_path in IMPLEMENTATION_FILES
    }
    commit = git_commit()
    for run in args.runs:
        db_path = (
            ROOT / "data" / "processed" / "runs" / run / f"{run}.db"
        )
        deployment_path = (
            ROOT
            / "reports"
            / "cross_run"
            / f"deployment_q1q4_{run}.json"
        )
        parity_path = (
            ROOT
            / "reports"
            / "cross_run"
            / f"deployment_q1q4_{run}__kuzu_parity.json"
        )
        output_path = args.out_dir / f"deployment_downstream_{run}.json"
        if output_path.exists() and not args.overwrite:
            raise FileExistsError(
                f"{output_path} exists; choose another directory or "
                "pass --overwrite"
            )
        inputs = load_registered_inputs(db_path, deployment_path)
        artifact = build_downstream_artifact(inputs)
        artifact["execution_evidence"] = {
            "full_population_backend": "offline_set_semantics",
            "kuzu_parity": load_kuzu_parity_evidence(
                inputs,
                parity_path,
            ),
        }
        artifact["implementation"] = {
            "git_commit": commit,
            "file_sha256": implementation,
            "runtime": runtime_versions(),
        }
        temporary_path = output_path.with_suffix(".json.tmp")
        temporary_path.write_text(
            json.dumps(
                artifact,
                indent=2,
                sort_keys=True,
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
        temporary_path.replace(output_path)
        population = artifact["population"]
        print(
            f"[done] {run}: "
            f"{population['n_pairs_with_nonempty_workload']} eligible pairs, "
            f"{population['n_query_evaluations']} query evaluations -> "
            f"{output_path}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
