"""Reliability query interface (README §9).

Implements the five query primitives as Python functions over the SQLite store.

    why_edge(edge_id, top_k)            -> list[Cause]   (existence responsibility)
    why_type(edge_id, top_k)            -> list[Cause]   (relation-type responsibility)
    find_fragile_edges(threshold)       -> list[Edge]
    find_schema_sensitive_edges(thresh) -> list[Edge]
    rank_edges_for_audit(k)             -> list[Edge]    (ordered by risk_score desc)

A `Cause` summarises one *intervention variable* with its measured effect
on the target edge (existence or type). Effect is in [0, 1].
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass, asdict
from typing import List, Optional


EXIST_CHANGE = {"DISAPPEARED", "AMBIGUOUS"}
TYPE_CHANGE = {"TYPE_FLIP"}


@dataclass
class Cause:
    variable_type: str           # sentence | prompt_clause | schema
    variable_id: str             # target_id of the intervention
    operator: str
    intervention_id: str
    n_runs: int
    effect: float                # in [0, 1]
    interpretation: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class EdgeView:
    edge_id: str
    document_id: str
    subject_name: str
    relation: str
    object_name: str
    confidence: Optional[float]
    risk_score: Optional[float]
    stability_score: Optional[float]
    text_responsibility: Optional[float]
    prompt_sensitivity: Optional[float]
    schema_sensitivity: Optional[float]
    stochastic_variance: Optional[float]

    def to_dict(self) -> dict:
        return asdict(self)


# ---------- helpers ----------

def _causes_for_edge(conn: sqlite3.Connection, edge_id: str,
                     change_set: set[str], top_k: int) -> List[Cause]:
    rows = list(conn.execute("""
        SELECT ic.intervention_id, ic.target_type, ic.target_id, ic.operator, ic.description,
               eo.outcome_type
        FROM edge_outcomes eo
        JOIN counterfactual_runs cfr ON cfr.run_id = eo.run_id
        JOIN intervention_candidates ic ON ic.intervention_id = cfr.intervention_id
        WHERE eo.original_edge_id = ?
    """, (edge_id,)))
    by_iv: dict[str, dict] = {}
    for r in rows:
        d = by_iv.setdefault(r["intervention_id"], {
            "intervention_id": r["intervention_id"],
            "target_type": r["target_type"],
            "target_id": r["target_id"],
            "operator": r["operator"],
            "description": r["description"],
            "n": 0, "k": 0,
        })
        d["n"] += 1
        if r["outcome_type"] in change_set:
            d["k"] += 1
    causes: List[Cause] = []
    for d in by_iv.values():
        if d["n"] == 0:
            continue
        eff = d["k"] / d["n"]
        if eff <= 0:
            continue
        if change_set is EXIST_CHANGE:
            interp = (f"{d['operator']} on {d['target_type']} {d['target_id']!r}"
                      f" → edge disappears in {d['k']}/{d['n']} runs")
        else:
            interp = (f"{d['operator']} on {d['target_type']} {d['target_id']!r}"
                      f" → relation type flips in {d['k']}/{d['n']} runs")
        causes.append(Cause(
            variable_type=d["target_type"], variable_id=d["target_id"],
            operator=d["operator"], intervention_id=d["intervention_id"],
            n_runs=d["n"], effect=eff, interpretation=interp,
        ))
    causes.sort(key=lambda c: (-c.effect, c.variable_type, c.variable_id))
    return causes[:top_k]


def _edge_view_row(r: sqlite3.Row) -> EdgeView:
    return EdgeView(
        edge_id=r["edge_id"], document_id=r["document_id"],
        subject_name=r["subject_name"], relation=r["relation"], object_name=r["object_name"],
        confidence=r["confidence"], risk_score=r["risk_score"],
        stability_score=r["stability_score"], text_responsibility=r["text_responsibility"],
        prompt_sensitivity=r["prompt_sensitivity"], schema_sensitivity=r["schema_sensitivity"],
        stochastic_variance=r["stochastic_variance"],
    )


_EDGE_JOIN = """
SELECT e.edge_id, e.document_id, e.subject_name, e.relation, e.object_name, e.confidence,
       s.risk_score, s.stability_score, s.text_responsibility,
       s.prompt_sensitivity, s.schema_sensitivity, s.stochastic_variance
FROM extracted_edges e
LEFT JOIN edge_reliability_scores s ON s.edge_id = e.edge_id
"""


# ---------- public API ----------

def why_edge(conn: sqlite3.Connection, edge_id: str, top_k: int = 10) -> List[Cause]:
    """Return top causes whose intervention makes the edge disappear."""
    return _causes_for_edge(conn, edge_id, EXIST_CHANGE, top_k)


def why_type(conn: sqlite3.Connection, edge_id: str, top_k: int = 10) -> List[Cause]:
    """Return top causes whose intervention flips the edge's relation type."""
    return _causes_for_edge(conn, edge_id, TYPE_CHANGE, top_k)


def find_fragile_edges(conn: sqlite3.Connection,
                       document_id: Optional[str] = None,
                       threshold: float = 0.5,
                       limit: Optional[int] = None) -> List[EdgeView]:
    q = _EDGE_JOIN + " WHERE COALESCE(s.stability_score, 1.0) <= ? "
    params: list = [1.0 - threshold]  # threshold on (1-stability) i.e. "fragility"
    if document_id is not None:
        q += " AND e.document_id = ? "
        params.append(document_id)
    q += " ORDER BY s.stability_score ASC "
    if limit:
        q += " LIMIT ? "
        params.append(limit)
    return [_edge_view_row(r) for r in conn.execute(q, params)]


def find_schema_sensitive_edges(conn: sqlite3.Connection,
                                threshold: float = 0.5,
                                limit: Optional[int] = None) -> List[EdgeView]:
    q = _EDGE_JOIN + " WHERE COALESCE(s.schema_sensitivity, 0) >= ? "
    params: list = [threshold]
    q += " ORDER BY s.schema_sensitivity DESC "
    if limit:
        q += " LIMIT ? "
        params.append(limit)
    return [_edge_view_row(r) for r in conn.execute(q, params)]


def find_prompt_induced_edges(conn: sqlite3.Connection,
                              threshold: float = 0.5,
                              limit: Optional[int] = None) -> List[EdgeView]:
    q = _EDGE_JOIN + " WHERE COALESCE(s.prompt_sensitivity, 0) >= ? "
    params: list = [threshold]
    q += " ORDER BY s.prompt_sensitivity DESC "
    if limit:
        q += " LIMIT ? "
        params.append(limit)
    return [_edge_view_row(r) for r in conn.execute(q, params)]


def rank_edges_for_audit(conn: sqlite3.Connection, k: int = 20) -> List[EdgeView]:
    q = _EDGE_JOIN + " ORDER BY s.risk_score DESC NULLS LAST LIMIT ? "
    # SQLite < 3.30 doesn't support NULLS LAST; fall back gracefully.
    try:
        return [_edge_view_row(r) for r in conn.execute(q, (k,))]
    except sqlite3.OperationalError:
        q = _EDGE_JOIN + " ORDER BY (s.risk_score IS NULL), s.risk_score DESC LIMIT ? "
        return [_edge_view_row(r) for r in conn.execute(q, (k,))]
