#!/usr/bin/env python3
"""Run the versioned deployment Q1--Q4 evaluation on materialized DBs."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from graphguard.deployment_runner import analyze_database  # noqa: E402
from graphguard.sqlite_snapshot import (  # noqa: E402
    database_fingerprint,
    require_quiescent_snapshot,
    require_stable_quiescent_snapshot,
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
    "graphguard/deployment_runner.py",
    "graphguard/diagnostic_runner.py",
    "graphguard/kuzu_executor.py",
    "graphguard/qa.py",
    "graphguard/query_catalog.py",
    "graphguard/interventions/schema.py",
    "graphguard/sqlite_snapshot.py",
    "scripts/run_deployment_queries.py",
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
    parser.add_argument("--bootstrap", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=0)
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
        if not db_path.exists():
            raise FileNotFoundError(db_path)
        output_path = args.out_dir / f"deployment_q1q4_{run}.json"
        if output_path.exists() and not args.overwrite:
            raise FileExistsError(
                f"{output_path} exists; choose a new output directory or "
                "pass --overwrite explicitly"
            )

        source_before = database_fingerprint(db_path)
        require_quiescent_snapshot(source_before)
        artifact = analyze_database(
            db_path,
            n_bootstrap=args.bootstrap,
            seed=args.seed,
        )
        source_after = database_fingerprint(db_path)
        require_stable_quiescent_snapshot(source_before, source_after)
        artifact["source_database"] = {
            "path": str(db_path.relative_to(ROOT)),
            "sha256": source_before["main"]["sha256"],
            "size_bytes": source_before["main"]["size_bytes"],
            "snapshot_policy": (
                "single explicit read transaction; non-empty WAL rejected; "
                "main SHA/size stable before and after; zero-length WAL "
                "existence/mtime ignored"
            ),
            "fingerprint_before": source_before,
            "fingerprint_after": source_after,
        }
        artifact["implementation"] = {
            "git_commit": commit,
            "file_sha256": implementation,
            "runtime": runtime_versions(),
        }
        serialized = json.dumps(
            artifact,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
        ) + "\n"
        temporary_path = output_path.with_suffix(".json.tmp")
        temporary_path.write_text(serialized, encoding="utf-8")
        temporary_path.replace(output_path)

        print(
            f"[done] {run}: {artifact['pairing']['n_pairs']} pairs -> "
            f"{output_path}"
        )
        for query_id, result in artifact["summary"].items():
            if result["status"] != "ok":
                print(f"  {query_id}: N/A")
                continue
            ci = result["amplification_document_cluster_ci"]
            print(
                f"  {query_id}: amp="
                f"{result['amplification_mean_per_pair']:.4f} "
                f"[{ci['ci_low']:.4f}, {ci['ci_high']:.4f}], "
                f"pairs={result['n_pairs']}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
