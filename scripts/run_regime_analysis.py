#!/usr/bin/env python3
"""Workload-regime analysis: where do query-aware contracts beat graph drift?
(PVLDB revision, Rev6-W3/D3.)

Splits the gold-grounded query-divergence detection task by workload
regime instead of pooling all queries:

  local regime     — mean absolute gold DeltaF1 over lookup + neighbor > 0.05
  multi-hop regime — mean absolute gold DeltaF1 over join + two-hop > 0.05

For each regime and corpus, two gold-free detectors target the regime's
label base rate: graph-only (edge Jaccard drift) and query-aware (max
answer-set drift over the regime's own templates). Thresholds are selected
as close as possible to that target. Because these scores are discrete and
often tied, the achieved alarm rates can differ; the regime split is
therefore a diagnostic F1 comparison rather than a strictly alarm-matched
experiment. The pooled policy comparison in run_graph_vs_query_ablation.py
is the rate-matched analysis.

Writes reports/cross_run/regimes_formal_v1_<run>.json.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from graphguard.formal_artifacts import (  # noqa: E402
    DEFAULT_INDEX,
    load_artifact_index,
    load_formal_downstream,
)
from graphguard.sqlite_snapshot import sha256_file  # noqa: E402

MAIN_RUNS = [
    "docred__deepseek-v4-flash__300d",
    "redocred__deepseek-v4-flash__300d",
    "scierc__deepseek-v4-flash__100d",
    "cdr__deepseek-v4-flash__300d",
]

OUT_DIR = ROOT / "reports" / "cross_run"
HARM_TAU = 0.05
REGIMES = {"local": ("lookup", "neighbor"), "multihop": ("join", "twohop")}
FORMAL_FAMILIES = {
    "lookup": "deployment.lookup",
    "neighbor": "deployment.neighbor",
    "join": "deployment.shared_tail_join",
    "twohop": "deployment.typed_two_hop",
}


def confusion(flags, harm):
    tp = sum(1 for a, h in zip(flags, harm) if a and h)
    fp = sum(1 for a, h in zip(flags, harm) if a and not h)
    fn = sum(1 for a, h in zip(flags, harm) if not a and h)
    tn = sum(1 for a, h in zip(flags, harm) if not a and not h)
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    return {
        "alarm_rate": (tp + fp) / max(1, len(harm)),
        "precision": round(prec, 4), "recall": round(rec, 4),
        "f1": round(2 * prec * rec / (prec + rec), 4) if prec + rec else 0.0,
    }


def flags_at_alarm(scores, target):
    """Alarm flags whose rate is closest to target, robust to score ties.

    Answer-drift scores saturate at 1.0 on dense corpora, so a strict '>'
    against the tie value can yield zero alarms; pick the comparison
    direction ('>' vs '>=') whose alarm rate lands closer to the target.
    """
    s = sorted(scores)
    k = max(0, min(len(s) - 1, int(round((1 - target) * len(s)))))
    tau = s[k]
    n = len(scores)
    gt = [x > tau for x in scores]
    ge = [x >= tau for x in scores]
    if abs(sum(gt) / n - target) <= abs(sum(ge) / n - target):
        return gt, tau, ">"
    return ge, tau, ">="


def analyze_run(run: str) -> dict | None:
    artifact = load_formal_downstream(ROOT, run)
    rows = []
    for pair in artifact["per_pair"]:
        row = {"graph_drift": pair["graph_drift"]}
        for regime, fams in REGIMES.items():
            summaries = [
                pair["families"][FORMAL_FAMILIES[family]]
                for family in fams
            ]
            n_queries = sum(item["n_queries"] for item in summaries)
            has_answer = any(
                item.get("has_nonempty_answer", False)
                for item in summaries
            )
            if n_queries and has_answer:
                mean_delta = sum(
                    item.get("mean_delta_f1_abs", 0.0)
                    * item["n_queries"]
                    for item in summaries
                ) / n_queries
                row[f"{regime}_harm"] = mean_delta > HARM_TAU
                row[f"{regime}_qdrift"] = max(
                    item.get("max_answer_drift", 0.0)
                    for item in summaries
                )
        rows.append(row)

    index = load_artifact_index(ROOT)
    out = {
        "artifact_type": "graphguard.query_regime_analysis",
        "artifact_version": 1,
        "run": run,
        "source": {
            "formal_index": {
                "path": str(DEFAULT_INDEX),
                "sha256": sha256_file(ROOT / DEFAULT_INDEX),
            },
            "downstream_sha256": index["entries"][
                f"downstream:{run}"
            ]["raw_sha256"],
        },
        "n_pairs": len(rows),
        "label_definition": (
            "regime mean absolute per-query F1 change > threshold"
        ),
        "harm_tau": HARM_TAU,
        "regimes": {},
    }
    for regime in REGIMES:
        rr = [r for r in rows if f"{regime}_harm" in r]
        if len(rr) < 50:
            continue
        harm = [r[f"{regime}_harm"] for r in rr]
        base_rate = sum(harm) / len(rr)
        g_scores = [r["graph_drift"] for r in rr]
        q_scores = [r[f"{regime}_qdrift"] for r in rr]
        g_flags, tg, g_cmp = flags_at_alarm(g_scores, base_rate)
        q_flags, tq, q_cmp = flags_at_alarm(q_scores, base_rate)
        g_conf = confusion(g_flags, harm)
        q_conf = confusion(q_flags, harm)
        out["regimes"][regime] = {
            "n": len(rr), "harm_base_rate": round(base_rate, 4),
            "tau_graph": round(tg, 4), "cmp_graph": g_cmp,
            "tau_query": round(tq, 4), "cmp_query": q_cmp,
            "graph_only": g_conf, "query_aware": q_conf,
            "delta_f1": round(q_conf["f1"] - g_conf["f1"], 4),
        }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / f"regimes_formal_v1_{run}.json"
    out_path.write_text(json.dumps(out, indent=1) + "\n")
    print(f"[done] {run}: {len(rows)} pairs -> {out_path}")
    for regime, s in out["regimes"].items():
        print(f"  {regime:<9} n={s['n']:<6} base={s['harm_base_rate']:.2f} "
              f"graphF1={s['graph_only']['f1']:.3f} queryF1={s['query_aware']['f1']:.3f} "
              f"dF1={s['delta_f1']:+.3f}")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", nargs="*", default=MAIN_RUNS)
    args = ap.parse_args()
    for run in args.runs:
        analyze_run(run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
