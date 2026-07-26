#!/usr/bin/env python3
"""Extended query-level drift analysis (PVLDB revision, R2 / Rev6-W2).

Adds three query templates beyond the lookup/neighbor/join/two-hop workload:

  Q_path  — shortest-path query: for (h, t) pairs at directed distance 2-3 in
            the base view, the answer is the set of intermediate nodes lying
            on any shortest h->t path.
  Q_deg   — aggregation query: the set of top-3 entities by out-degree.
  Q_rag   — GraphRAG-style retrieval: the edge set of the 2-hop ego subgraph
            around the top-degree seed entity (the triples a graph-RAG system
            would fetch as context).

Following the paper's convention, query parameters are instantiated from the
base view of each pair and reused on the counterfactual view. For every ok
counterfactual pair we report per-template answer-set drift, amplification
Amp = QDrift / (GraphDrift + 0.05) (the implementation constant used by the
existing amplification evaluation), and violation rates on presentation-class
pairs at the registered catalogue threshold (drift > 0.30), plus the legacy
0.50-drift sensitivity point retained for comparison.

Writes reports/cross_run/extqueries_<run>.json.
"""
from __future__ import annotations

import argparse
import json
import random
import sqlite3
import statistics
import sys
from collections import defaultdict, deque
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from graphguard.contracts import metrics as M  # noqa: E402

MAIN_RUNS = [
    "docred__deepseek-v4-flash__300d",
    "redocred__deepseek-v4-flash__300d",
    "scierc__deepseek-v4-flash__100d",
    "cdr__deepseek-v4-flash__300d",
    "docred__glm-5__100d",
    "docred__kimi-k2__100d",
    "docred__qwen3-32b__100d",
]

OUT_DIR = ROOT / "reports" / "cross_run"
AMP_EPS = 0.05          # matches graphguard.contracts.metrics.EPS
TAU_LEGACY = 0.50       # legacy sensitivity point (not the registered contract)
TAU_TABLE = 0.30        # violation when answer drift > 0.30 (catalogue table)
N_PATH_QUERIES = 6


def jac(a: set, b: set) -> float:
    if not a and not b:
        return 1.0
    u = len(a | b)
    return len(a & b) / u if u else 1.0


# ------------------------------------------------------------------ queries

def graph_index(triples):
    out = defaultdict(set)
    for s, r, o in triples:
        out[s].add(o)
    return out


def bfs_dist(adj, src):
    d = {src: 0}
    q = deque([src])
    while q:
        u = q.popleft()
        for v in adj.get(u, ()):
            if v not in d:
                d[v] = d[u] + 1
                q.append(v)
    return d


def path_queries(base_triples):
    """Pick up to N_PATH_QUERIES (h, t) pairs at distance 2-3 in the base view."""
    adj = graph_index(base_triples)
    cands = []
    for h in sorted(adj):
        dist = bfs_dist(adj, h)
        for t, d in dist.items():
            if 2 <= d <= 3:
                cands.append((h, t, d))
    cands.sort()
    return cands[:N_PATH_QUERIES]


def path_answer(triples, h, t):
    """Nodes on any shortest directed h->t path (excluding endpoints)."""
    adj = graph_index(triples)
    radj = defaultdict(set)
    for s, r, o in triples:
        radj[o].add(s)
    dh = bfs_dist(adj, h)
    if t not in dh:
        return set()
    dt = bfs_dist(radj, t)
    d = dh[t]
    return {v for v in dh
            if v not in (h, t) and v in dt and dh[v] + dt[v] == d}


def top_degree_answer(triples, k=3):
    deg = defaultdict(int)
    for s, r, o in triples:
        deg[s] += 1
    top = sorted(deg.items(), key=lambda kv: (-kv[1], kv[0]))[:k]
    return {n for n, _ in top}


def rag_answer(triples, seed):
    """Edge set of the 2-hop ego subgraph around seed (undirected expansion)."""
    nbr = defaultdict(set)
    for s, r, o in triples:
        nbr[s].add(o)
        nbr[o].add(s)
    frontier = {seed}
    nodes = {seed}
    for _ in range(2):
        frontier = {v for u in frontier for v in nbr.get(u, ())} - nodes
        nodes |= frontier
    return {(s, r, o) for s, r, o in triples if s in nodes and o in nodes}


# ------------------------------------------------------------------- runner

def analyze_run(run: str) -> dict | None:
    db = ROOT / "data" / "processed" / "runs" / run / f"{run}.db"
    if not db.exists():
        print(f"[skip] {run}: no db")
        return None
    con = sqlite3.connect(db)
    cur = con.cursor()

    raw_edges = defaultdict(list)
    for eid, sid, sn, r, oid, on in cur.execute(
        "SELECT event_id, subject_entity_id, subject_name, relation, "
        "object_entity_id, object_name FROM extracted_edges"):
        raw_edges[eid].append({
            "subject_entity_id": sid, "subject_name": sn, "relation": r,
            "object_entity_id": oid, "object_name": on,
        })
    ev_schema = dict(cur.execute("SELECT event_id, schema_id FROM extraction_events"))
    schemas = {sid: {r["id"] for r in json.loads(rj)} for sid, rj in cur.execute(
        "SELECT schema_id, relation_types_json FROM schemas")}
    iv = {ivid: (fam, sc) for ivid, fam, sc in cur.execute(
        "SELECT intervention_id, cause_family, semantic_class FROM intervention_candidates")}

    per_q = defaultdict(
        lambda: {"doc": [], "qd": [], "gd": [], "amp": [], "pres_qd": []}
    )
    n_pairs = 0
    for run_id, base_ev, cf_ev, ivid, doc in cur.execute(
        "SELECT run_id, base_event_id, cf_event_id, intervention_id, document_id "
        "FROM counterfactual_runs WHERE status='ok' AND cf_event_id IS NOT NULL AND cf_event_id<>''"):
        if base_ev not in raw_edges and cf_ev not in raw_edges:
            continue
        fam, sem_class = iv.get(ivid, ("unknown", "unknown"))
        base_rel_ids = schemas.get(ev_schema.get(base_ev)) or None
        bt, ct = M.paired_triples(
            raw_edges.get(base_ev, []), raw_edges.get(cf_ev, []),
            base_relation_ids=base_rel_ids,
        )
        bt, ct = set(bt), set(ct)
        if not bt:
            continue
        gd = 1.0 - M.edge_jaccard(raw_edges.get(base_ev, []), raw_edges.get(cf_ev, []),
                                  base_relation_ids=base_rel_ids)
        n_pairs += 1

        answers = {}
        # Q_path
        pqs = path_queries(bt)
        if pqs:
            ds = [1.0 - jac(path_answer(bt, h, t), path_answer(ct, h, t))
                  for h, t, _ in pqs]
            answers["Q_path"] = sum(ds) / len(ds)
        # Q_deg
        answers["Q_deg"] = 1.0 - jac(top_degree_answer(bt), top_degree_answer(ct))
        # Q_rag
        seeds = sorted(top_degree_answer(bt, k=1))
        seed = seeds[0] if seeds else None
        if seed is not None:
            answers["Q_rag"] = 1.0 - jac(rag_answer(bt, seed), rag_answer(ct, seed))

        for q, qd in answers.items():
            st = per_q[q]
            st["doc"].append(doc)
            st["qd"].append(qd)
            st["gd"].append(gd)
            st["amp"].append(qd / (gd + AMP_EPS))
            if sem_class == "presentation":
                st["pres_qd"].append(qd)

    rng = random.Random(0)

    def boot_ci(vals, docs_for_values, B=1000):
        if not vals:
            return None, None, None
        by_doc = defaultdict(list)
        for doc, value in zip(docs_for_values, vals):
            by_doc[doc].append(value)
        docs = sorted(by_doc)
        means = sorted(
            statistics.mean([
                value
                for sampled_doc in rng.choices(docs, k=len(docs))
                for value in by_doc[sampled_doc]
            ])
            for _ in range(B)
        )
        return statistics.mean(vals), means[int(B * 0.025)], means[int(B * 0.975)]

    summary = {}
    for q, st in sorted(per_q.items()):
        amp_mean, lo, hi = boot_ci(st["amp"], st["doc"])
        pres = st["pres_qd"]
        summary[q] = {
            "n": len(st["qd"]),
            "n_documents": len(set(st["doc"])),
            "query_drift_mean": statistics.mean(st["qd"]),
            "graph_drift_mean": statistics.mean(st["gd"]),
            "amp_mean": amp_mean, "amp_ci_lo": lo, "amp_ci_hi": hi,
            "n_presentation": len(pres),
            "viol_rate_jaccard_lt_0.50": (sum(1 for d in pres if d > TAU_LEGACY) / len(pres)) if pres else None,
            "viol_rate_drift_gt_0.30": (sum(1 for d in pres if d > TAU_TABLE) / len(pres)) if pres else None,
        }

    out = {
        "run": run,
        "n_pairs": n_pairs,
        "amp_eps": AMP_EPS,
        "confidence_intervals": "document-cluster bootstrap (B=1000)",
        "summary": summary,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / f"extqueries_{run}.json"
    out_path.write_text(json.dumps(out, indent=1))
    print(f"[done] {run}: {n_pairs} pairs -> {out_path}")
    for q, s in summary.items():
        print(f"  {q:<7} n={s['n']:<6} qd={s['query_drift_mean']:.3f} "
              f"amp={s['amp_mean']:.2f} [{s['amp_ci_lo']:.2f},{s['amp_ci_hi']:.2f}] "
              f"violJ<.5={s['viol_rate_jaccard_lt_0.50'] if s['viol_rate_jaccard_lt_0.50'] is None else round(s['viol_rate_jaccard_lt_0.50'],3)} "
              f"violD>.3={s['viol_rate_drift_gt_0.30'] if s['viol_rate_drift_gt_0.30'] is None else round(s['viol_rate_drift_gt_0.30'],3)}")
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
