"""Budget-aware contract checking with CI-based early stopping.

Simulates: for each contract, instead of materializing all pair budget b, the
checker draws pairs sequentially and stops early once a Wilson 95% CI on the
violation rate is fully above α (clear violation) or fully below α (clear
satisfaction). Otherwise, keeps drawing up to budget b.

We replay this on the recorded DocRED main pairs and report:
  - mean pairs drawn (i.e., LLM calls saved)
  - verdict agreement with full-budget run
  - false-positive / false-negative rates introduced by early stopping

Output: reports/cross_run/budget_stopping.json
"""
from __future__ import annotations
import json, math, random, sys
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from graphguard.contracts import metrics as M  # noqa: E402
from graphguard.db.database import open_db  # noqa: E402

DB = "data/processed/runs/docred__deepseek-v4-flash__300d/docred__deepseek-v4-flash__300d.db"
OUT = Path("reports/cross_run/budget_stopping.json")

ALPHA = 0.20
FAM_TAU = {"schema": 0.10, "prompt": 0.15, "evidence": 0.50, "stochastic": 0.15, "entity_alias": 0.30}

def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    den = 1 + z*z/n
    center = (p + z*z/(2*n)) / den
    half = z * math.sqrt(p*(1-p)/n + z*z/(4*n*n)) / den
    return (max(0.0, center - half), min(1.0, center + half))

def jaccard_drift(a, b):
    if not a and not b:
        return 0.0
    return 1.0 - len(a & b) / max(1, len(a | b))

def main():
    import argparse, os
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=os.environ.get("CL_DB", DB))
    ap.add_argument("--out", default=os.environ.get("CL_OUT_BUDGET", str(OUT)))
    args = ap.parse_args()
    out_path = Path(args.out)
    con = open_db(args.db)
    cur = con.cursor()
    raw_edges_by_event = defaultdict(list)
    for eid, s, r, o in cur.execute("SELECT event_id, subject_name, relation, object_name FROM extracted_edges"):
        if s and r and o:
            raw_edges_by_event[eid].append({
                "subject_name": s, "relation": r, "object_name": o,
            })
    event_schema = dict(cur.execute(
        "SELECT event_id, schema_id FROM extraction_events"
    ))
    schemas = {
        schema_id: {row["id"] for row in json.loads(relations_json)}
        for schema_id, relations_json in cur.execute(
            "SELECT schema_id, relation_types_json FROM schemas"
        )
    }

    rows = cur.execute("""
        SELECT cr.run_id, cr.base_event_id, cr.cf_event_id, ic.cause_family
        FROM counterfactual_runs cr
        JOIN intervention_candidates ic ON cr.intervention_id = ic.intervention_id
        WHERE cr.status='ok' AND ic.cause_family IS NOT NULL
    """).fetchall()
    # Group pairs by family (treat each family as one contract for this simulation)
    by_fam = defaultdict(list)
    for run_id, be, ce, fam in rows:
        if not ce or not be:
            continue
        base_relation_ids = schemas.get(event_schema.get(be))
        m = 1.0 - M.edge_jaccard(
            raw_edges_by_event.get(be, []),
            raw_edges_by_event.get(ce, []),
            base_relation_ids=base_relation_ids,
        )
        violated = m > FAM_TAU.get(fam, 0.30)
        by_fam[fam].append(violated)

    def full_verdict(seq):
        if not seq:
            return "inconclusive"
        return "violated" if (sum(seq) / len(seq)) > ALPHA else "satisfied"

    def early_verdict(seq, budget):
        k = 0
        for i, v in enumerate(seq[:budget], start=1):
            if v:
                k += 1
            lo, hi = wilson(k, i)
            if lo > ALPHA:
                return "violated", i
            if hi < ALPHA and i >= 20:
                return "satisfied", i
        return full_verdict(seq[:budget]), min(budget, len(seq))

    rng = random.Random(7)
    summary = {}
    for fam, seq in by_fam.items():
        if len(seq) < 30:
            continue
        full = full_verdict(seq)
        # average over 100 random orderings
        savings = []
        agree = 0
        n_runs = 100
        for _ in range(n_runs):
            shuffled = seq[:]
            rng.shuffle(shuffled)
            ev, drawn = early_verdict(shuffled, budget=len(seq))
            savings.append(drawn / len(seq))
            if ev == full:
                agree += 1
        summary[fam] = {
            "n_pairs": len(seq),
            "full_verdict": full,
            "full_violation_rate": round(sum(seq)/len(seq), 4),
            "early_stopping_avg_fraction_drawn": round(sum(savings)/len(savings), 4),
            "early_stopping_verdict_agreement": round(agree/n_runs, 4),
        }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))

if __name__ == "__main__":
    main()
