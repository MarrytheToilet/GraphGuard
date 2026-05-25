#!/usr/bin/env python3
"""Run the full GraphGuard experiment for multiple LLMs in series.

For each model we:
  1. Clone a "v0" DB (which already has prep + interventions + a baseline run)
     into a fresh per-model DB with model-dependent tables wiped.
  2. Run scripts/run_full_experiment.py with OPENAI_MODEL=<m>, --db=<per-model db>,
     --report-dir=data/processed/<model_safe>/, --out=reports/multi_model/<model_safe>/.
  3. Run scripts/visualize.py against that per-model DB.

After all models finish, write reports/multi_model/_compare.json + .md
aggregating each model's E2/E1/E3/E4/repair top-line numbers.

Usage:
  python scripts/run_multi_model_full.py --src-db data/processed/docred.db \
      --models deepseek-ai/DeepSeek-V4-Flash MiniMaxAI/MiniMax-M2.5 Qwen/Qwen3.6-27B \
      --limit 100 --budget 5 --e0-limit 20 --e0-runs 3
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable

DEFAULT_MODELS = [
    "deepseek-ai/DeepSeek-V4-Flash",
    "MiniMaxAI/MiniMax-M2.5",
    "Qwen/Qwen3.6-27B",
]


def safe(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("_")


def run(cmd: list[str], env: dict | None = None) -> int:
    print("[exec]", " ".join(cmd))
    t0 = time.time()
    rc = subprocess.call(cmd, cwd=str(ROOT), env=env)
    print(f"[exec] -> rc={rc} ({time.time()-t0:.1f}s)")
    return rc


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src-db", default="data/processed/docred.db",
                    help="Baseline DB (must have prep + interventions; usually v0 DeepSeek-V3).")
    ap.add_argument("--models", nargs="+", default=DEFAULT_MODELS)
    ap.add_argument("--limit", type=int, default=100)
    ap.add_argument("--budget", type=int, default=5)
    ap.add_argument("--e0-limit", type=int, default=20)
    ap.add_argument("--e0-runs", type=int, default=3)
    ap.add_argument("--cases", type=int, default=5)
    ap.add_argument("--workers", type=int, default=2,
                    help="Parallel workers passed to each full experiment run.")
    ap.add_argument("--out-root", default="reports/multi_model")
    ap.add_argument("--db-root", default="data/processed/multi_model")
    ap.add_argument("--keep-cache", action="store_true")
    ap.add_argument("--skip-clone", action="store_true",
                    help="Reuse existing per-model DB if present.")
    ap.add_argument("--skip-viz", action="store_true")
    args = ap.parse_args()

    src_db = Path(args.src_db)
    if not src_db.exists():
        print(f"[error] src-db not found: {src_db}", file=sys.stderr)
        return 1

    out_root = Path(args.out_root); out_root.mkdir(parents=True, exist_ok=True)
    db_root = Path(args.db_root); db_root.mkdir(parents=True, exist_ok=True)

    summary = []
    for model in args.models:
        s = safe(model)
        per_db = db_root / f"docred_{s}.db"
        per_out = out_root / s
        per_reports = Path("data/processed/multi_model") / s
        per_reports.mkdir(parents=True, exist_ok=True)

        print(f"\n========== MODEL: {model} ==========")
        if not args.skip_clone or not per_db.exists():
            rc = run([PY, "scripts/clone_db_for_model.py",
                     "--src", str(src_db), "--dst", str(per_db)] +
                    (["--keep-cache"] if args.keep_cache else []))
            if rc != 0:
                summary.append({"model": model, "stage": "clone", "rc": rc})
                continue

        env = dict(os.environ, OPENAI_MODEL=model)
        rc = run([PY, "scripts/run_full_experiment.py",
                  "--limit", str(args.limit),
                  "--budget", str(args.budget),
                  "--e0-limit", str(args.e0_limit),
                  "--e0-runs", str(args.e0_runs),
                  "--cases", str(args.cases),
                  "--workers", str(args.workers),
                  "--db", str(per_db),
                  "--report-dir", str(per_reports),
                  "--out", str(per_out),
                  "--skip-prepare"], env=env)

        if rc == 0 and not args.skip_viz:
            rc_viz = run([PY, "scripts/visualize.py",
                          "--db", str(per_db),
                          "--reports-dir", str(per_reports),
                          "--out", str(per_out / "viz"),
                          "--n-graphs", str(args.cases)], env=env)
        else:
            rc_viz = -1

        per_summary = {"model": model, "rc": rc, "rc_viz": rc_viz,
                       "db": str(per_db), "out": str(per_out)}
        # Pull top-line numbers if reports exist.
        for k in ("e0", "e1", "e2", "e3", "e4", "e5_audit", "repair"):
            p = per_reports / f"{k}_report.json"
            if p.exists():
                try:
                    per_summary[k] = json.loads(p.read_text())
                except Exception as e:
                    per_summary[k + "_error"] = str(e)
        summary.append(per_summary)

    # Cross-model comparison report.
    cmp_json = out_root / "_compare.json"
    cmp_json.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    md = ["# Multi-model GraphGuard comparison", ""]
    md.append("Primary claim: reliability **audit prioritization**, not F1 repair.")
    md.append("")
    md.append("| Model | E2 clean risk AUC-PR | E2 strict risk P@10% | E5 wrong-only risk errs/100 | E5 wrong-only random errs/100 | E1 Top-3 | E3 max flip | E4 best planner |")
    md.append("|---|---|---|---|---|---|---|---|")
    for s in summary:
        e2_modes = s.get("e2", {}).get("modes", {})
        e2_clean_risk = e2_modes.get("clean", {}).get("signals", {}).get("risk", {})
        e2_strict_risk = e2_modes.get("strict", {}).get("signals", {}).get("risk", {})
        e5_wrong = s.get("e5_audit", {}).get("modes", {}).get("wrong_only", {}).get("signals", {})
        e5_risk = e5_wrong.get("risk", {})
        e5_rand = e5_wrong.get("random", {})
        e1 = s.get("e1", {})
        e3 = s.get("e3", {}).get("flip_rates", {})
        e3_max = max((v.get("type_flip_rate", 0) for v in e3.values()), default=0) if isinstance(e3, dict) else 0
        e4 = s.get("e4", [])
        e4_best = ""
        if isinstance(e4, list) and e4:
            best = max(e4, key=lambda r: r.get("cause_recall_at_k", r.get("recall_at_k", 0)))
            e4_best = f"{best.get('planner','?')}@b={best.get('budget','?')} ({best.get('cause_recall_at_k', best.get('recall_at_k', 0)):.2f})"
        md.append(f"| {s['model']} | {e2_clean_risk.get('auc_pr', 0):.3f} | "
                  f"{e2_strict_risk.get('p@10pct', 0):.3f} | "
                  f"{e5_risk.get('errors_per_100_reviewed', 0):.1f} | "
                  f"{e5_rand.get('errors_per_100_reviewed', 0):.1f} | "
                  f"{e1.get('top3_recall', 0):.3f} | {e3_max:.2f} | {e4_best} |")
    (out_root / "_compare.md").write_text("\n".join(md), encoding="utf-8")

    print(f"\n[done] {len(summary)} models -> {cmp_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
