"""Gold-grounded KG-QA workload shared by the e2e scripts.

Builds four query families (lookup, neighbor, join, twohop) from gold_edges,
executes them over an extracted edge set, and scores answer sets. Used by
scripts/run_e2e_qa.py, scripts/run_e2e_kuzu_case_study.py and
scripts/run_graph_vs_query_ablation.py.
"""

from __future__ import annotations

import math
from collections import defaultdict
from itertools import combinations

from graphguard.interventions.schema import COARSE_GROUPS, RELATION_RENAMES


_INVERSE_RELATION_RENAMES = {
    renamed: base for base, renamed in RELATION_RENAMES.items()
}


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


def graph_jaccard(base_edges, cf_edges):
    """Canonicalized Jaccard over typed ``(subject, relation, object)`` edges.

    Entity identifiers are already canonical in the QA workload. Declared
    presentation-only relation renames are projected back to base relation
    identifiers, and declared coarse buckets can match one member relation on
    the same entity pair. This mirrors the contract metric while retaining the
    compact tuple representation used by the Kuzu/query analyses.
    """
    def canonical(edge):
        subject, relation, obj = edge
        return (
            subject,
            _INVERSE_RELATION_RENAMES.get(relation, relation),
            obj,
        )

    base = {canonical(edge) for edge in base_edges}
    cf = {canonical(edge) for edge in cf_edges}
    exact = base & cf
    base_left = base - exact
    cf_left = cf - exact
    bucket_matches = 0
    for subject, relation, obj in list(cf_left):
        members = COARSE_GROUPS.get(relation)
        if not members:
            continue
        for member in members:
            candidate = (subject, member, obj)
            if candidate in base_left:
                base_left.remove(candidate)
                cf_left.remove((subject, relation, obj))
                bucket_matches += 1
                break
    matched = len(exact) + bucket_matches
    union = matched + len(base_left) + len(cf_left)
    return matched / union if union else 1.0


def entity_pair_jaccard(base_edges, cf_edges):
    """Jaccard over directed entity pairs, deliberately ignoring labels."""
    base = {(subject, obj) for subject, _, obj in base_edges}
    cf = {(subject, obj) for subject, _, obj in cf_edges}
    return jaccard(base, cf)


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
    for eid, doc, s, r, o in cur.execute(
        "SELECT event_id, document_id, subject_entity_id, relation, object_entity_id "
        "FROM extracted_edges "
        "WHERE subject_entity_id IS NOT NULL AND object_entity_id IS NOT NULL "
        "ORDER BY rowid"):
        edges[eid].add((s, r, o))
    gold = defaultdict(set)  # doc -> set of (h,r,t)
    for doc, h, r, t in cur.execute(
        "SELECT document_id, head_entity_id, relation_base, tail_entity_id "
        "FROM gold_edges ORDER BY rowid"):
        gold[doc].add((h, r, t))

    runs = []  # (run_id, base_event, cf_event, doc, cause_family, intervention_id)
    cur2 = con.cursor()
    for run_id, base_event, cf_event, iv_id, doc in cur.execute(
        "SELECT run_id, base_event_id, cf_event_id, intervention_id, document_id "
        "FROM counterfactual_runs WHERE status='ok' ORDER BY rowid"):
        # A matched edge is an authoritative witness for the paired event and
        # repairs legacy rows whose configuration/time backfill was ambiguous.
        # Runs with no matched edge still retain their explicit cf_event_id,
        # including valid empty or all-new counterfactual graphs.
        row = cur2.execute(
            "SELECT matched_edge_id FROM edge_outcomes "
            "WHERE run_id=? AND matched_edge_id IS NOT NULL "
            "AND matched_edge_id<>'' ORDER BY rowid LIMIT 1",
            (run_id,)).fetchone()
        if row and row[0]:
            cf_event = row[0].rsplit("::", 1)[0]
        # cause_family lookup
        fam = cur2.execute(
            "SELECT cause_family FROM intervention_candidates WHERE intervention_id=?",
            (iv_id,)).fetchone()
        family = fam[0] if fam else "unknown"
        # Preserve valid empty graph views as explicit empty sets. Membership
        # checks in downstream analyses must not silently drop them.
        if base_event:
            edges[base_event]
        if cf_event:
            edges[cf_event]
        runs.append((run_id, base_event, cf_event, doc, family, iv_id))
    return edges, gold, runs


def build_queries(
    gold_edges_for_doc,
    *,
    allowed_relations: set[str] | None = None,
):
    """Build the deterministic deployment Q1--Q4 workload.

    Query identity is defined by the parameters sent to the database, not by
    an individual gold witness.  Q3 and Q4 therefore merge duplicate
    parameter tuples before applying their six/eight-query caps, and their
    ``gold`` fields contain the complete answer set on the filtered gold
    graph.

    When ``allowed_relations`` is provided, only relations declared by the
    base extraction schema may instantiate the workload.  Execution over the
    paired materialized views still uses the fixed raw relation labels.
    """
    queries = []
    gold_edges_for_doc = {
        (h, r, t)
        for h, r, t in gold_edges_for_doc
        if allowed_relations is None or r in allowed_relations
    }
    by_h_r = defaultdict(set)
    by_h = defaultdict(set)
    # The source is a set. Sort every traversal that can affect query
    # selection so results do not depend on Python's randomized hash seed.
    ordered_gold = sorted(gold_edges_for_doc)
    for h, r, t in ordered_gold:
        by_h_r[(h, r)].add(t)
        by_h[h].add((r, t))

    # lookup: (h, r, ?)
    for h, r in sorted(by_h_r):
        ts = by_h_r[(h, r)]
        queries.append(("lookup", {"h": h, "r": r, "gold": ts}))

    # neighbor: (h, ?, ?) -> set of (r,t)
    for h in sorted(by_h):
        neigh = by_h[h]
        if len(neigh) >= 2:
            queries.append(("neighbor", {"h": h, "gold": neigh}))

    # Shared-tail join: x s.t. (h1,r1,x) and (h2,r2,x) in G.
    # Multiple tail witnesses may instantiate the same database query.  Merge
    # those parameter tuples before the cap so the cap counts unique queries.
    by_t = defaultdict(list)
    for h, r, t in ordered_gold:
        by_t[t].append((h, r))
    join_parameters = set()
    for tail in sorted(by_t):
        branches = sorted(set(by_t[tail]))
        if len(branches) < 2:
            continue
        for first, second in combinations(branches, 2):
            join_parameters.add((*first, *second))
    for h1, r1, h2, r2 in sorted(join_parameters)[:6]:
        query = (
            "join",
            {"h1": h1, "r1": r1, "h2": h2, "r2": r2},
        )
        query[1]["gold"] = execute(gold_edges_for_doc, query)
        queries.append(query)

    # Typed two-hop: (h, r1, x)(x, r2, t).  A query is identified
    # by (h,r1,r2), regardless of how many paths or tails witness it.
    twohop_parameters = set()
    for h, r1, x in ordered_gold:
        for r2, t in sorted(by_h.get(x, set())):
            if t != h:
                twohop_parameters.add((h, r1, r2))
    for h, r1, r2 in sorted(twohop_parameters)[:8]:
        query = ("twohop", {"h": h, "r1": r1, "r2": r2})
        query[1]["gold"] = execute(gold_edges_for_doc, query)
        queries.append(query)

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
