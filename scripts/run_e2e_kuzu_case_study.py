"""End-to-end case study: contract-guarded graph ingestion.

For a small subset of DocRED documents (no new LLM calls), for each
(base, counterfactual) pair we:

  1. Ingest base and counterfactual edge sets as Kuzu property graphs
     (one ephemeral in-memory DB per graph).
  2. Run four real Cypher queries (lookup, neighbor, join, twohop).
  3. Compute query regression vs gold answers (ΔF1 per query).
  4. Compare two ingestion policies:
       - publish-all:    publish the cf graph regardless of contract verdict
       - contract-guard: block publishing whenever GraphGuard's drift contract
                         (label-erased Jaccard distance > 0.30 OR query-aware
                          alarm fires) flags the pair as drifted

We report, per dataset, the harmful-regression rate (a) without GraphGuard
and (b) with the contract guard, plus the audit cost saved.

Output: reports/cross_run/e2e_kuzu_case_<dataset>__deepseek-v4-flash__<n>d.json
"""

from __future__ import annotations
import argparse, json, sqlite3, random, importlib.util, shutil, tempfile, os
from pathlib import Path
from collections import defaultdict

import kuzu

spec = importlib.util.spec_from_file_location("rq", "scripts/run_e2e_qa.py")
rq = importlib.util.module_from_spec(spec); spec.loader.exec_module(rq)


def safe_id(x):
    return str(x).replace("'", "_").replace('"', "_")


def kuzu_load(edges):
    """Load edges into an ephemeral Kuzu DB; return connection."""
    tmp = tempfile.mkdtemp(prefix="ggkuzu_")
    path = os.path.join(tmp, "db")
    db = kuzu.Database(path)
    con = kuzu.Connection(db)
    con.execute("CREATE NODE TABLE Entity(id STRING, PRIMARY KEY(id))")
    con.execute("CREATE REL TABLE Rel(FROM Entity TO Entity, label STRING)")
    nodes = {n for e in edges for n in (e[0], e[2])}
    for n in nodes:
        con.execute("CREATE (e:Entity {id: $i})", parameters={"i": safe_id(n)})
    for s, r, o in edges:
        con.execute(
            "MATCH (a:Entity {id: $s}), (b:Entity {id: $o}) "
            "CREATE (a)-[:Rel {label: $r}]->(b)",
            parameters={"s": safe_id(s), "o": safe_id(o), "r": safe_id(r)})
    return con, db, tmp


def kuzu_close(con, db, tmp):
    del con; del db
    shutil.rmtree(tmp, ignore_errors=True)


def cypher_lookup(con, h, r):
    res = con.execute(
        "MATCH (a:Entity {id:$h})-[e:Rel {label:$r}]->(b) RETURN b.id",
        parameters={"h": safe_id(h), "r": safe_id(r)})
    return {row[0] for row in res}


def cypher_neighbor(con, h):
    res = con.execute(
        "MATCH (a:Entity {id:$h})-[e:Rel]->(b) RETURN e.label, b.id",
        parameters={"h": safe_id(h)})
    return {(row[0], row[1]) for row in res}


def cypher_join(con, h1, r1, h2, r2):
    a = cypher_lookup(con, h1, r1)
    b = cypher_lookup(con, h2, r2)
    return a & b


def cypher_twohop(con, h, r1, r2):
    res = con.execute(
        "MATCH (a:Entity {id:$h})-[:Rel {label:$r1}]->(x)-[:Rel {label:$r2}]->(t) "
        "RETURN DISTINCT t.id",
        parameters={"h": safe_id(h), "r1": safe_id(r1), "r2": safe_id(r2)})
    return {row[0] for row in res}


def exec_query(con, q):
    fam, p = q
    if fam == "lookup":   return cypher_lookup(con, p["h"], p["r"])
    if fam == "neighbor": return cypher_neighbor(con, p["h"])
    if fam == "join":     return cypher_join(con, p["h1"], p["r1"], p["h2"], p["r2"])
    if fam == "twohop":   return cypher_twohop(con, p["h"], p["r1"], p["r2"])
    return set()


def f1(pred, gold):
    if not pred and not gold: return 1.0
    if not pred or not gold:  return 0.0
    tp = len(pred & gold)
    p = tp / len(pred); r = tp / len(gold)
    return 2 * p * r / (p + r) if (p + r) else 0.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--max-pairs", type=int, default=80,
                    help="number of pairs to ingest into Kuzu (keeps wall time bounded)")
    ap.add_argument("--harm-th", type=float, default=0.05)
    ap.add_argument("--tau-g", type=float, default=0.30)
    ap.add_argument("--tau-q", type=float, default=0.10)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    con = sqlite3.connect(args.db)
    edges, gold, runs = rq.load_data(con)
    random.seed(args.seed)
    random.shuffle(runs)

    pair_records = []
    n_done = 0
    for run_id, base_ev, cf_ev, doc, fam, iv in runs:
        if n_done >= args.max_pairs: break
        if not cf_ev or base_ev not in edges or cf_ev not in edges: continue
        qs = rq.build_queries(gold.get(doc, set()))
        if not qs: continue
        base_g, cf_g = edges[base_ev], edges[cf_ev]

        # Ingest both graphs into Kuzu and execute each query via Cypher
        cb, db_b, t_b = kuzu_load(base_g)
        cc, db_c, t_c = kuzu_load(cf_g)
        try:
            per_q = []
            for q in qs:
                ab = exec_query(cb, q); ac = exec_query(cc, q)
                gq = q[1]["gold"]
                f1b = f1(ab, gq); f1c = f1(ac, gq)
                # Gold-free answer-set drift = 1 - Jaccard(ab, ac); used as deployable blocking signal.
                if not ab and not ac:
                    ans_jac = 0.0
                else:
                    ans_jac = 1.0 - (len(ab & ac) / len(ab | ac)) if (ab | ac) else 0.0
                per_q.append({
                    "family": q[0],
                    "f1_base": round(f1b, 4),
                    "f1_cf":   round(f1c, 4),
                    "delta_f1": round(abs(f1b - f1c), 4),
                    "delta_f1_signed": round(f1b - f1c, 4),  # positive = regression
                    "answer_drift": round(ans_jac, 4),       # gold-free, deployable
                })
        finally:
            kuzu_close(cb, db_b, t_b)
            kuzu_close(cc, db_c, t_c)

        mean_df1 = sum(x["delta_f1"] for x in per_q) / len(per_q)
        max_df1  = max(x["delta_f1"] for x in per_q)
        mean_df1_signed = sum(x["delta_f1_signed"] for x in per_q) / len(per_q)
        max_answer_drift = max(x["answer_drift"] for x in per_q)
        mean_answer_drift = sum(x["answer_drift"] for x in per_q) / len(per_q)
        be = {(s, o) for s, _, o in base_g}
        ce = {(s, o) for s, _, o in cf_g}
        graph_drift = 1.0 - rq.jaccard(be, ce)
        flag_graph = graph_drift > args.tau_g
        # Deployable query-side flag uses answer-set Jaccard, NOT F1-vs-gold.
        flag_query = max_answer_drift > args.tau_q
        contract_flag = flag_graph or flag_query
        # Directional harm: a regression in mean per-query F1 (cf is worse than base).
        harmful = mean_df1_signed > args.harm_th

        pair_records.append({
            "run_id": run_id, "doc": doc, "family": fam,
            "graph_drift": round(graph_drift, 4),
            "mean_df1": round(mean_df1, 4),
            "max_df1":  round(max_df1, 4),
            "mean_df1_signed": round(mean_df1_signed, 4),
            "max_answer_drift":  round(max_answer_drift, 4),
            "mean_answer_drift": round(mean_answer_drift, 4),
            "harmful":  harmful,
            "contract_flag": contract_flag,
            "per_query": per_q,
        })
        n_done += 1

    n = len(pair_records)
    harm = sum(1 for p in pair_records if p["harmful"])
    flag = sum(1 for p in pair_records if p["contract_flag"])
    tp = sum(1 for p in pair_records if p["contract_flag"] and p["harmful"])
    publish_all_regressions = harm
    guarded_published   = sum(1 for p in pair_records if not p["contract_flag"])
    guarded_regressions = sum(1 for p in pair_records if not p["contract_flag"] and p["harmful"])

    out = {
        "n_pairs": n,
        "n_queries_per_pair": "varies (lookup/neighbor/join/twohop)",
        "harm_threshold_delta_f1": args.harm_th,
        "tau_graph": args.tau_g, "tau_query": args.tau_q,
        "publish_all": {
            "published":     n,
            "regressions":   publish_all_regressions,
            "regression_rate": round(publish_all_regressions / n, 4) if n else 0.0,
        },
        "contract_guard": {
            "blocked":       flag,
            "published":     guarded_published,
            "regressions":   guarded_regressions,
            "regression_rate": round(guarded_regressions / guarded_published, 4) if guarded_published else 0.0,
            "harmful_caught": tp,
            "catch_rate":     round(tp / harm, 4) if harm else 0.0,
        },
        "pair_records": pair_records,
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    json.dump(out, open(args.out, "w"), indent=2)
    print(json.dumps({k: v for k, v in out.items() if k != "pair_records"}, indent=2))


if __name__ == "__main__":
    main()
