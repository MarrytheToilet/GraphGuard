"""Metrics used by drift contracts.

All metrics return a float; semantics depend on the contract direction.
When ``base_relation_ids`` is provided, cf-side relation tokens are projected
back to the base schema's relation ids via :func:`project_to_base`. This lets
a rename perturbation (e.g., ``P19`` -> ``place_of_birth``) be scored on
semantic identity rather than on the renamed surface token.
"""
from __future__ import annotations

from typing import Iterable, Optional, Sequence


# Reuse triple extraction from existing drift module
from graphguard.metrics.graph_drift import _to_triples as _raw_to_triples
from graphguard.matching.relation_normalizer import project_to_base
from graphguard.interventions.schema import COARSE_GROUPS
from graphguard.interventions.text import _ALIAS_TABLE


# Canonical entity-name table: both surface forms map to the same canonical key
# so audit-time entity matching is alias-aware (e.g., "United States" == "the U.S.").
_ENTITY_CANON: dict[str, str] = {}
for _canon, _alias in _ALIAS_TABLE.items():
    _key = _canon.lower().strip()
    _ENTITY_CANON[_key] = _key
    _ENTITY_CANON[_alias.lower().strip()] = _key


def _canon_entity(name: str) -> str:
    """Canonicalize an entity surface form via the alias table (lower-cased)."""
    k = (name or "").lower().strip()
    return _ENTITY_CANON.get(k, k)


def _to_triples(edges):
    """Wrapper that adds entity-alias canonicalization on top of the raw extractor."""
    return [(_canon_entity(s), r, _canon_entity(o)) for (s, r, o) in _raw_to_triples(edges)]


def _project(triples, base_relation_ids):
    if not base_relation_ids:
        return triples
    out = []
    for s, r, o in triples:
        proj = project_to_base(r, base_relation_ids=base_relation_ids)
        out.append((s, proj if proj else r, o))
    return out


def _bucket_aware_match(base_triples, cf_triples) -> tuple[int, int]:
    """Return (matched, union_size) where a cf triple whose relation is a coarse
    bucket name matches any base triple sharing (s, o) with a relation in
    COARSE_GROUPS[bucket]. Exact triples match first; remaining cf bucket triples
    are then matched greedily."""
    base = set(base_triples)
    cf = set(cf_triples)
    inter = base & cf
    base_left = base - inter
    cf_left = cf - inter
    matches_via_bucket = 0
    for s, r, o in list(cf_left):
        members = COARSE_GROUPS.get(r)
        if not members:
            continue
        for m in members:
            cand = (s, m, o)
            if cand in base_left:
                base_left.discard(cand)
                cf_left.discard((s, r, o))
                matches_via_bucket += 1
                break
    matched = len(inter) + matches_via_bucket
    union = matched + len(base_left) + len(cf_left)
    return matched, union


def edge_jaccard(base_edges: Iterable, cf_edges: Iterable,
                 *, base_relation_ids: Optional[set] = None) -> float:
    a = _project(_to_triples(base_edges), base_relation_ids)
    b = _project(_to_triples(cf_edges), base_relation_ids)
    matched, union = _bucket_aware_match(a, b)
    if union == 0:
        return 1.0
    return matched / union


def relation_distribution_l1(base_edges: Iterable, cf_edges: Iterable,
                             *, base_relation_ids: Optional[set] = None) -> float:
    """L1 distance between normalized relation distributions, in [0, 2].
    Returned as 1 - L1/2 so that "1.0 = identical".
    """
    from collections import Counter
    ta = _project(_to_triples(base_edges), base_relation_ids)
    tb = _project(_to_triples(cf_edges), base_relation_ids)
    a = Counter(t[1] for t in ta)
    b = Counter(t[1] for t in tb)
    sa = max(1, sum(a.values()))
    sb = max(1, sum(b.values()))
    keys = set(a) | set(b)
    if not keys:
        return 1.0
    l1 = sum(abs(a.get(k, 0) / sa - b.get(k, 0) / sb) for k in keys)
    return 1.0 - l1 / 2.0


def type_flip_rate(base_edges: Iterable, cf_edges: Iterable,
                   *, base_relation_ids: Optional[set] = None) -> float:
    """Fraction of base (s,o) pairs whose relation changed in cf."""
    base_t = _project(_to_triples(base_edges), base_relation_ids)
    cf_t = _project(_to_triples(cf_edges), base_relation_ids)
    base_so = {(s, o): r for s, r, o in base_t}
    cf_so = {(s, o): r for s, r, o in cf_t}
    common = set(base_so) & set(cf_so)
    if not common:
        return 0.0
    flips = sum(1 for so in common if base_so[so] != cf_so[so])
    return flips / len(common)


def query_jaccard(base_ans: set, cf_ans: set) -> float:
    if not base_ans and not cf_ans:
        return 1.0
    return len(base_ans & cf_ans) / max(1, len(base_ans | cf_ans))


# ---- Amplification ---------------------------------------------------------

EPS = 0.05  # avoid division blow-up when graph drift ~ 0


def amplification(graph_drift: float, query_drift: float, eps: float = EPS) -> float:
    """Amp(Q) = QueryDrift / (GraphDrift + eps).

    Where Drift = 1 - Jaccard, both in [0,1].
    Amp > 1 means the query is more sensitive than the underlying graph.
    """
    return query_drift / (graph_drift + eps)
