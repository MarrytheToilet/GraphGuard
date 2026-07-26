"""Canonical names and semantics for GraphGuard's query workloads.

The project contains three query workloads created for different analyses:

``deployment``
    Gold-instantiated Q1--Q4 queries executed by the Kuzu release gate.
``extended``
    Q5--Q7 queries added for the revision's topology analysis.
``diagnostic``
    Graph-wide queries used by the legacy E6/E8 amplification artifacts.

Legacy artifact identifiers are retained only as provenance aliases.  They are
not paper query identifiers because their semantics differ from Q1--Q7.  The
``answer`` field records the deterministic semantics to use in future runs;
``legacy_behavior`` records a known difference in a historical artifact rather
than preserving that behavior as the specification.

This module is metadata-only for now; introducing it does not change any query
execution path or reported result.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


Workload = Literal["deployment", "extended", "diagnostic"]


@dataclass(frozen=True)
class QuerySpec:
    """Stable description of one query template."""

    canonical_id: str
    workload: Workload
    name: str
    parameters: str
    answer: str
    paper_id: str | None = None
    legacy_artifact_id: str | None = None
    legacy_behavior: str | None = None


DEPLOYMENT_QUERIES = (
    QuerySpec(
        canonical_id="deployment.lookup",
        workload="deployment",
        paper_id="Q1",
        name="typed lookup",
        parameters="head entity x and relation type r",
        answer="tail entities y such that (x, r, y) is present",
    ),
    QuerySpec(
        canonical_id="deployment.neighbor",
        workload="deployment",
        paper_id="Q2",
        name="outgoing neighbors",
        parameters="entity x",
        answer="outgoing (relation, neighbor) pairs of x",
    ),
    QuerySpec(
        canonical_id="deployment.shared_tail_join",
        workload="deployment",
        paper_id="Q3",
        name="shared-tail join",
        parameters="two fixed (head, relation) branches",
        answer="tail entities satisfying both branches",
    ),
    QuerySpec(
        canonical_id="deployment.typed_two_hop",
        workload="deployment",
        paper_id="Q4",
        name="typed two-hop",
        parameters="head entity x and relation types r1 and r2",
        answer="entities reachable through an r1-then-r2 path",
    ),
)


EXTENDED_QUERIES = (
    QuerySpec(
        canonical_id="extended.shortest_path_intermediates",
        workload="extended",
        paper_id="Q5",
        name="shortest-path intermediates",
        parameters="base-view endpoints at directed distance 2--3",
        answer="intermediate entities on any shortest directed path",
    ),
    QuerySpec(
        canonical_id="extended.top_out_degree",
        workload="extended",
        paper_id="Q6",
        name="top out-degree",
        parameters="k=3",
        answer="the top-k entities ranked by directed out-degree",
    ),
    QuerySpec(
        canonical_id="extended.rag_ego_edges",
        workload="extended",
        paper_id="Q7",
        name="GraphRAG ego retrieval",
        parameters="the base view's top-out-degree entity as seed",
        answer="typed edges in the seed's undirected two-hop ego subgraph",
    ),
)


DIAGNOSTIC_QUERIES = (
    QuerySpec(
        canonical_id="diagnostic.edge_identity",
        workload="diagnostic",
        legacy_artifact_id="Q1_single_edge",
        name="typed-edge identity",
        parameters="none",
        answer="the complete typed edge set",
    ),
    QuerySpec(
        canonical_id="diagnostic.two_hop_endpoints",
        workload="diagnostic",
        legacy_artifact_id="Q2_two_hop",
        name="graph-wide two-hop endpoints",
        parameters="none",
        answer="ordered endpoint pairs connected by an exact two-hop path",
    ),
    QuerySpec(
        canonical_id="diagnostic.fanout_join",
        workload="diagnostic",
        legacy_artifact_id="Q3_join",
        name="same-head fan-out join",
        parameters="none",
        answer=(
            "canonical unordered pairs of differently typed outgoing branches "
            "that share a head entity"
        ),
        legacy_behavior=(
            "E6/E8 serialized each branch pair in extracted-edge traversal "
            "order; reversing the two branches therefore produced a different "
            "tuple even though the logical answer was unchanged"
        ),
    ),
    QuerySpec(
        canonical_id="diagnostic.top_undirected_degree",
        workload="diagnostic",
        legacy_artifact_id="Q4_top_degree",
        name="top undirected degree",
        parameters="k=5",
        answer=(
            "the top-k entities ranked by simple-undirected distinct-neighbor "
            "degree, with canonical entity keys breaking ties"
        ),
        legacy_behavior=(
            "E6 did not retain answer identities and its producer is missing, "
            "so its cutoff-tie rule cannot be recovered; observed results are "
            "more consistent with traversal-order than canonical-key ties"
        ),
    ),
    QuerySpec(
        canonical_id="diagnostic.short_connectivity",
        workload="diagnostic",
        legacy_artifact_id="Q5_short_paths",
        name="short-range connectivity",
        parameters="none",
        answer="unordered entity pairs connected within two undirected hops",
    ),
)


ALL_QUERIES = DEPLOYMENT_QUERIES + EXTENDED_QUERIES + DIAGNOSTIC_QUERIES


def by_paper_id(query_id: str) -> QuerySpec:
    """Return the unique Q1--Q7 specification."""
    matches = [spec for spec in ALL_QUERIES if spec.paper_id == query_id]
    if len(matches) != 1:
        raise KeyError(query_id)
    return matches[0]


def by_legacy_artifact_id(query_id: str) -> QuerySpec:
    """Resolve an E6/E8 artifact identifier without treating it as Q1--Q7."""
    matches = [
        spec for spec in DIAGNOSTIC_QUERIES
        if spec.legacy_artifact_id == query_id
    ]
    if len(matches) != 1:
        raise KeyError(query_id)
    return matches[0]
