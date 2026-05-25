"""CLI: check drift contracts on a recorded run-DB.

Usage:
    python scripts/run_contracts.py --db data/processed/runs/X/X.db \
                                    --out reports/runs/X/eval/contracts.json \
                                    --md  reports/runs/X/report.contracts.md
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from graphguard.contracts import REGISTRY, run_all


def write_md(report: dict, path: Path) -> None:
    lines = []
    s = report["summary"]
    lines.append("# Drift contract report\n")
    lines.append(
        f"**{s['n_satisfied']} satisfied · {s['n_violated']} violated · "
        f"{s['n_inconclusive']} inconclusive** "
        f"(of {s['n_contracts']} contracts)\n"
    )
    lines.append("| ID | Contract | Kind | Verdict | n | Viol-rate | Mean metric | Severity (μ / p95) |")
    lines.append("|---|---|---|---|---:|---:|---:|---:|")
    for r in report["contracts"]:
        lines.append(
            f"| {r['contract_id']} | {r['name']} | {r['kind']} | "
            f"**{r['verdict']}** | {r['n_pairs']} | {r['violation_rate']:.2f} | "
            f"{r['metric_mean']:.3f} | "
            f"{r['severity_mean']:.3f} / {r['severity_p95']:.3f} |"
        )
    lines.append("")
    lines.append("## Per-contract details\n")
    for r in report["contracts"]:
        lines.append(f"### {r['contract_id']} — {r['name']}  · *{r['verdict']}*\n")
        lines.append(f"- kind: `{r['kind']}` · direction: `{r['direction']}` · "
                     f"threshold: `{r['threshold']}`")
        lines.append(f"- scope: `{r['scope']}`")
        lines.append(f"- pairs: n={r['n_pairs']}, fail={r['n_fail']}, "
                     f"violation_rate={r['violation_rate']:.3f}")
        lines.append(f"- metric: mean={r['metric_mean']:.3f}, "
                     f"median={r['metric_median']:.3f}")
        if r["by_family"]:
            lines.append("- by family:")
            for fam, d in sorted(r["by_family"].items()):
                lines.append(
                    f"    - `{fam}` n={d['n']}, viol={d['violation_rate']:.2f}, "
                    f"mean_metric={d['mean_metric']:.3f}"
                )
        if r["threshold_sensitivity"]:
            lines.append("- threshold sensitivity (violation_rate at alt thresholds):")
            for t, vr in sorted(r["threshold_sensitivity"].items(), key=lambda x: float(x[0])):
                lines.append(f"    - τ={t}: {vr:.2f}")
        if r["examples"]:
            lines.append("- top violation examples:")
            for ex in r["examples"][:3]:
                lines.append(
                    f"    - doc=`{ex['doc']}` op=`{ex['operator']}` "
                    f"family=`{ex['family']}` metric={ex['metric']:.3f}"
                )
        lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--out", required=True, help="JSON output path")
    ap.add_argument("--md", required=False, help="Markdown report output path")
    ap.add_argument("--ids", nargs="*", default=None, help="optional subset of contract ids")
    args = ap.parse_args()

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    report = run_all(conn, contract_ids=args.ids)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")

    if args.md:
        write_md(report, Path(args.md))

    s = report["summary"]
    print(f"[contracts] satisfied={s['n_satisfied']} violated={s['n_violated']} "
          f"inconclusive={s['n_inconclusive']} (n={s['n_contracts']})")
    for r in report["contracts"]:
        print(f"  {r['contract_id']:>3}  {r['verdict']:<13} "
              f"n={r['n_pairs']:>4}  viol={r['violation_rate']:.2f}  "
              f"mean_m={r['metric_mean']:.3f}  ({r['name']})")


if __name__ == "__main__":
    main()
