"""Graph-only vs query-aware contract ablation.

For each base/cf pair, emits per-pair graph drift, query drift, and a
query-divergence label, then compares three monitors at the same alarm rate:

  - graph-only:   alarm if graph_drift > tau_g
  - query-aware:  alarm if max answer-set Jaccard drift > tau_q
  - hybrid (OR):  alarm if either fires

Detection target: mean absolute ΔF1 over 4 templates > 0.05. This includes
both regressions and improvements and is distinct from the directional label
in the Kuzu release-gate experiment.

Inputs are the frozen, schema-eligible full downstream populations. Outputs:
  reports/cross_run/graph_vs_query_formal_v1_<run>.json
"""

from __future__ import annotations

import argparse
import hashlib
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


def confusion(flags, harm):
    tp = fp = fn = tn = 0
    for f, h in zip(flags, harm):
        if f and h: tp += 1
        elif f and not h: fp += 1
        elif not f and h: fn += 1
        else: tn += 1
    n = tp + fp + fn + tn
    prec = tp / (tp + fp) if (tp + fp) else 0.0
    rec  = tp / (tp + fn) if (tp + fn) else 0.0
    f1   = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn,
            "alarm_rate": (tp + fp) / n if n else 0.0,
            "precision": round(prec, 4),
            "recall":    round(rec, 4),
            "f1":        round(f1, 4)}


def flags_at_count(scores, row_ids, n_alarm):
    """Flag exactly ``n_alarm`` rows, breaking score ties without labels.

    Answer-set drift is discrete and frequently tied at 0 or 1. A scalar
    threshold alone therefore cannot match another detector's alarm count.
    Stable SHA-256 ordering of run IDs supplies a reproducible, label-blind
    tie break.
    """
    n_alarm = max(0, min(len(scores), n_alarm))
    ranked = sorted(
        range(len(scores)),
        key=lambda index: (
            -scores[index],
            hashlib.sha256(row_ids[index].encode()).hexdigest(),
        ),
    )
    selected = set(ranked[:n_alarm])
    flags = [index in selected for index in range(len(scores))]
    assert sum(flags) == n_alarm
    boundary = scores[ranked[n_alarm - 1]] if n_alarm else float("inf")
    return flags, boundary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--out")
    ap.add_argument("--harm-th", type=float, default=0.05)
    args = ap.parse_args()

    artifact = load_formal_downstream(ROOT, args.run)
    rows = [
        {
            "run_id": pair["run_id"],
            "graph_drift": pair["graph_drift"],
            "query_drift": pair["max_answer_drift"],
            "mean_df1": pair["mean_delta_f1_abs"],
            "harmful": pair["mean_delta_f1_abs"] > args.harm_th,
        }
        for pair in artifact["per_pair"]
    ]

    harm = [r["harmful"] for r in rows]
    base_rate = sum(harm) / len(harm) if harm else 0.0

    # Matched alarm rate = the natural rate that graph-only achieves at tau_g=0.30
    g_scores = [r["graph_drift"] for r in rows]
    q_scores = [r["query_drift"] for r in rows]
    row_ids = [r["run_id"] for r in rows]

    out = {
        "artifact_type": "graphguard.graph_vs_query_ablation",
        "artifact_version": 1,
        "run": args.run,
        "source": {
            "formal_index": {
                "path": str(DEFAULT_INDEX),
                "sha256": sha256_file(ROOT / DEFAULT_INDEX),
            },
            "downstream_sha256": load_artifact_index(ROOT)["entries"][
                f"downstream:{args.run}"
            ]["raw_sha256"],
        },
        "n_pairs": len(rows),
        "label_definition": "mean absolute per-query F1 change > threshold",
        "query_monitor": "max answer-set Jaccard drift (gold-free at decision time)",
        "graph_monitor": "canonicalized typed-edge Jaccard drift",
        "matched_alarm_ties": (
            "exact top-k selection; score ties broken by SHA-256(run_id), "
            "without target labels"
        ),
        "harm_threshold_delta_f1": args.harm_th,
        "harmful_base_rate": round(base_rate, 4),
        "monitors_at_matched_alarm": {},
        "sweep": [],
    }

    # Sweep alarm rates 0.2..0.9 and report each monitor
    for target in [0.30, 0.50, 0.70, 0.90]:
        n_alarm = round(target * len(rows))
        gflags, tau_g = flags_at_count(g_scores, row_ids, n_alarm)
        qflags, tau_q = flags_at_count(q_scores, row_ids, n_alarm)
        hflags = [a or b for a, b in zip(gflags, qflags)]
        out["sweep"].append({
            "target_alarm": target,
            "tau_graph": round(tau_g, 4),
            "tau_query": round(tau_q, 4),
            "graph_only":  confusion(gflags, harm),
            "query_aware": confusion(qflags, harm),
            "hybrid_or":   confusion(hflags, harm),
        })

    # "Headline": pin tau_g = 0.30 (matches contract K3), report all 3 at that alarm rate
    tau_g_fixed = 0.30
    gflags = [s > tau_g_fixed for s in g_scores]
    nat_alarm = sum(gflags) / len(gflags) if gflags else 0.0
    qflags, tau_q = flags_at_count(q_scores, row_ids, sum(gflags))
    hflags = [a or b for a, b in zip(gflags, qflags)]
    out["monitors_at_matched_alarm"] = {
        "alarm_rate_target": round(nat_alarm, 4),
        "tau_graph_fixed":   tau_g_fixed,
        "tau_query":         round(tau_q, 4),
        "graph_only":        confusion(gflags, harm),
        "query_aware":       confusion(qflags, harm),
        "hybrid_or":         confusion(hflags, harm),
    }

    # Disagreement: pairs where graph_only and query_aware diverge
    disagree = sum(1 for g, q in zip(gflags, qflags) if g != q)
    out["disagreement_at_matched_alarm"] = {
        "pairs_disagree": disagree,
        "rate": round(disagree / len(rows), 4) if rows else 0.0,
        "graph_only_misses_harmful": sum(1 for g, q, h in zip(gflags, qflags, harm) if (not g) and q and h),
        "graph_only_false_alarms_on_benign": sum(1 for g, q, h in zip(gflags, qflags, harm) if g and (not q) and (not h)),
    }

    output = Path(args.out) if args.out else (
        ROOT / "reports" / "cross_run"
        / f"graph_vs_query_formal_v1_{args.run}.json"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(out, indent=2) + "\n")
    print(f"wrote {output}: n_pairs={len(rows)} base_rate={base_rate:.3f}")
    m = out["monitors_at_matched_alarm"]
    print(f"  @alarm={m['alarm_rate_target']:.3f}: "
          f"graph-only F1={m['graph_only']['f1']:.3f}, "
          f"query-aware F1={m['query_aware']['f1']:.3f}, "
          f"hybrid F1={m['hybrid_or']['f1']:.3f}")
    print(f"  disagreement: {out['disagreement_at_matched_alarm']}")


if __name__ == "__main__":
    main()
