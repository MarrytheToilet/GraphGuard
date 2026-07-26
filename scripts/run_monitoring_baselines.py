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
import json, statistics, re, sys
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from graphguard.contracts import metrics as M  # noqa: E402
from graphguard.db.database import open_db  # noqa: E402

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
    con = open_db(args.db)
    cur = con.cursor()
    gold_by_doc = defaultdict(set)
    for d, h, r, t in cur.execute("SELECT document_id, head_name, relation_base, tail_name FROM gold_edges"):
        if h and r and t:
            gold_by_doc[d].add((
                M._canon_entity(h), r, M._canon_entity(t)
            ))

    edges_by_event: dict[str, set] = defaultdict(set)
    raw_edges_by_event: dict[str, list] = defaultdict(list)
    conf_by_event: dict[str, list] = defaultdict(list)
    for eid, s, r, o, c in cur.execute(
        "SELECT event_id, subject_name, relation, object_name, confidence FROM extracted_edges"
    ):
        if s and r and o:
            raw_edges_by_event[eid].append({
                "subject_name": s, "relation": r, "object_name": o,
            })
        if c is not None:
            conf_by_event[eid].append(c)
    mean_conf = {e: (statistics.mean(cs) if cs else 0.0) for e, cs in conf_by_event.items()}

    event_meta = {
        event_id: (document_id, schema_id)
        for event_id, document_id, schema_id in cur.execute(
            "SELECT event_id, document_id, schema_id FROM extraction_events"
        )
    }
    doc_of_event = {
        event_id: document_id
        for event_id, (document_id, _) in event_meta.items()
    }
    schemas = {
        schema_id: {row["id"] for row in json.loads(relations_json)}
        for schema_id, relations_json in cur.execute(
            "SELECT schema_id, relation_types_json FROM schemas"
        )
    }

    def projected(event_id, base_relation_ids):
        return set(M._project(
            M._to_triples(raw_edges_by_event.get(event_id, [])),
            base_relation_ids,
        ))

    rows = cur.execute("""
        SELECT cr.run_id, cr.base_event_id, cr.cf_event_id, ic.cause_family
        FROM counterfactual_runs cr
        JOIN intervention_candidates ic ON cr.intervention_id = ic.intervention_id
        WHERE cr.status='ok' AND ic.cause_family IS NOT NULL
    """).fetchall()
    # Per-doc: collect base repeats for self-consistency baseline
    base_repeats = defaultdict(list)
    for be in {b for _, b, _, _ in rows if b}:
        d = doc_of_event.get(be)
        if d:
            base_repeats[d].append(be)
    majority_set = {}
    for d, evs in base_repeats.items():
        if len(evs) < 2:
            continue
        cnt = defaultdict(int)
        for e in evs:
            base_relation_ids = schemas.get(event_meta.get(e, (None, None))[1])
            for ed in projected(e, base_relation_ids):
                cnt[ed] += 1
        thr = max(2, len(evs) // 2 + 1)
        majority_set[d] = {ed for ed, c in cnt.items() if c >= thr}

    base_conf_q30 = {}
    base_means_by_doc = defaultdict(list)
    for be in {b for _, b, _, _ in rows if b}:
        d = doc_of_event.get(be)
        if d and be in mean_conf:
            base_means_by_doc[d].append(mean_conf[be])
    for d, vs in base_means_by_doc.items():
        vs = sorted(vs)
        base_conf_q30[d] = vs[max(0, len(vs) * 30 // 100)] if vs else 0.5

    pairs = []
    for run_id, be, ce, fam in rows:
        if not ce or not be:
            continue
        d = doc_of_event.get(be)
        gold = gold_by_doc.get(d, set())
        if not gold:
            continue
        base_relation_ids = schemas.get(
            event_meta.get(be, (None, None))[1]
        )
        ge = projected(be, base_relation_ids)
        gc = projected(ce, base_relation_ids)
        rb = len(ge & gold) / len(gold)
        rc = len(gc & gold) / len(gold)
        u = abs(rb - rc)
        m = 1.0 - M.edge_jaccard(
            raw_edges_by_event.get(be, []),
            raw_edges_by_event.get(ce, []),
            base_relation_ids=base_relation_ids,
        )
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
