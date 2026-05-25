"""SLA-calibrated thresholds: tie each contract's τ to a gold-utility regression target.

For each contract C with metric M and (base, cf) pairs, we have:
  - drift m = M(G_base, G_cf)
  - utility loss u = max(0, recall(G_base, gold) - recall(G_cf, gold))

An operator who sets an SLA "release-block whenever expected u > U_max" wants τ
such that P(u > U_max | m > τ) is high (precision of contract violation as a
release-blocker) and the violation budget α is met by historical baselines.

We compute, per contract:
  - τ at quantiles 0.5, 0.7, 0.9 of m
  - operator metrics at each τ: violation rate r_v, expected u above τ,
    precision (fraction of violating pairs with u > 0.05), recall (fraction
    of pairs with u > 0.05 that are flagged as violating).

Output: reports/cross_run/threshold_sla.json
"""
from __future__ import annotations
import json, sqlite3, statistics, re
from pathlib import Path
from collections import defaultdict

DB = "data/processed/runs/docred__deepseek-v4-flash__300d/docred__deepseek-v4-flash__300d.db"
OUT = Path("reports/cross_run/threshold_sla.json")

P_RX = re.compile(r"^P\d+$")

def jaccard_drift(a, b):
    if not a and not b:
        return 0.0
    return 1.0 - len(a & b) / max(1, len(a | b))

def recall(extracted: set, gold: set) -> float:
    if not gold:
        return None
    return len(extracted & gold) / len(gold)

def main():
    import argparse, os
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=os.environ.get("CL_DB", DB))
    ap.add_argument("--out", default=os.environ.get("CL_OUT_SLA", str(OUT)))
    args = ap.parse_args()
    out_path = Path(args.out)
    con = sqlite3.connect(args.db)
    cur = con.cursor()
    # Gold per doc
    gold_by_doc = defaultdict(set)
    for d, h, r, t in cur.execute(
        "SELECT document_id, head_name, relation_base, tail_name FROM gold_edges"
    ).fetchall():
        if h and r and t:
            gold_by_doc[d].add((h.lower(), r, t.lower()))

    # Edges per event
    edges_by_event: dict[str, set] = {}
    for eid, s, r, o in cur.execute(
        "SELECT event_id, subject_name, relation, object_name FROM extracted_edges"
    ).fetchall():
        if eid not in edges_by_event:
            edges_by_event[eid] = set()
        if s and r and o:
            edges_by_event[eid].add(((s or "").lower(), r, (o or "").lower()))

    # Doc per event
    doc_of_event = {eid: d for eid, d in cur.execute(
        "SELECT event_id, document_id FROM extraction_events"
    ).fetchall()}

    # cf runs with families
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

    # Build per-family pair list with (drift, utility_loss)
    by_family = defaultdict(list)
    overall = []
    for run_id, be, fam in rows:
        ce = cf_event.get(run_id)
        if not ce or not be:
            continue
        ge = edges_by_event.get(be, set())
        gc = edges_by_event.get(ce, set())
        d = doc_of_event.get(be)
        gold = gold_by_doc.get(d, set())
        m = jaccard_drift(ge, gc)
        rb = recall(ge, gold) if gold else None
        rc = recall(gc, gold) if gold else None
        if rb is None or rc is None:
            u = None
        else:
            u = abs(rb - rc)
        by_family[fam].append((m, u))
        overall.append((m, u))

    def quantile(xs, q):
        if not xs:
            return None
        s = sorted(xs)
        i = int(round(q * (len(s) - 1)))
        return s[i]

    def report(pairs, U_max=0.05):
        ms = [m for m, _ in pairs]
        ms_with_u = [(m, u) for m, u in pairs if u is not None]
        n = len(pairs)
        n_u = len(ms_with_u)
        positives = [m for m, u in ms_with_u if u > U_max]
        out = {
            "n_pairs": n,
            "n_with_gold": n_u,
            "frac_harmful_u_gt_0.05": round(len(positives) / max(1, n_u), 4),
        }
        for q in [0.5, 0.7, 0.9]:
            tau = quantile(ms, q)
            if tau is None:
                continue
            tp = sum(1 for m, u in ms_with_u if m > tau and u > U_max)
            fp = sum(1 for m, u in ms_with_u if m > tau and u <= U_max)
            fn = sum(1 for m, u in ms_with_u if m <= tau and u > U_max)
            tn = sum(1 for m, u in ms_with_u if m <= tau and u <= U_max)
            prec = tp / max(1, tp + fp)
            rec = tp / max(1, tp + fn)
            mean_u_above = round(statistics.mean([u for m, u in ms_with_u if m > tau]), 4) if (tp + fp) else None
            out[f"tau_q{int(q*100)}"] = {
                "tau": round(tau, 4),
                "violation_rate": round((tp + fp) / max(1, n_u), 4),
                "precision_for_harmful": round(prec, 4),
                "recall_for_harmful": round(rec, 4),
                "mean_u_above_tau": mean_u_above,
            }
        return out

    summary = {"overall": report(overall)}
    for fam, pairs in by_family.items():
        summary[fam] = report(pairs)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))

if __name__ == "__main__":
    main()
