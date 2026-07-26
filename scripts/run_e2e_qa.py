"""End-to-end KG-QA divergence experiment.

For every (base, counterfactual) extraction pair in the lineage DB, build a
gold-grounded KG-QA workload from gold_edges, execute over base graph and CF
graph, and measure ΔAnswer-F1 per query family. Then:

  (A) Contract-as-divergence-detector: precision/recall/F1 of contract-flagged
      pairs at predicting absolute QA change (mean |ΔF1| > 0.05), compared
      against confidence-only and self-consistency-only monitors.
  (B) Borderline-stratified Wilson-CI early stopping: simulate sequential
      ordering, stop when CI half-width < 0.05, report % budget vs verdict
      agreement on satisfied / borderline / violated strata.
  (C) Per-query-family amplification of ΔF1 vs edge GraphDrift.

Pure post-processing of data/processed/runs/docred__deepseek-v4-flash__300d/.
"""

from __future__ import annotations
import argparse, json, sqlite3, statistics, random, sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from graphguard.qa import (                                  # noqa: E402
    build_queries, execute, f1, graph_jaccard, load_data, wilson_ci,
)

DB = "data/processed/runs/docred__deepseek-v4-flash__300d/docred__deepseek-v4-flash__300d.db"
OUT = Path("reports/cross_run/e2e_qa.json")


# --------------------------------------------------------------------- main

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=DB)
    parser.add_argument("--out", default=str(OUT))
    parser.add_argument("--max-runs", type=int, default=4000)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    con = sqlite3.connect(args.db)
    edges, gold, runs = load_data(con)
    random.seed(args.seed)
    if args.max_runs and len(runs) > args.max_runs:
        runs = random.sample(runs, args.max_runs)

    # Cache queries per document
    qcache = {}
    def queries_for(doc):
        if doc not in qcache:
            qcache[doc] = build_queries(gold.get(doc, set()))
        return qcache[doc]

    # Per-run metrics
    rows = []  # one per run
    by_family_qstats = defaultdict(lambda: {"deltaf1": [], "drift": []})

    for run_id, base_ev, cf_ev, doc, fam, iv_id in runs:
        if not cf_ev or base_ev not in edges or cf_ev not in edges:
            continue
        base_g = edges[base_ev]
        cf_g = edges[cf_ev]
        gold_set = gold.get(doc, set())
        # edge-level GraphDrift (Jaccard distance)
        drift = 1.0 - graph_jaccard(base_g, cf_g)
        # gold recall divergence
        rec_b = (len(base_g & gold_set) / len(gold_set)) if gold_set else 0.0
        rec_c = (len(cf_g & gold_set) / len(gold_set)) if gold_set else 0.0
        d_recall = abs(rec_b - rec_c)

        # QA over queries
        qs = queries_for(doc)
        if not qs:
            continue
        per_fam_delta = defaultdict(list)
        for q in qs:
            gold_q = q[1]["gold"]
            pred_b = execute(base_g, q)
            pred_c = execute(cf_g, q)
            f1_b = f1(pred_b, gold_q)
            f1_c = f1(pred_c, gold_q)
            d = abs(f1_b - f1_c)
            per_fam_delta[q[0]].append(d)
            by_family_qstats[q[0]]["deltaf1"].append(d)
            by_family_qstats[q[0]]["drift"].append(drift)
        mean_delta = statistics.mean([v for vs in per_fam_delta.values() for v in vs])
        rows.append({
            "run_id": run_id, "doc": doc, "cause_family": fam,
            "drift": drift, "delta_recall": d_recall,
            "mean_delta_f1": mean_delta,
            "per_family_delta_f1": {k: statistics.mean(v) for k, v in per_fam_delta.items()},
            "n_queries": len(qs),
        })

    # ----------------------------------- (A) detector P/R/F1
    HARM_TAU = 0.05
    DRIFT_TAU = 0.30
    # Use mean_delta_f1 > HARM_TAU as ground truth
    def evaluate(predicted_flags, truth_flags):
        tp = sum(1 for p, t in zip(predicted_flags, truth_flags) if p and t)
        fp = sum(1 for p, t in zip(predicted_flags, truth_flags) if p and not t)
        fn = sum(1 for p, t in zip(predicted_flags, truth_flags) if not p and t)
        tn = sum(1 for p, t in zip(predicted_flags, truth_flags) if not p and not t)
        prec = tp / (tp + fp) if tp + fp else 0.0
        rec = tp / (tp + fn) if tp + fn else 0.0
        f1v = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
        return {"tp": tp, "fp": fp, "fn": fn, "tn": tn,
                "alarm_rate": (tp + fp) / max(1, len(truth_flags)),
                "precision": prec, "recall": rec, "f1": f1v}

    truth = [r["mean_delta_f1"] > HARM_TAU for r in rows]
    base_rate = sum(truth) / len(truth) if truth else 0.0

    # Operating-point sweep on contract drift threshold
    drift_sweep = {}
    for tau in [0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70]:
        drift_sweep[f"contract_drift_>{tau}"] = evaluate(
            [r["drift"] > tau for r in rows], truth)

    # At matched alarm rate, compare to: (a) self-consistency only (stochastic-family),
    # (b) confidence-only random alarm, (c) random alarm.
    # We report contract at three operating points, and matched-budget baselines.
    contract_at = drift_sweep["contract_drift_>0.3"]
    matched_alarm = contract_at["alarm_rate"]
    rng = random.Random(1)
    detectors = {
        "contract_drift_tau_0.30": contract_at,
        "contract_drift_tau_0.50": drift_sweep["contract_drift_>0.5"],
        "self_consistency_only_drift_>0.30": evaluate(
            [r["drift"] > 0.30 and r["cause_family"] == "stochastic" for r in rows], truth),
        "confidence_only_random_matched_alarm": evaluate(
            [rng.random() < matched_alarm for _ in rows], truth),
        "exhaustive_oracle_drift_>0": evaluate(
            [r["drift"] > 0.0 for r in rows], truth),
    }

    # ----------------------------------- (B) stream-level Wilson-CI early stopping
    # Treat all pairs (pooled per cause_family) as a stream. Stop when CI half-width
    # of fraction-with-drift>tau is < HALF, then report budget %.
    HALF_OLD = 0.05
    by_family = defaultdict(list)
    for r in rows:
        by_family[r["cause_family"]].append(r["drift"] > DRIFT_TAU)


    # ----------------------------------- (B) Wilson-CI sequential stopping
    # Decision rule: contract is "violated" iff true violation rate p > alpha.
    # Stop when Wilson 95% CI excludes alpha (either lo>alpha => violated,
    # or hi<alpha => satisfied). Otherwise consume the full stream.
    ALPHA = 0.20
    HALF = 0.05  # max half-width fallback (only used if CI never excludes alpha)

    def simulate(stream_bool, n_trials=200, seed_base=1000):
        budgets = []
        agree = 0
        full_p = sum(stream_bool) / len(stream_bool)
        full_verdict = full_p > ALPHA
        for trial in range(n_trials):
            order = stream_bool[:]
            random.Random(seed_base + trial).shuffle(order)
            stopped = None
            verdict = None
            for i, _ in enumerate(order, 1):
                if i < 20:
                    continue
                p = sum(order[:i]) / i
                lo, hi = wilson_ci(p, i)
                if lo > ALPHA:
                    stopped, verdict = i, True
                    break
                if hi < ALPHA:
                    stopped, verdict = i, False
                    break
            if stopped is None:
                stopped = len(order)
                verdict = (sum(order) / len(order)) > ALPHA
            if verdict == full_verdict:
                agree += 1
            budgets.append(stopped / len(order))
        return {
            "n_pairs": len(stream_bool),
            "violation_rate_full": full_p,
            "mean_budget_fraction": statistics.mean(budgets),
            "verdict_agreement": agree / n_trials,
        }

    # (B1) natural workload
    stream_stopping = {}
    for fam, stream in by_family.items():
        if len(stream) < 30:
            continue
        stream_stopping[fam] = simulate(stream)

    # (B2) controlled-rate streams: synthesize p in {0.05, 0.18, 0.20, 0.22, 0.50}
    # by Bernoulli-resampling from the family's pos / neg pools.
    rate_streams = {}
    for fam, stream in by_family.items():
        if len(stream) < 100:
            continue
        pos = [x for x in stream if x]
        neg = [x for x in stream if not x]
        if len(pos) < 30 or len(neg) < 30:
            continue
        N = min(len(pos) + len(neg), 600)
        fam_seed = sum(ord(c) for c in fam) * 13
        per_rate = {}
        for target_p in [0.05, 0.18, 0.20, 0.22, 0.50]:
            n_pos = int(round(target_p * N))
            n_neg = N - n_pos
            rng = random.Random(fam_seed + 7000 + int(target_p * 1000))
            if n_pos > len(pos):
                samp_pos = [rng.choice(pos) for _ in range(n_pos)]
            else:
                samp_pos = rng.sample(pos, n_pos)
            if n_neg > len(neg):
                samp_neg = [rng.choice(neg) for _ in range(n_neg)]
            else:
                samp_neg = rng.sample(neg, n_neg)
            bs = samp_pos + samp_neg
            per_rate[f"p={target_p:.2f}"] = simulate(
                bs, n_trials=200, seed_base=fam_seed + 3000 + int(target_p * 1000)
            )
        rate_streams[fam] = per_rate


    # ----------------------------------- (C) per-family amplification
    family_amp = {}
    for fam, st in by_family_qstats.items():
        if not st["deltaf1"]:
            continue
        mean_delta = statistics.mean(st["deltaf1"])
        mean_drift = statistics.mean(st["drift"])
        family_amp[fam] = {
            "n": len(st["deltaf1"]),
            "mean_delta_f1": mean_delta,
            "mean_drift": mean_drift,
            "amplification": (mean_delta / mean_drift) if mean_drift > 0 else None,
        }

    out = {
        "n_runs_analyzed": len(rows),
        "label_definition": "mean absolute per-query F1 change > threshold",
        "harm_threshold_delta_f1": HARM_TAU,
        "drift_threshold_tau": DRIFT_TAU,
        "alpha": ALPHA,
        "harmful_base_rate": base_rate,
        "drift_threshold_sweep": drift_sweep,
        "detectors_at_matched_alarm": detectors,
        "stream_stopping_natural": stream_stopping,
        "stream_stopping_controlled_rate": rate_streams,
        "family_amplification": family_amp,
    }
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2))
    print(f"Wrote {out_path} ({len(rows)} runs analyzed)")
    print(json.dumps({"detectors": detectors,
                      "stream_natural": stream_stopping,
                      "stream_rates": rate_streams,
                      "family_amplification": family_amp}, indent=2))


if __name__ == "__main__":
    main()
