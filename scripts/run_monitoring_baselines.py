"""Monitoring baselines: compare 4 strategies for flagging harmful drift.

Strategies (per (base, cf) pair, only on pairs with gold):
  (A) Confidence-only:    flag if mean confidence(cf) < q-quantile of base mean.
  (B) Self-consistency:   flag if cf disagrees with majority vote of base repeats.
  (C) Drift contracts:    flag if pair drift > catalogue threshold (per family).
  (D) Exhaustive (oracle cost): always flag — upper bound on recall, lower bound
      on precision; reported for cost-only comparison.

Ground truth: pair is "harmful" if |Δrecall_gold| > 0.05.
Metrics: precision, recall, F1, plus a cost proxy (LLM calls per flagged pair).

Output: reports/cross_run/monitoring_baselines.json
"""
from __future__ import annotations
import json, sqlite3, statistics, re
from pathlib import Path
from collections import defaultdict

DB = "data/processed/runs/docred__deepseek-v4-flash__300d/docred__deepseek-v4-flash__300d.db"
OUT = Path("reports/cross_run/monitoring_baselines.json")

# Per-family thresholds matching paper catalogue
FAM_TAU = {"schema": 0.10, "prompt": 0.15, "evidence": 0.50, "stochastic": 0.15, "entity_alias": 0.30}

def jaccard_drift(a, b):
    if not a and not b:
        return 0.0
    return 1.0 - len(a & b) / max(1, len(a | b))

def main():
    import argparse, os
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=os.environ.get("CL_DB", DB))
    ap.add_argument("--out", default=os.environ.get("CL_OUT_MONITORING", str(OUT)))
    args = ap.parse_args()
    out_path = Path(args.out)
    con = sqlite3.connect(args.db)
    cur = con.cursor()
    gold_by_doc = defaultdict(set)
    for d, h, r, t in cur.execute("SELECT document_id, head_name, relation_base, tail_name FROM gold_edges"):
        if h and r and t:
            gold_by_doc[d].add((h.lower(), r, t.lower()))

    edges_by_event: dict[str, set] = defaultdict(set)
    conf_by_event: dict[str, list] = defaultdict(list)
    for eid, s, r, o, c in cur.execute(
        "SELECT event_id, subject_name, relation, object_name, confidence FROM extracted_edges"
    ):
        if s and r and o:
            edges_by_event[eid].add((s.lower(), r, o.lower()))
        if c is not None:
            conf_by_event[eid].append(c)
    mean_conf = {e: (statistics.mean(cs) if cs else 0.0) for e, cs in conf_by_event.items()}

    doc_of_event = dict(cur.execute("SELECT event_id, document_id FROM extraction_events"))

    rows = cur.execute("""
        SELECT cr.run_id, cr.base_event_id, ic.cause_family
        FROM counterfactual_runs cr
        JOIN intervention_candidates ic ON cr.intervention_id = ic.intervention_id
        WHERE cr.status='ok' AND ic.cause_family IS NOT NULL
    """).fetchall()
    cf_event = {}
    for run_id, _, _ in rows:
        r = cur.execute(
            "SELECT matched_edge_id FROM edge_outcomes WHERE run_id=? AND matched_edge_id IS NOT NULL LIMIT 1",
            (run_id,)
        ).fetchone()
        if r and r[0] and "::" in r[0]:
            cf_event[run_id] = r[0].rsplit("::", 1)[0]

    # Per-doc: collect base repeats for self-consistency baseline
    base_repeats = defaultdict(list)
    for be in {b for _, b, _ in rows if b}:
        d = doc_of_event.get(be)
        if d:
            base_repeats[d].append(be)
    majority_set = {}
    for d, evs in base_repeats.items():
        if len(evs) < 2:
            continue
        cnt = defaultdict(int)
        for e in evs:
            for ed in edges_by_event.get(e, set()):
                cnt[ed] += 1
        thr = max(2, len(evs) // 2 + 1)
        majority_set[d] = {ed for ed, c in cnt.items() if c >= thr}

    base_conf_q30 = {}
    base_means_by_doc = defaultdict(list)
    for be in {b for _, b, _ in rows if b}:
        d = doc_of_event.get(be)
        if d and be in mean_conf:
            base_means_by_doc[d].append(mean_conf[be])
    for d, vs in base_means_by_doc.items():
        vs = sorted(vs)
        base_conf_q30[d] = vs[max(0, len(vs) * 30 // 100)] if vs else 0.5

    pairs = []
    for run_id, be, fam in rows:
        ce = cf_event.get(run_id)
        if not ce or not be:
            continue
        d = doc_of_event.get(be)
        gold = gold_by_doc.get(d, set())
        if not gold:
            continue
        ge = edges_by_event.get(be, set())
        gc = edges_by_event.get(ce, set())
        rb = len(ge & gold) / len(gold)
        rc = len(gc & gold) / len(gold)
        u = abs(rb - rc)
        m = jaccard_drift(ge, gc)
        # baselines
        flag_conf = mean_conf.get(ce, 1.0) < base_conf_q30.get(d, 0.5)
        maj = majority_set.get(d)
        flag_sc = (jaccard_drift(gc, maj) > 0.30) if maj else False
        flag_contract = m > FAM_TAU.get(fam, 0.30)
        pairs.append({
            "fam": fam, "u": u, "harmful": u > 0.05,
            "flag_conf": flag_conf, "flag_sc": flag_sc, "flag_contract": flag_contract,
        })

    def prf(pairs, key):
        tp = sum(1 for p in pairs if p[key] and p["harmful"])
        fp = sum(1 for p in pairs if p[key] and not p["harmful"])
        fn = sum(1 for p in pairs if not p[key] and p["harmful"])
        tn = sum(1 for p in pairs if not p[key] and not p["harmful"])
        n_flag = tp + fp
        prec = tp / max(1, n_flag)
        rec = tp / max(1, tp + fn)
        f1 = 2 * prec * rec / max(1e-9, prec + rec)
        return {
            "flagged": n_flag, "harmful": tp + fn,
            "precision": round(prec, 4), "recall": round(rec, 4), "f1": round(f1, 4),
            "flag_rate": round(n_flag / max(1, len(pairs)), 4),
        }

    out = {
        "n_pairs": len(pairs),
        "harmful_pairs": sum(1 for p in pairs if p["harmful"]),
        "confidence_only":  prf(pairs, "flag_conf"),
        "self_consistency_only": prf(pairs, "flag_sc"),
        "drift_contracts":  prf(pairs, "flag_contract"),
        "exhaustive": {"flagged": len(pairs), "precision": round(sum(1 for p in pairs if p["harmful"]) / max(1, len(pairs)), 4), "recall": 1.0},
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=2))

if __name__ == "__main__":
    main()
