"""Deterministic implementations of graph-wide diagnostic queries.

Callers are responsible for supplying canonical ``(subject, relation, object)``
triples.  Paired extraction edges should first pass through
``graphguard.contracts.metrics.paired_triples`` so both views share the same
entity and relation representation.
"""

from __future__ import annotations

from collections import defaultdict, deque
from itertools import combinations
from typing import FrozenSet, Iterable, TypeVar

from graphguard.query_catalog import (
    DIAGNOSTIC_QUERIES,
    by_legacy_artifact_id,
)


Triple = tuple[str, str, str]
Branch = tuple[str, str]
FanoutAnswer = tuple[str, Branch, Branch]
Answer = TypeVar("Answer")


def edge_identity_answers(triples: Iterable[Triple]) -> FrozenSet[Triple]:
    """Return the complete typed-edge set."""
    return frozenset(triples)


def two_hop_endpoint_answers(
    triples: Iterable[Triple],
) -> FrozenSet[tuple[str, str]]:
    """Return ordered endpoints connected by a directed two-edge walk.

    Relation labels and intermediate entities are not part of the answer.
    A direct edge between the endpoints does not invalidate the two-hop answer,
    while a walk that returns to its source is excluded.
    """
    outgoing: dict[str, set[str]] = defaultdict(set)
    for source, _relation, target in set(triples):
        outgoing[source].add(target)

    answers = {
        (source, target)
        for source in outgoing
        for middle in outgoing[source]
        for target in outgoing.get(middle, ())
        if source != target
    }
    return frozenset(answers)


def fanout_join_answers(triples: Iterable[Triple]) -> FrozenSet[FanoutAnswer]:
    """Return canonical same-head fan-out branch pairs.

    Each answer contains two differently typed outgoing branches from the same
    head.  Duplicate triples are removed, and branches are sorted before
    pairing.  Consequently, swapping either the input row order or the two
    logical branches cannot change the answer set.
    """
    by_head: dict[str, set[Branch]] = defaultdict(set)
    for head, relation, tail in triples:
        by_head[head].add((relation, tail))

    answers: set[FanoutAnswer] = set()
    for head in sorted(by_head):
        branches = sorted(by_head[head])
        for branch_a, branch_b in combinations(branches, 2):
            if branch_a[0] != branch_b[0]:
                answers.add((head, branch_a, branch_b))
    return frozenset(answers)


def top_undirected_degree_answers(
    triples: Iterable[Triple],
    *,
    k: int = 5,
) -> FrozenSet[str]:
    """Return the top-k entities by simple-undirected neighbor count.

    Parallel typed edges contribute one neighbor, self-loops contribute no
    neighbor, and canonical entity keys break degree ties deterministically.
    """
    if k < 0:
        raise ValueError("k must be non-negative")

    neighbors: dict[str, set[str]] = defaultdict(set)
    for source, _relation, target in set(triples):
        neighbors[source]
        neighbors[target]
        if source != target:
            neighbors[source].add(target)
            neighbors[target].add(source)

    ranked = sorted(
        neighbors,
        key=lambda entity: (-len(neighbors[entity]), entity),
    )
    return frozenset(ranked[:k])


def short_connectivity_answers(
    triples: Iterable[Triple],
    *,
    max_hops: int = 2,
) -> FrozenSet[tuple[str, str]]:
    """Return unordered node pairs within ``max_hops`` undirected hops."""
    if max_hops < 1:
        return frozenset()

    neighbors: dict[str, set[str]] = defaultdict(set)
    for source, _relation, target in set(triples):
        neighbors[source]
        neighbors[target]
        if source != target:
            neighbors[source].add(target)
            neighbors[target].add(source)

    answers: set[tuple[str, str]] = set()
    for source in sorted(neighbors):
        distance = {source: 0}
        queue = deque([source])
        while queue:
            node = queue.popleft()
            if distance[node] == max_hops:
                continue
            for adjacent in sorted(neighbors[node]):
                if adjacent not in distance:
                    distance[adjacent] = distance[node] + 1
                    queue.append(adjacent)
        answers.update(
            (source, target)
            for target, hops in distance.items()
            if source < target and 1 <= hops <= max_hops
        )
    return frozenset(answers)


def _canonical_diagnostic_id(query_id: str) -> str:
    canonical_ids = {spec.canonical_id for spec in DIAGNOSTIC_QUERIES}
    if query_id in canonical_ids:
        return query_id
    return by_legacy_artifact_id(query_id).canonical_id


def execute_diagnostic(query_id: str, triples: Iterable[Triple]) -> FrozenSet:
    """Execute one diagnostic query by canonical ID or legacy artifact alias."""
    canonical_id = _canonical_diagnostic_id(query_id)
    if canonical_id == "diagnostic.edge_identity":
        return edge_identity_answers(triples)
    if canonical_id == "diagnostic.two_hop_endpoints":
        return two_hop_endpoint_answers(triples)
    if canonical_id == "diagnostic.fanout_join":
        return fanout_join_answers(triples)
    if canonical_id == "diagnostic.top_undirected_degree":
        return top_undirected_degree_answers(triples)
    if canonical_id == "diagnostic.short_connectivity":
        return short_connectivity_answers(triples)
    raise KeyError(query_id)


def answer_jaccard(
    left: Iterable[Answer],
    right: Iterable[Answer],
) -> float:
    """Jaccard similarity for two query-answer collections."""
    left_set, right_set = set(left), set(right)
    if not left_set and not right_set:
        return 1.0
    return len(left_set & right_set) / len(left_set | right_set)
