#!/usr/bin/env python3
"""End-to-end driver for one GraphGuard paper run.

The driver materializes the base extraction, controlled counterfactuals, the
repeated-extraction baseline, and the registered drift-contract report.  Other
paper analyses consume the resulting lineage database and contract artifact.

Example:
  python scripts/run_paper_experiment.py --profile pilot --fresh
  python scripts/run_paper_experiment.py --profile main --workers 4 --fresh
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable


def _run(cmd: list[str], *, skip: bool = False, env: dict[str, str] | None = None,
         dry_run: bool = False) -> int:
    label = "[skip]" if skip else "[exec]"
    print(label, " ".join(cmd), flush=True)
    if skip or dry_run:
        return 0
    return subprocess.call(cmd, cwd=str(ROOT), env=env)


def _profile(cfg: dict[str, Any], name: str) -> dict[str, Any]:
    profiles = cfg.get("profiles") or {}
    if name not in profiles:
        raise SystemExit(f"unknown profile {name}; available={list(profiles)}")
    return dict(profiles[name])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/experiments/docred_paper.yaml")
    ap.add_argument("--profile", default="pilot", choices=["smoke", "pilot", "medium", "main", "main100", "main300"])
    ap.add_argument("--run-name", default=None,
                    help="Output run name. Defaults to <config.name>_<profile>.")
    ap.add_argument("--fresh", action="store_true",
                    help="Delete the run DB before starting.")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--model", default=None,
                    help="Override OPENAI_MODEL for the primary run.")
    ap.add_argument("--docs", type=int, default=None)
    ap.add_argument("--oracle-docs", type=int, default=None)
    ap.add_argument("--main-budget", type=int, default=None)
    ap.add_argument("--oracle-budget", type=int, default=None)
    ap.add_argument("--e0-docs", type=int, default=None)
    ap.add_argument("--e0-runs", type=int, default=None)
    ap.add_argument("--workers", type=int, default=None)
    stage_names = [
        "prepare", "extract", "interventions", "oracle", "main", "e0", "contracts",
    ]
    ap.add_argument("--start-at", default="prepare", choices=stage_names)
    ap.add_argument("--stop-after", default="contracts", choices=stage_names)
    args = ap.parse_args()

    cfg_path = ROOT / args.config
    cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    prof = _profile(cfg, args.profile)
    for key in ("docs", "oracle_docs", "main_budget", "oracle_budget",
                "e0_docs", "e0_runs", "workers"):
        val = getattr(args, key.replace("_", "-"), None) if False else getattr(args, key, None)
        if val is not None:
            prof[key] = val

    run_name = args.run_name or f"{cfg.get('name', 'paper')}_{args.profile}"
    data_root = ROOT / (cfg.get("paths", {}).get("data_root") or "data/processed/runs")
    report_root = ROOT / (cfg.get("paths", {}).get("report_root") or "reports/runs")
    run_data = data_root / run_name
    run_report = report_root / run_name
    json_reports = run_data / "reports"
    db_path = run_data / f"{run_name}.db"
    log_path = run_data / "run.log"
    if not args.dry_run:
        run_data.mkdir(parents=True, exist_ok=True)
        json_reports.mkdir(parents=True, exist_ok=True)
        run_report.mkdir(parents=True, exist_ok=True)

    if args.fresh and not args.dry_run:
        for p in (db_path, Path(str(db_path) + "-wal"), Path(str(db_path) + "-shm")):
            if p.exists():
                p.unlink()

    env = dict(os.environ)
    if args.model:
        env["OPENAI_MODEL"] = args.model

    docred_cfg = cfg["dataset"]["config"]
    prompt_cfg = cfg["prompt_schema"]["prompt_config"]
    schema_cfg = cfg["prompt_schema"]["schema_config"]
    models_cfg = cfg["models"]["config"]
    split_arg = str(cfg["dataset"].get("splits", "validation"))
    workers = str(prof["workers"])
    db_args = ["--db", str(db_path)]
    common_cfg = ["--docred-config", docred_cfg]
    worker_args = ["--workers", workers]

    stages: list[tuple[str, list[str]]] = [
        ("prepare", [PY, "scripts/prepare_docred.py",
                     "--config", docred_cfg,
                     "--splits", split_arg,
                     "--limit", str(prof["docs"]),
                     *db_args]),
        ("extract", [PY, "scripts/run_extract.py",
                     *common_cfg,
                     "--prompts-config", prompt_cfg,
                     "--schemas-config", schema_cfg,
                     "--models-config", models_cfg,
                     "--limit", str(prof["docs"]),
                     "--skip-extracted",
                     *worker_args,
                     *db_args]),
        ("interventions", [PY, "scripts/generate_interventions.py",
                           *common_cfg,
                           "--limit", str(prof["docs"]),
                           "--schema-variants", *cfg["prompt_schema"]["schema_variants"],
                           "--prompt-clauses-to-drop", *cfg["prompt_schema"]["prompt_clauses_to_drop"],
                           "--max-drop-relations", str(cfg["prompt_schema"]["max_drop_relations"]),
                           *db_args]),
        ("oracle", [PY, "scripts/run_planners.py",
                    *common_cfg,
                    "--prompts-config", prompt_cfg,
                    "--schemas-config", schema_cfg,
                    "--models-config", models_cfg,
                    "--planner", "exhaustive",
                    "--budget", str(prof["oracle_budget"]),
                    "--limit", str(prof["oracle_docs"]),
                    *worker_args,
                    *db_args]),
        ("main", [PY, "scripts/run_planners.py",
                  *common_cfg,
                  "--prompts-config", prompt_cfg,
                  "--schemas-config", schema_cfg,
                  "--models-config", models_cfg,
                  "--planner", "graphguard",
                  "--budget", str(prof["main_budget"]),
                  "--limit", str(prof["docs"]),
                  *worker_args,
                  *db_args]),
        ("e0", [PY, "scripts/run_e0_stability.py",
                *common_cfg,
                "--prompts-config", prompt_cfg,
                "--schemas-config", schema_cfg,
                "--models-config", models_cfg,
                "--limit", str(prof["e0_docs"]),
                "--runs", str(prof["e0_runs"]),
                "--temperature", "0.3",
                "--report", str(json_reports / "e0_report.json"),
                *db_args]),
        ("contracts", [PY, "scripts/run_contracts.py",
                       "--db", str(db_path),
                       "--out", str(run_report / "eval" / "contracts.json"),
                       "--md",  str(run_report / "eval" / "contracts.md")]),
    ]

    order = stage_names
    started = order.index(args.start_at)
    stopped = order.index(args.stop_after)
    rc = 0
    if not args.dry_run:
        with log_path.open("a", encoding="utf-8") as log:
            log.write(
                f"\n=== run {run_name} profile={args.profile} db={db_path} ===\n"
            )
    for stage, cmd in stages:
        idx = order.index(stage)
        skip = idx < started or idx > stopped
        rc |= _run(cmd, skip=skip, env=env, dry_run=args.dry_run)
        if rc != 0:
            print(f"[error] stage={stage} rc={rc}", flush=True)
            break

    print(f"[done] rc={rc} run={run_name} db={db_path} reports={run_report}", flush=True)
    return 0 if rc == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
