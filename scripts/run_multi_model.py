"""跑多个模型的 base extraction，用于 B2 多模型泛化性证据。

每个模型一次完整 extract → 共用同一组 documents / interventions / cf cache
通过 extraction_events.model_id 区分，下游 score / E2 可分模型聚合。

usage:
  python scripts/run_multi_model.py --limit 100 \
    --models deepseek-ai/DeepSeek-V3 deepseek-ai/DeepSeek-V4-Flash \
             MiniMaxAI/MiniMax-M2.5 Qwen/Qwen3.6-27B
"""
from __future__ import annotations
import argparse, os, subprocess, sys, time
from pathlib import Path

DEFAULT_MODELS = [
    "deepseek-ai/DeepSeek-V3",
    "deepseek-ai/DeepSeek-V4-Flash",
    "MiniMaxAI/MiniMax-M2.5",
    "Qwen/Qwen3.6-27B",
]


def run(cmd, env):
    print("[exec]", " ".join(cmd), f"OPENAI_MODEL={env['OPENAI_MODEL']}")
    r = subprocess.run(cmd, env=env)
    print(f"[done] rc={r.returncode}")
    return r.returncode


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=100)
    ap.add_argument("--budget", type=int, default=5)
    ap.add_argument("--models", nargs="+", default=DEFAULT_MODELS)
    ap.add_argument("--skip-cf", action="store_true",
                    help="只跑 base extraction，不跑 counterfactuals (速度快)")
    args = ap.parse_args()

    py = sys.executable
    base_env = os.environ.copy()

    summary = []
    for m in args.models:
        env = dict(base_env, OPENAI_MODEL=m)
        t0 = time.time()
        rc1 = run([py, "scripts/run_extract.py", "--limit", str(args.limit),
                   "--skip-extracted"], env)
        rc2 = 0
        if not args.skip_cf and rc1 == 0:
            rc2 = run([py, "scripts/run_planners.py",
                       "--planner", "graphguard", "--budget", str(args.budget),
                       "--limit", str(args.limit)], env)
        summary.append((m, rc1, rc2, round(time.time() - t0)))

    print("\n=== multi-model summary ===")
    for m, rc1, rc2, dt in summary:
        print(f"  {m:50s} extract_rc={rc1}  cf_rc={rc2}  {dt}s")


if __name__ == "__main__":
    main()
