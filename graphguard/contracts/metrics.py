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
    """Surface-keyed triples used when no paired identifier context is available."""
    return [(_canon_entity(s), r, _canon_entity(o)) for (s, r, o) in _raw_to_triples(edges)]


def _project(triples, base_relation_ids):
    if not base_relation_ids:
        return triples
    out = []
    for s, r, o in triples:
        proj = project_to_base(r, base_relation_ids=base_relation_ids)
        out.append((s, proj if proj else r, o))
    return out


def _get(row, key, default=None):
    try:
        if hasattr(row, "keys") and key in row.keys():
            value = row[key]
            return value if value is not None else default
        if isinstance(row, dict):
            return row.get(key, default)
    except Exception:
        pass
    return default


def _paired_entity_resolver(base_edges: list, cf_edges: list):
    """Build an identifier-first resolver shared by a paired graph comparison.

    Extracted edges retain benchmark entity identifiers when linking succeeds.
    For an unlinked mention, declared aliases and an unambiguous
    case-insensitive/containment fallback map the surface form to an identifier
    already present on either side. Ambiguous fallbacks remain surface keyed.
    """
    name_to_ids: dict[str, set[str]] = {}
    for edge in [*base_edges, *cf_edges]:
        for side in ("subject", "object"):
            entity_id = _get(edge, f"{side}_entity_id")
            name = _canon_entity(_get(edge, f"{side}_name", ""))
            if entity_id and name:
                name_to_ids.setdefault(name, set()).add(str(entity_id))

    def resolve(edge, side: str) -> str:
        entity_id = _get(edge, f"{side}_entity_id")
        if entity_id:
            return f"id:{entity_id}"
        name = _canon_entity(_get(edge, f"{side}_name", ""))
        direct = name_to_ids.get(name, set())
        if len(direct) == 1:
            return f"id:{next(iter(direct))}"
        candidates: set[str] = set()
        if name:
            for known_name, ids in name_to_ids.items():
                if name in known_name or known_name in name:
                    candidates.update(ids)
        if len(candidates) == 1:
            return f"id:{next(iter(candidates))}"
        return f"name:{name}"

    return resolve


def paired_triples(base_edges: Iterable, cf_edges: Iterable,
                   *, base_relation_ids: Optional[set] = None
                   ) -> tuple[list[tuple[str, str, str]], list[tuple[str, str, str]]]:
    """Return identifier-first, declared-perturbation-aware paired triples."""
    base_list, cf_list = list(base_edges), list(cf_edges)
    resolve = _paired_entity_resolver(base_list, cf_list)

    def convert(edges):
        triples = []
        for edge in edges:
            relation = _get(edge, "relation")
            if not relation:
                continue
            projected = (
                project_to_base(relation, base_relation_ids=base_relation_ids)
                if base_relation_ids else None
            )
            triples.append((
                resolve(edge, "subject"),
                projected if projected else relation,
                resolve(edge, "object"),
            ))
        return triples

    return convert(base_list), convert(cf_list)


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
    a, b = paired_triples(
        base_edges, cf_edges, base_relation_ids=base_relation_ids
    )
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
    base_t, cf_t = paired_triples(
        base_edges, cf_edges, base_relation_ids=base_relation_ids
    )
    base_so = {(s, o): r for s, r, o in base_t}
    cf_so = {(s, o): r for s, r, o in cf_t}
    common = set(base_so) & set(cf_so)
    if not common:
        return 0.0
    flips = sum(1 for so in common if base_so[so] != cf_so[so])
    return flips / len(common)


def gold_recall(edges: Iterable, gold_edges: Iterable,
                *, base_relation_ids: Optional[set] = None) -> float:
    """Recall against a benchmark's canonical entity identifiers.

    Extracted identifiers take precedence.  When an extracted mention is
    unlinked, an unambiguous alias/surface match to the gold entity names is
    used as the documented fallback.
    """
    edge_list, gold_list = list(edges), list(gold_edges)
    name_to_ids: dict[str, set[str]] = {}
    gold = set()
    for edge in gold_list:
        subject_id = _get(edge, "head_entity_id")
        object_id = _get(edge, "tail_entity_id")
        relation = _get(edge, "relation_base")
        if not subject_id or not object_id or not relation:
            continue
        gold.add((f"id:{subject_id}", relation, f"id:{object_id}"))
        for name_key, entity_id in (
            ("head_name", subject_id), ("tail_name", object_id)
        ):
            name = _canon_entity(_get(edge, name_key, ""))
            if name:
                name_to_ids.setdefault(name, set()).add(str(entity_id))

    if not gold:
        return 0.0

    def resolve(edge, side: str) -> str:
        entity_id = _get(edge, f"{side}_entity_id")
        if entity_id:
            return f"id:{entity_id}"
        name = _canon_entity(_get(edge, f"{side}_name", ""))
        candidates = set(name_to_ids.get(name, set()))
        if not candidates and name:
            for known_name, ids in name_to_ids.items():
                if name in known_name or known_name in name:
                    candidates.update(ids)
        if len(candidates) == 1:
            return f"id:{next(iter(candidates))}"
        return f"name:{name}"

    predicted = set()
    for edge in edge_list:
        relation = _get(edge, "relation")
        if not relation:
            continue
        projected = (
            project_to_base(relation, base_relation_ids=base_relation_ids)
            if base_relation_ids else None
        )
        predicted.add((
            resolve(edge, "subject"),
            projected if projected else relation,
            resolve(edge, "object"),
        ))
    return len(predicted & gold) / len(gold)


def recall_difference(base_edges: Iterable, cf_edges: Iterable,
                      *, gold_edges: Optional[Iterable] = None,
                      base_relation_ids: Optional[set] = None) -> float:
    """Absolute per-document gold-recall difference used by K5."""
    if gold_edges is None:
        raise ValueError("recall_difference requires gold_edges")
    gold_list = list(gold_edges)
    recall_base = gold_recall(
        base_edges, gold_list, base_relation_ids=base_relation_ids
    )
    recall_cf = gold_recall(
        cf_edges, gold_list, base_relation_ids=base_relation_ids
    )
    return abs(recall_base - recall_cf)


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
