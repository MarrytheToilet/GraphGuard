#!/usr/bin/env python3
"""Workload-regime analysis: where do query-aware contracts beat graph drift?
(PVLDB revision, Rev6-W3/D3.)

Splits the gold-grounded harmful-regression detection task by workload
regime instead of pooling all queries:

  local regime     — harm = mean gold DeltaF1 over lookup + neighbor > 0.05
  multi-hop regime — harm = mean gold DeltaF1 over join + two-hop  > 0.05

For each regime and corpus, two gold-free detectors are compared at the
SAME alarm rate (set to the regime's harm base rate): graph-only (edge
Jaccard drift) and query-aware (max answer-set drift over the regime's own
templates). This isolates the regimes in which query-aware contracts add
value over plain graph-drift scoring.

Writes reports/cross_run/regimes_<run>.json.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import statistics
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from graphguard.qa import build_queries, execute, f1, jaccard, load_data  # noqa: E402

MAIN_RUNS = [
    "docred__deepseek-v4-flash__300d",
    "redocred__deepseek-v4-flash__300d",
    "scierc__deepseek-v4-flash__100d",
    "cdr__deepseek-v4-flash__300d",
]

OUT_DIR = ROOT / "reports" / "cross_run"
HARM_TAU = 0.05
REGIMES = {"local": ("lookup", "neighbor"), "multihop": ("join", "twohop")}


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
    db = ROOT / "data" / "processed" / "runs" / run / f"{run}.db"
    if not db.exists():
        print(f"[skip] {run}: no db")
        return None
    con = sqlite3.connect(db)
    edges, gold, runs = load_data(con)

    qcache: dict = {}
    def queries_for(doc):
        if doc not in qcache:
            qcache[doc] = build_queries(gold.get(doc, set()))
        return qcache[doc]

    rows = []
    for run_id, base_ev, cf_ev, doc, fam, iv_id in runs:
        if not cf_ev or base_ev not in edges or cf_ev not in edges:
            continue
        bg, cg = edges[base_ev], edges[cf_ev]
        qs = queries_for(doc)
        if not qs:
            continue
        gdrift = 1.0 - jaccard(bg, cg)
        delta = defaultdict(list)   # gold DeltaF1 per template family
        adrift = defaultdict(list)  # gold-free answer drift per template family
        nonempty = defaultdict(bool)
        for q in qs:
            fam_q = q[0]
            pb, pc = execute(bg, q), execute(cg, q)
            delta[fam_q].append(abs(f1(pb, q[1]["gold"]) - f1(pc, q[1]["gold"])))
            adrift[fam_q].append(1.0 - jaccard(pb, pc))
            nonempty[fam_q] = nonempty[fam_q] or bool(pb) or bool(pc)
        row = {"graph_drift": gdrift}
        for regime, fams in REGIMES.items():
            ds = [d for f_ in fams for d in delta.get(f_, [])]
            qd = [d for f_ in fams for d in adrift.get(f_, [])]
            has_answer = any(nonempty.get(f_) for f_ in fams)
            if ds and has_answer:
                row[f"{regime}_harm"] = statistics.mean(ds) > HARM_TAU
                row[f"{regime}_qdrift"] = max(qd) if qd else 0.0
        rows.append(row)

    out = {"run": run, "n_pairs": len(rows), "harm_tau": HARM_TAU, "regimes": {}}
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
    out_path = OUT_DIR / f"regimes_{run}.json"
    out_path.write_text(json.dumps(out, indent=1))
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
