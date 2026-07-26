"""Matched alarm-rate / matched-cost baseline comparison.

For each (base, cf) pair (with gold), emit five continuous monitor scores:
  - confidence_inv : 1 - mean(cf edge confidence)
  - min_confidence_inv : 1 - min(cf edge confidence)
  - self_consistency : Jaccard drift between cf graph and majority-vote graph
                       across base repeats of the same document
  - graph_only_drift : Jaccard drift between base and cf edge sets
  - contract (= our query-aware monitor) : per-family contract severity,
                       defined as graph_drift / fam_tau (so contract fires when
                       severity > 1.0)

Positive label: absolute gold-recall change |delta_recall_gold| > 0.05.

For each monitor, sweep the score threshold to match alarm rates from
{baseline alarm rate, GraphGuard alarm rate, 0.10, 0.20, 0.30, 0.50} and
report precision/recall/F1. Also report cost proxy: extraction calls per
flagged pair (self-consistency at k=5 base repeats = 5x; the rest = 2x).

Output: reports/cross_run/baselines_matched_<dataset>.json
"""
from __future__ import annotations
import argparse, json, statistics, sys
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from graphguard.contracts import metrics as M  # noqa: E402
from graphguard.db.database import open_db  # noqa: E402


FAM_TAU = {"schema": 0.10, "prompt": 0.15, "evidence": 0.50,
           "stochastic": 0.15, "entity_alias": 0.30, "model": 0.30}


def jaccard_drift(a, b):
    if not a and not b:
        return 0.0
    return 1.0 - len(a & b) / max(1, len(a | b))


def metrics_at_threshold(pairs, key, thr):
    tp = fp = fn = tn = 0
    for p in pairs:
        flag = p[key] >= thr
        if flag and p["harmful"]:
            tp += 1
        elif flag and not p["harmful"]:
            fp += 1
        elif (not flag) and p["harmful"]:
            fn += 1
        else:
            tn += 1
    n_flag = tp + fp
    prec = tp / max(1, n_flag)
    rec = tp / max(1, tp + fn)
    f1 = 2 * prec * rec / max(1e-9, prec + rec)
    n = len(pairs)
    return {
        "threshold": round(thr, 4),
        "alarm_rate": round(n_flag / max(1, n), 4),
        "precision": round(prec, 4),
        "recall": round(rec, 4),
        "f1": round(f1, 4),
    }


def threshold_for_alarm_rate(pairs, key, target_rate):
    scores = sorted([p[key] for p in pairs], reverse=True)
    if not scores:
        return float("inf")
    k = max(1, min(len(scores), int(round(target_rate * len(scores)))))
    # threshold = k-th largest score; flag = score >= threshold flags ~k pairs
    return scores[k - 1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--harm-th", type=float, default=0.05)
    args = ap.parse_args()

    con = open_db(args.db)
    cur = con.cursor()

    gold_by_doc = defaultdict(set)
    for d, h, r, t in cur.execute(
        "SELECT document_id, head_name, relation_base, tail_name FROM gold_edges"
    ):
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
    min_conf = {e: (min(cs) if cs else 0.0) for e, cs in conf_by_event.items()}

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

    rows = cur.execute(
        """
        SELECT cr.run_id, cr.base_event_id, cr.cf_event_id, ic.cause_family
        FROM counterfactual_runs cr
        JOIN intervention_candidates ic
          ON cr.intervention_id = ic.intervention_id
        WHERE cr.status='ok' AND ic.cause_family IS NOT NULL
        """
    ).fetchall()
    # Self-consistency majority graph per document
    base_repeats = defaultdict(set)
    for _, be, _, _ in rows:
        d = doc_of_event.get(be)
        if d and be:
            base_repeats[d].add(be)
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
        maj = majority_set.get(d)
        sc = jaccard_drift(gc, maj) if maj is not None else 0.0
        tau = FAM_TAU.get(fam, 0.30)
        contract_sev = m / tau  # >=1.0 means firing
        pairs.append({
            "family": fam,
            "harmful": u > args.harm_th,
            "confidence_inv": 1.0 - mean_conf.get(ce, 0.5),
            "min_confidence_inv": 1.0 - min_conf.get(ce, 0.5),
            "self_consistency": sc,
            "graph_only_drift": m,
            "contract_severity": contract_sev,
        })

    if not pairs:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps({"n_pairs": 0}, indent=2))
        return

    base_rate = sum(1 for p in pairs if p["harmful"]) / len(pairs)
    # GraphGuard reference: alarm-rate at contract_severity >= 1.0
    gg_alarm = sum(1 for p in pairs if p["contract_severity"] >= 1.0) / len(pairs)

    sweep_rates = sorted({gg_alarm, 0.10, 0.20, 0.30, 0.50})
    cost_per_flag = {
        "confidence_inv": 1, "min_confidence_inv": 1,
        "self_consistency": 5,
        "graph_only_drift": 2, "contract_severity": 2,
    }

    out = {
        "n_pairs": len(pairs),
        "harmful_base_rate": round(base_rate, 4),
        "graphguard_alarm_rate": round(gg_alarm, 4),
        "graphguard_at_fixed_threshold": metrics_at_threshold(
            pairs, "contract_severity", 1.0
        ),
        "by_monitor": {},
    }
    for key in [
        "confidence_inv", "min_confidence_inv", "self_consistency",
        "graph_only_drift", "contract_severity",
    ]:
        sweep = []
        for rate in sweep_rates:
            thr = threshold_for_alarm_rate(pairs, key, rate)
            m = metrics_at_threshold(pairs, key, thr)
            m["target_alarm_rate"] = round(rate, 4)
            m["cost_per_flag_relative"] = cost_per_flag[key]
            sweep.append(m)
        out["by_monitor"][key] = sweep

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(out, indent=2))
    print(json.dumps({"n_pairs": out["n_pairs"],
                      "harmful_base_rate": out["harmful_base_rate"],
                      "graphguard_alarm_rate": out["graphguard_alarm_rate"]}, indent=2))


if __name__ == "__main__":
    main()
