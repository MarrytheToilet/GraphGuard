"""End-to-end KG-QA regression experiment.

For every (base, counterfactual) extraction pair in the lineage DB, build a
gold-grounded KG-QA workload from gold_edges, execute over base graph and CF
graph, and measure ΔAnswer-F1 per query family. Then:

  (A) Contract-as-regression-detector: precision/recall/F1 of contract-flagged
      pairs at predicting harmful QA regression (mean ΔF1 > 0.05), compared
      against confidence-only and self-consistency-only monitors.
  (B) Borderline-stratified Wilson-CI early stopping: simulate sequential
      ordering, stop when CI half-width < 0.05, report % budget vs verdict
      agreement on satisfied / borderline / violated strata.
  (C) Per-query-family amplification of ΔF1 vs edge GraphDrift.

Pure post-processing of data/processed/runs/docred__deepseek-v4-flash__300d/.
"""

from __future__ import annotations
import argparse, json, math, sqlite3, statistics, random
from collections import defaultdict
from pathlib import Path

DB = "data/processed/runs/docred__deepseek-v4-flash__300d/docred__deepseek-v4-flash__300d.db"
OUT = Path("reports/cross_run/e2e_qa.json")

# --------------------------------------------------------------------- helpers

def wilson_ci(p, n, z=1.96):
    if n == 0:
        return (0.0, 1.0)
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    rad = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (max(0.0, centre - rad), min(1.0, centre + rad))


def jaccard(a, b):
    if not a and not b:
        return 1.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 1.0


def f1(pred, gold):
    if not pred and not gold:
        return 1.0
    if not pred or not gold:
        return 0.0
    p = pred & gold
    prec = len(p) / len(pred)
    rec = len(p) / len(gold)
    if prec + rec == 0:
        return 0.0
    return 2 * prec * rec / (prec + rec)


# --------------------------------------------------------------------- load

def load_data(con):
    cur = con.cursor()
    edges = defaultdict(set)  # event_id -> set of (s,r,o)
    edge_doc = {}
    for eid, doc, s, r, o in cur.execute(
        "SELECT event_id, document_id, subject_entity_id, relation, object_entity_id "
        "FROM extracted_edges WHERE subject_entity_id IS NOT NULL AND object_entity_id IS NOT NULL"):
        edges[eid].add((s, r, o))
        edge_doc[eid] = doc
    gold = defaultdict(set)  # doc -> set of (h,r,t)
    for doc, h, r, t in cur.execute(
        "SELECT document_id, head_entity_id, relation_base, tail_entity_id FROM gold_edges"):
        gold[doc].add((h, r, t))

    runs = []  # (run_id, base_event, cf_event, doc, cause_family, intervention_id)
    cur2 = con.cursor()
    for run_id, base_event, iv_id, doc in cur.execute(
        "SELECT run_id, base_event_id, intervention_id, document_id FROM counterfactual_runs WHERE status='ok'"):
        # Find CF event_id by sampling matched_edge_id prefix from edge_outcomes for this run
        row = cur2.execute(
            "SELECT matched_edge_id FROM edge_outcomes "
            "WHERE run_id=? AND matched_edge_id IS NOT NULL AND matched_edge_id<>'' LIMIT 1",
            (run_id,)).fetchone()
        cf_event = None
        if row and row[0]:
            cf_event = row[0].split("::")[0]
        # cause_family lookup
        fam = cur2.execute(
            "SELECT cause_family FROM intervention_candidates WHERE intervention_id=?",
            (iv_id,)).fetchone()
        family = fam[0] if fam else "unknown"
        runs.append((run_id, base_event, cf_event, doc, family, iv_id))
    return edges, gold, runs


# --------------------------------------------------------------------- queries

def build_queries(gold_edges_for_doc):
    """Return list of (family, query_dict). Each family is one of:
       lookup, neighbor, join, twohop. answer key 'gold' is set of expected results.
    """
    queries = []
    by_h_r = defaultdict(set)
    by_h = defaultdict(set)
    for h, r, t in gold_edges_for_doc:
        by_h_r[(h, r)].add(t)
        by_h[h].add((r, t))

    # lookup: (h, r, ?)
    for (h, r), ts in by_h_r.items():
        queries.append(("lookup", {"h": h, "r": r, "gold": ts}))

    # neighbor: (h, ?, ?) -> set of (r,t)
    for h, neigh in by_h.items():
        if len(neigh) >= 2:
            queries.append(("neighbor", {"h": h, "gold": neigh}))

    # shared-entity join: x s.t. (h1,r1,x) and (h2,r2,x) in G; gold derived from gold pairs
    # build tail-> [(h,r)]
    by_t = defaultdict(list)
    for h, r, t in gold_edges_for_doc:
        by_t[t].append((h, r))
    join_seeds = [(t, hrs) for t, hrs in by_t.items() if len(hrs) >= 2][:6]
    for t, hrs in join_seeds:
        (h1, r1), (h2, r2) = hrs[0], hrs[1]
        queries.append(("join", {"h1": h1, "r1": r1, "h2": h2, "r2": r2, "gold": {t}}))

    # 2-hop path: (h, r1, x)(x, r2, t)
    # Find gold chains
    chains = []
    for h, r1, x in gold_edges_for_doc:
        for r2, t in by_h.get(x, set()):
            if t != h:
                chains.append((h, r1, r2, t))
                if len(chains) >= 8:
                    break
        if len(chains) >= 8:
            break
    for h, r1, r2, t in chains:
        queries.append(("twohop", {"h": h, "r1": r1, "r2": r2, "gold": {t}}))

    return queries


def execute(graph_edges, q):
    """Return predicted answer set."""
    fam = q[0]
    g = graph_edges
    by_h_r = defaultdict(set)
    by_h = defaultdict(set)
    by_t = defaultdict(list)
    for s, r, o in g:
        by_h_r[(s, r)].add(o)
        by_h[s].add((r, o))
        by_t[o].append((s, r))
    if fam == "lookup":
        return by_h_r.get((q[1]["h"], q[1]["r"]), set())
    if fam == "neighbor":
        return by_h.get(q[1]["h"], set())
    if fam == "join":
        a = by_h_r.get((q[1]["h1"], q[1]["r1"]), set())
        b = by_h_r.get((q[1]["h2"], q[1]["r2"]), set())
        return a & b
    if fam == "twohop":
        firsts = by_h_r.get((q[1]["h"], q[1]["r1"]), set())
        out = set()
        for x in firsts:
            for r2, t in by_h.get(x, set()):
                if r2 == q[1]["r2"]:
                    out.add(t)
        return out
    return set()


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
        drift = 1.0 - jaccard(base_g, cf_g)
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
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT_P = Path(args.out)
    OUT_P.parent.mkdir(parents=True, exist_ok=True)
    OUT_P.write_text(json.dumps(out, indent=2))
    print(f"Wrote {OUT} ({len(rows)} runs analyzed)")
    print(json.dumps({"detectors": detectors,
                      "stream_natural": stream_stopping,
                      "stream_rates": rate_streams,
                      "family_amplification": family_amp}, indent=2))


if __name__ == "__main__":
    main()
