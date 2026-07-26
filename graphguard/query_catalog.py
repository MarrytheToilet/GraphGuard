"""Canonical names and semantics for GraphGuard's query workloads.

The project contains three query workloads created for different analyses:

``deployment``
    Gold-instantiated Q1--Q4 queries executed by the Kuzu release gate.
``extended``
    Q5--Q7 queries used for topology analysis.
``diagnostic``
    Graph-wide D1--D5 queries used for amplification diagnostics.

This module is the canonical registry consumed by the diagnostic runner and
deployment artifact pipeline; executable query operators remain in
``diagnostic_queries.py`` and the deployment/Kuzu executors.
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
        name="typed-edge identity",
        parameters="none",
        answer="the complete typed edge set",
    ),
    QuerySpec(
        canonical_id="diagnostic.two_hop_endpoints",
        workload="diagnostic",
        name="graph-wide two-hop endpoints",
        parameters="none",
        answer="ordered endpoint pairs connected by an exact two-hop path",
    ),
    QuerySpec(
        canonical_id="diagnostic.fanout_join",
        workload="diagnostic",
        name="same-head fan-out join",
        parameters="none",
        answer=(
            "canonical unordered pairs of differently typed outgoing branches "
            "that share a head entity"
        ),
    ),
    QuerySpec(
        canonical_id="diagnostic.top_undirected_degree",
        workload="diagnostic",
        name="top undirected degree",
        parameters="k=5",
        answer=(
            "the top-k entities ranked by simple-undirected distinct-neighbor "
            "degree, with canonical entity keys breaking ties"
        ),
    ),
    QuerySpec(
        canonical_id="diagnostic.short_connectivity",
        workload="diagnostic",
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
