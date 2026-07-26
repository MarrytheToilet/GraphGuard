#!/usr/bin/env python3
"""Validate exact offline/Kuzu parity for deployment Q1--Q4 artifacts."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from graphguard.deployment_parity import validate_parity  # noqa: E402
from graphguard.sqlite_snapshot import (  # noqa: E402
    runtime_versions,
    sha256_file,
)


IMPLEMENTATION_FILES = (
    "graphguard/deployment_parity.py",
    "graphguard/deployment_runner.py",
    "graphguard/kuzu_executor.py",
    "graphguard/qa.py",
    "graphguard/sqlite_snapshot.py",
    "scripts/validate_deployment_kuzu_parity.py",
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
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--min-pairs", type=int, default=20)
    parser.add_argument("--max-pairs", type=int)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    if args.out.exists() and not args.overwrite:
        raise FileExistsError(
            f"{args.out} exists; choose a new path or pass --overwrite"
        )
    artifact = validate_parity(
        args.db,
        args.artifact,
        seed=args.seed,
        min_pairs=args.min_pairs,
        max_pairs=args.max_pairs,
    )
    artifact["implementation"] = {
        "git_commit": git_commit(),
        "file_sha256": {
            relative_path: sha256_file(ROOT / relative_path)
            for relative_path in IMPLEMENTATION_FILES
        },
        "runtime": runtime_versions(),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = args.out.with_suffix(args.out.suffix + ".tmp")
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
    temporary_path.replace(args.out)
    print(
        f"[{artifact['status']}] {artifact['source_run']}: "
        f"{artifact['n_graph_pairs_materialized']} pairs, "
        f"{artifact['n_answer_sets_checked']} answer sets, "
        f"{artifact['n_mismatches']} mismatches"
    )
    return 0 if artifact["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
