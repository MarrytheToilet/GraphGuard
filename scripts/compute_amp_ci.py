#!/usr/bin/env python3
"""Compute bootstrap 95% CIs for Amp(Q) per query and per run.

Writes:
  reports/cross_run/amp_ci.json
  reports/cross_run/amp_ci.md   (paper-ready table)
"""
from __future__ import annotations
import json, os, math, random
from pathlib import Path
from collections import defaultdict

RUNS = [
    "docred__deepseek-v4-flash__300d", "redocred__deepseek-v4-flash__300d",
    "scierc__deepseek-v4-flash__100d", "cdr__deepseek-v4-flash__300d",
    "docred__glm-5__100d",
    "docred__kimi-k2__100d", "docred__qwen3-32b__100d",
]
ROOT = Path(__file__).resolve().parent.parent
B = 1000
random.seed(0)


def boot_ci(values, B=1000, alpha=0.05):
    n = len(values)
    if n == 0:
        return (float("nan"), float("nan"), float("nan"))
    means = []
    for _ in range(B):
        s = 0.0
        for _ in range(n):
            s += values[random.randrange(n)]
        means.append(s / n)
    means.sort()
    lo = means[int(B * alpha / 2)]
    hi = means[int(B * (1 - alpha / 2))]
    mean = sum(values) / n
    return mean, lo, hi


def main():
    out = {}
    for run in RUNS:
        f = ROOT / "reports/runs" / run / "eval" / "e8_amplification.json"
        if not f.exists():
            print("skip", run)
            continue
        data = json.load(open(f))
        per_q = defaultdict(list)
        per_q_qd = defaultdict(list)
        per_q_gd = defaultdict(list)
        for o in data["per_obs"]:
            per_q[o["query"]].append(o["amp"])
            per_q_qd[o["query"]].append(o["query_drift"])
            per_q_gd[o["query"]].append(o["graph_drift"])
        run_out = {}
        for q in sorted(per_q):
            mean, lo, hi = boot_ci(per_q[q], B=B)
            qd = sum(per_q_qd[q]) / len(per_q_qd[q])
            gd = sum(per_q_gd[q]) / len(per_q_gd[q])
            run_out[q] = {
                "n": len(per_q[q]),
                "amp_mean": mean,
                "amp_ci_lo": lo,
                "amp_ci_hi": hi,
                "query_drift_mean": qd,
                "graph_drift_mean": gd,
                "amp_ratio_of_means": (qd / (gd + 1e-9)) if gd > 0 else float("nan"),
            }
        out[run] = run_out
    out_path = ROOT / "reports/cross_run/amp_ci.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    json.dump(out, open(out_path, "w"), indent=2)
    print("wrote", out_path)

    # Markdown table for paper insertion
    md = ["# Amp(Q) bootstrap 95% CIs (B=1000, mean of per-pair ratios)", ""]
    md.append("| run | query | n | Amp mean | 95% CI | Amp(ratio-of-means) |")
    md.append("|---|---|---:|---:|---|---:|")
    for run, qs in out.items():
        for q, st in qs.items():
            md.append(
                f"| {run} | {q} | {st['n']} | {st['amp_mean']:.3f} | "
                f"[{st['amp_ci_lo']:.3f}, {st['amp_ci_hi']:.3f}] | "
                f"{st['amp_ratio_of_means']:.3f} |"
            )
    md_path = ROOT / "reports/cross_run/amp_ci.md"
    md_path.write_text("\n".join(md) + "\n")
    print("wrote", md_path)


if __name__ == "__main__":
    main()
