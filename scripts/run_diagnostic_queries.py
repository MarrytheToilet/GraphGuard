#!/usr/bin/env python3
"""Run the canonical full diagnostic-query evaluation on materialized DBs."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from graphguard.diagnostic_runner import analyze_database  # noqa: E402


RUNS = (
    "docred__deepseek-v4-flash__300d",
    "redocred__deepseek-v4-flash__300d",
    "scierc__deepseek-v4-flash__100d",
    "cdr__deepseek-v4-flash__300d",
    "docred__glm-5__100d",
    "docred__kimi-k2__100d",
    "docred__qwen3-32b__100d",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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
    for run in args.runs:
        db_path = (
            ROOT / "data" / "processed" / "runs" / run / f"{run}.db"
        )
        if not db_path.exists():
            raise FileNotFoundError(db_path)
        output_path = args.out_dir / f"diagnostic_{run}.json"
        if output_path.exists() and not args.overwrite:
            raise FileExistsError(
                f"{output_path} exists; pass --overwrite to replace it"
            )

        artifact = analyze_database(
            db_path,
            n_bootstrap=args.bootstrap,
            seed=args.seed,
        )
        artifact["source_database"] = {
            "path": str(db_path.relative_to(ROOT)),
            "sha256": sha256_file(db_path),
            "size_bytes": db_path.stat().st_size,
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
            ci = result["amplification_document_cluster_ci"]
            print(
                f"  {query_id}: amp="
                f"{result['amplification_mean_per_pair']:.4f} "
                f"[{ci['ci_low']:.4f}, {ci['ci_high']:.4f}]"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
