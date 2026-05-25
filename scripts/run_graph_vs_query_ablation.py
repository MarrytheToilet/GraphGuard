"""Graph-only vs query-aware contract ablation.

For each base/cf pair, emits per-pair (graph_drift, query_drift, harmful)
tuples and compares three monitors at the same alarm rate:

  - graph-only:   alarm if graph_drift > tau_g
  - query-aware:  alarm if max-family ΔF1 > tau_q
  - hybrid (OR):  alarm if either fires

Detection target: harmful query regression, mean ΔF1 over 4 templates > 0.05.

Outputs:
  reports/cross_run/graph_vs_query_<dataset>__<model>__<n>d.json
"""

from __future__ import annotations
import argparse, json, sqlite3, random
from collections import defaultdict
from pathlib import Path

# reuse helpers from run_e2e_qa
import importlib.util, sys
spec = importlib.util.spec_from_file_location("rq", "scripts/run_e2e_qa.py")
rq = importlib.util.module_from_spec(spec); spec.loader.exec_module(rq)


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


def pick_tau_at_target_alarm(scores, target):
    """Return tau s.t. fraction of (score > tau) is closest to target."""
    if not scores: return float("inf")
    s = sorted(scores)
    k = int(round((1 - target) * len(s)))
    k = max(0, min(len(s) - 1, k))
    return s[k]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--harm-th", type=float, default=0.05)
    ap.add_argument("--max-runs", type=int, default=8000)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    con = sqlite3.connect(args.db)
    edges, gold, runs = rq.load_data(con)
    random.seed(args.seed)
    if args.max_runs and len(runs) > args.max_runs:
        runs = random.sample(runs, args.max_runs)

    qcache = {}
    def qfor(d):
        if d not in qcache: qcache[d] = rq.build_queries(gold.get(d, set()))
        return qcache[d]

    rows = []  # one per pair
    for run_id, base_ev, cf_ev, doc, fam, iv in runs:
        if not cf_ev or base_ev not in edges or cf_ev not in edges:
            continue
        base_g, cf_g = edges[base_ev], edges[cf_ev]
        qs = qfor(doc)
        if not qs: continue
        # label-erased graph_drift (endpoint-set Jaccard distance) to match K1 spirit
        be = {(s, o) for s, _, o in base_g}
        ce = {(s, o) for s, _, o in cf_g}
        graph_drift = 1.0 - rq.jaccard(be, ce)
        # per-family delta F1
        deltas = []
        max_qd = 0.0
        for q in qs:
            gq = q[1]["gold"]
            ab = rq.execute(base_g, q); ac = rq.execute(cf_g, q)
            db_ = rq.f1(ab, gq); dc = rq.f1(ac, gq)
            d = abs(db_ - dc)
            deltas.append(d)
            if d > max_qd: max_qd = d
        if not deltas: continue
        mean_df1 = sum(deltas) / len(deltas)
        rows.append({
            "graph_drift": graph_drift,
            "query_drift": max_qd,
            "mean_df1":   mean_df1,
            "harmful":    mean_df1 > args.harm_th,
        })

    harm = [r["harmful"] for r in rows]
    base_rate = sum(harm) / len(harm) if harm else 0.0

    # Matched alarm rate = the natural rate that graph-only achieves at tau_g=0.30
    g_scores = [r["graph_drift"] for r in rows]
    q_scores = [r["query_drift"] for r in rows]

    out = {
        "n_pairs": len(rows),
        "harm_threshold_delta_f1": args.harm_th,
        "harmful_base_rate": round(base_rate, 4),
        "monitors_at_matched_alarm": {},
        "sweep": [],
    }

    # Sweep alarm rates 0.2..0.9 and report each monitor
    for target in [0.30, 0.50, 0.70, 0.90]:
        tau_g = pick_tau_at_target_alarm(g_scores, target)
        tau_q = pick_tau_at_target_alarm(q_scores, target)
        gflags = [s > tau_g for s in g_scores]
        qflags = [s > tau_q for s in q_scores]
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
    tau_q = pick_tau_at_target_alarm(q_scores, nat_alarm)
    qflags = [s > tau_q for s in q_scores]
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

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(out, indent=2))
    print(f"wrote {args.out}: n_pairs={len(rows)} base_rate={base_rate:.3f}")
    m = out["monitors_at_matched_alarm"]
    print(f"  @alarm={m['alarm_rate_target']:.3f}: "
          f"graph-only F1={m['graph_only']['f1']:.3f}, "
          f"query-aware F1={m['query_aware']['f1']:.3f}, "
          f"hybrid F1={m['hybrid_or']['f1']:.3f}")
    print(f"  disagreement: {out['disagreement_at_matched_alarm']}")


if __name__ == "__main__":
    main()
