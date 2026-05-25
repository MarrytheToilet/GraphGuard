"""Graph-level drift metrics between two extracted-graph snapshots.

Each "graph" here is a set of (subject_entity_id, relation, object_entity_id)
triples plus their per-doc scope. All metrics are pure functions of those
triples + (optionally) edge-level metadata. No DB/LLM access.

These are used by E1 (schema design study), E6 (query-stability), and E7
(schema redesign before/after).
"""
from __future__ import annotations

import math
import statistics as stats
from collections import Counter, defaultdict
from typing import Iterable, Optional, Sequence

import networkx as nx


Triple = tuple[str, str, str]   # (subject, relation, object)


def _get(row, key, default=None):
    try:
        if hasattr(row, "keys") and key in row.keys():
            v = row[key]
            return v if v is not None else default
        if isinstance(row, dict):
            return row.get(key, default)
    except Exception:
        pass
    try:
        return row[key]
    except Exception:
        return default


def _to_triples(edges: Iterable) -> list[Triple]:
    """Triples keyed on canonical surface names (lowercased+trimmed). We deliberately
    avoid event-scoped entity_ids because cf extractions create fresh entity rows.
    """
    out: list[Triple] = []
    for e in edges:
        s = _get(e, "subject_name") or _get(e, "subject_entity_id")
        o = _get(e, "object_name") or _get(e, "object_entity_id")
        r = _get(e, "relation")
        if not s or not o or not r:
            continue
        out.append((str(s).strip().lower(), str(r), str(o).strip().lower()))
    return out


def _to_pairs(edges: Iterable) -> set[tuple[str, str]]:
    return {(s, o) for (s, _r, o) in _to_triples(edges)}


def _jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 1.0
    return len(a & b) / max(1, len(a | b))


def edge_jaccard(edges_a: Iterable, edges_b: Iterable) -> float:
    """Jaccard over (s,r,o) triples."""
    return _jaccard(set(_to_triples(edges_a)), set(_to_triples(edges_b)))


def entity_pair_jaccard(edges_a: Iterable, edges_b: Iterable) -> float:
    """Jaccard over (s,o) pairs ignoring relation type."""
    return _jaccard(_to_pairs(edges_a), _to_pairs(edges_b))


def relation_distribution_kl(edges_a: Iterable, edges_b: Iterable,
                              eps: float = 1e-9) -> float:
    """KL(P_a || P_b) over relation labels. Smoothed with eps."""
    ca = Counter(r for _s, r, _o in _to_triples(edges_a))
    cb = Counter(r for _s, r, _o in _to_triples(edges_b))
    keys = set(ca) | set(cb)
    if not keys:
        return 0.0
    na, nb = sum(ca.values()) + eps * len(keys), sum(cb.values()) + eps * len(keys)
    kl = 0.0
    for k in keys:
        p = (ca.get(k, 0) + eps) / na
        q = (cb.get(k, 0) + eps) / nb
        kl += p * math.log(p / q)
    return kl


def relation_confusion_matrix(edges_base: Iterable, edges_cf: Iterable
                              ) -> dict[tuple[str, str], int]:
    """For (s,o) pairs present in both snapshots, count (rel_base -> rel_cf)."""
    base_by_pair: dict[tuple[str, str], list[str]] = defaultdict(list)
    cf_by_pair: dict[tuple[str, str], list[str]] = defaultdict(list)
    for s, r, o in _to_triples(edges_base):
        base_by_pair[(s, o)].append(r)
    for s, r, o in _to_triples(edges_cf):
        cf_by_pair[(s, o)].append(r)
    matrix: Counter[tuple[str, str]] = Counter()
    for pair, base_rs in base_by_pair.items():
        cf_rs = cf_by_pair.get(pair, [])
        for br in base_rs:
            if not cf_rs:
                matrix[(br, "<DROPPED>")] += 1
            else:
                for cr in cf_rs:
                    matrix[(br, cr)] += 1
    return dict(matrix)


def schema_pair_drift_distance(edges_a: Iterable, edges_b: Iterable) -> dict[str, float]:
    """Composite distance between two schema-induced snapshots.

    Components are normalised in [0,1]; the headline ``distance`` is their mean.
    """
    triples_a = set(_to_triples(edges_a))
    triples_b = set(_to_triples(edges_b))
    pairs_a = {(s, o) for (s, _r, o) in triples_a}
    pairs_b = {(s, o) for (s, _r, o) in triples_b}

    edge_d = 1.0 - _jaccard(triples_a, triples_b)
    pair_d = 1.0 - _jaccard(pairs_a, pairs_b)
    rel_d = 1.0 - _jaccard(
        {r for _s, r, _o in triples_a}, {r for _s, r, _o in triples_b}
    )
    rel_kl = relation_distribution_kl(edges_a, edges_b)
    return {
        "edge_distance": edge_d,
        "pair_distance": pair_d,
        "relation_set_distance": rel_d,
        "relation_kl": rel_kl,
        "distance": stats.mean([edge_d, pair_d, rel_d]),
    }


def degree_distribution_shift(edges_a: Iterable, edges_b: Iterable) -> float:
    """L1 distance between degree-distributions of the two snapshots."""
    def _deg(triples: list[Triple]) -> Counter:
        c: Counter = Counter()
        for s, _r, o in triples:
            c[s] += 1
            c[o] += 1
        return c
    da = Counter(_deg(_to_triples(edges_a)).values())
    db = Counter(_deg(_to_triples(edges_b)).values())
    keys = set(da) | set(db)
    if not keys:
        return 0.0
    na = max(1, sum(da.values()))
    nb = max(1, sum(db.values()))
    return sum(abs(da.get(k, 0) / na - db.get(k, 0) / nb) for k in keys) / 2.0


def _to_graph(edges: Iterable) -> nx.MultiDiGraph:
    g = nx.MultiDiGraph()
    for s, r, o in _to_triples(edges):
        g.add_edge(s, o, key=r, relation=r)
    return g


def connected_component_change(edges_a: Iterable, edges_b: Iterable) -> float:
    ga = _to_graph(edges_a).to_undirected()
    gb = _to_graph(edges_b).to_undirected()
    na = nx.number_connected_components(ga) if ga.number_of_nodes() else 0
    nb = nx.number_connected_components(gb) if gb.number_of_nodes() else 0
    return float(abs(na - nb))


def path_preservation_rate(edges_a: Iterable, edges_b: Iterable,
                           samples: int = 50, max_hops: int = 2) -> float:
    """Fraction of (u,v) endpoint pairs reachable in A within max_hops that are
    also reachable in B within max_hops."""
    ga = _to_graph(edges_a).to_undirected()
    gb = _to_graph(edges_b).to_undirected()
    nodes = list(ga.nodes())
    if len(nodes) < 2:
        return 1.0
    import random as _r
    rng = _r.Random(13)
    pairs = []
    while len(pairs) < samples and len(nodes) >= 2:
        u, v = rng.sample(nodes, 2)
        pairs.append((u, v))
    if not pairs:
        return 1.0
    preserved = 0
    total = 0
    for u, v in pairs:
        try:
            la = nx.shortest_path_length(ga, u, v)
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            continue
        if la > max_hops:
            continue
        total += 1
        try:
            lb = nx.shortest_path_length(gb, u, v)
            if lb <= max_hops:
                preserved += 1
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            pass
    return preserved / total if total else 1.0


def centrality_rank_correlation(edges_a: Iterable, edges_b: Iterable) -> float:
    """Spearman correlation between degree-centrality rankings of shared nodes.
    Returns 1.0 when the graphs are too small to rank meaningfully.
    """
    ga = _to_graph(edges_a).to_undirected()
    gb = _to_graph(edges_b).to_undirected()
    shared = list(set(ga.nodes()) & set(gb.nodes()))
    if len(shared) < 3:
        return 1.0
    da = nx.degree_centrality(ga)
    db = nx.degree_centrality(gb)
    xs = [da.get(n, 0.0) for n in shared]
    ys = [db.get(n, 0.0) for n in shared]
    return _spearman(xs, ys)


def _spearman(xs: Sequence[float], ys: Sequence[float]) -> float:
    def _rank(arr):
        idx = sorted(range(len(arr)), key=lambda i: arr[i])
        ranks = [0.0] * len(arr)
        i = 0
        while i < len(arr):
            j = i
            while j + 1 < len(arr) and arr[idx[j + 1]] == arr[idx[i]]:
                j += 1
            avg = (i + j) / 2 + 1
            for k in range(i, j + 1):
                ranks[idx[k]] = avg
            i = j + 1
        return ranks
    rx, ry = _rank(list(xs)), _rank(list(ys))
    n = len(xs)
    mx, my = sum(rx) / n, sum(ry) / n
    num = sum((rx[i] - mx) * (ry[i] - my) for i in range(n))
    dx = math.sqrt(sum((rx[i] - mx) ** 2 for i in range(n)))
    dy = math.sqrt(sum((ry[i] - my) ** 2 for i in range(n)))
    if dx == 0 or dy == 0:
        return 1.0
    return num / (dx * dy)


def all_drift_metrics(edges_a: Iterable, edges_b: Iterable) -> dict[str, float]:
    """One-stop bundle for E1/E6 reporting."""
    ea = list(edges_a)
    eb = list(edges_b)
    out = {
        "edge_jaccard": edge_jaccard(ea, eb),
        "entity_pair_jaccard": entity_pair_jaccard(ea, eb),
        "relation_kl": relation_distribution_kl(ea, eb),
        "degree_shift": degree_distribution_shift(ea, eb),
        "path_preservation": path_preservation_rate(ea, eb),
        "component_change": connected_component_change(ea, eb),
        "centrality_rank_corr": centrality_rank_correlation(ea, eb),
    }
    out["pair_distance"] = schema_pair_drift_distance(ea, eb)["distance"]
    return out
