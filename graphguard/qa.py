"""Gold-grounded KG-QA workload shared by the e2e scripts.

Builds four query families (lookup, neighbor, join, twohop) from gold_edges,
executes them over an extracted edge set, and scores answer sets. Used by
scripts/run_e2e_qa.py, scripts/run_e2e_kuzu_case_study.py and
scripts/run_graph_vs_query_ablation.py.
"""

from __future__ import annotations

import math
from collections import defaultdict


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


def load_data(con):
    """Load per-event edge sets, gold edges, and ok counterfactual runs."""
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
