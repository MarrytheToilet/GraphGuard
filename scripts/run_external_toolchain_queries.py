#!/usr/bin/env python3
"""Run the shared external-toolchain Q1--Q4 workload in actual Kuzu."""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from graphguard.external_toolchain_queries import (  # noqa: E402
    analyze_external_toolchains,
    write_artifact,
)


DEFAULT_DB = (
    ROOT
    / "data/processed/runs/docred__deepseek-v4-flash__300d"
    / "docred__deepseek-v4-flash__300d.db"
)
DEFAULT_OUTPUT = (
    ROOT / "reports/cross_run/external_toolchain_q1q4_kuzu.json"
)
DEFAULT_CHECKPOINTS = {
    "langchain": ROOT / "reports/cross_run/langchain_toolchain_cache.jsonl",
    "neo4j": ROOT / "reports/cross_run/neo4j_toolchain_cache.jsonl",
}


def relative_or_absolute(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(path.resolve())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument(
        "--langchain-cache",
        type=Path,
        default=DEFAULT_CHECKPOINTS["langchain"],
    )
    parser.add_argument(
        "--neo4j-cache",
        type=Path,
        default=DEFAULT_CHECKPOINTS["neo4j"],
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--workers", type=int, default=1)
    args = parser.parse_args()

    artifact = analyze_external_toolchains(
        db_path=args.db,
        checkpoints={
            "langchain": args.langchain_cache,
            "neo4j": args.neo4j_cache,
        },
        workers=args.workers,
    )
    artifact["source_database"]["path"] = relative_or_absolute(args.db)
    for toolchain, cache_path in (
        ("langchain", args.langchain_cache),
        ("neo4j", args.neo4j_cache),
    ):
        artifact["toolchains"][toolchain]["source_checkpoint"][
            "path"
        ] = relative_or_absolute(cache_path)
    implementation_paths = (
        ROOT / "graphguard/external_toolchain_queries.py",
        ROOT / "graphguard/qa.py",
        ROOT / "graphguard/kuzu_executor.py",
        Path(__file__).resolve(),
    )
    artifact["producer"] = {
        "command": (
            "python scripts/run_external_toolchain_queries.py "
            f"--workers {args.workers}"
        ),
        "implementation_sha256": {
            path.resolve().relative_to(ROOT).as_posix(): hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
            for path in implementation_paths
        },
    }
    write_artifact(args.output, artifact)

    print(f"Kuzu {artifact['kuzu_version']}")
    print(
        "parity:",
        artifact["parity"]["status"],
        f"({artifact['parity']['n_mismatches']} mismatches)",
    )
    for toolchain, result in artifact["toolchains"].items():
        print(toolchain)
        for axis, row in result["summary"].items():
            print(
                f"  {axis}: n={row['n_pairs']}, "
                f"mean max Q drift={row['mean_pair_max_query_drift']:.4f}, "
                f"viol={row['violation_rate']:.4f}, "
                f"active queries={row['active_query_rate']:.4f}"
            )
    print(args.output)
    return 0 if artifact["parity"]["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
