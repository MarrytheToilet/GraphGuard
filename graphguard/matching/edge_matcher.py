"""Match base edges to counterfactual edges and categorize outcomes.

Outcome categories:
  EXACT_SAME    same subject, same relation, same object
  TYPE_FLIP     same subject, same object, different relation
  OBJECT_FLIP   same subject, same relation, different object
  SUBJECT_FLIP  different subject, same relation, same object
  DISAPPEARED   no sufficiently similar edge in the cf set
  AMBIGUOUS     more than one cf edge is a plausible match
"""
from __future__ import annotations

import sqlite3
import uuid
from dataclasses import dataclass
from typing import Iterable, Optional

from ..matching.entity_matcher import same_entity
from ..matching.relation_normalizer import project_to_base


@dataclass
class EdgeOutcome:
    outcome_id: str
    run_id: str
    original_edge_id: str
    outcome_type: str
    matched_edge_id: Optional[str]
    relation_after: Optional[str]
    confidence_after: Optional[float]
    match_score: float


OUTCOMES = ("EXACT_SAME", "TYPE_FLIP", "OBJECT_FLIP", "SUBJECT_FLIP", "DISAPPEARED", "AMBIGUOUS")


def _row_relation(row, base_relation_ids: set[str]) -> str:
    rel = row["relation"]
    proj = project_to_base(rel, base_relation_ids=base_relation_ids)
    return proj or rel  # if relation is from a coarse schema we keep as-is and treat as FLIP


def match_edges(base_edges: Iterable[sqlite3.Row],
                cf_edges: list[sqlite3.Row],
                *,
                run_id: str,
                base_relation_ids: set[str]) -> list[EdgeOutcome]:
    out: list[EdgeOutcome] = []
    used_cf: set[str] = set()

    for be in base_edges:
        candidates: list[tuple[str, sqlite3.Row, float]] = []
        for ce in cf_edges:
            if ce["edge_id"] in used_cf:
                continue
            subj_eq = same_entity(be["subject_entity_id"], be["subject_name"],
                                  ce["subject_entity_id"], ce["subject_name"])
            obj_eq = same_entity(be["object_entity_id"], be["object_name"],
                                 ce["object_entity_id"], ce["object_name"])
            be_rel = be["relation"]
            ce_rel = _row_relation(ce, base_relation_ids)
            rel_eq = (be_rel == ce_rel)

            if subj_eq and obj_eq and rel_eq:
                cat, score = "EXACT_SAME", 1.0
            elif subj_eq and obj_eq:
                cat, score = "TYPE_FLIP", 0.85
            elif subj_eq and rel_eq:
                cat, score = "OBJECT_FLIP", 0.7
            elif obj_eq and rel_eq:
                cat, score = "SUBJECT_FLIP", 0.7
            else:
                continue
            candidates.append((cat, ce, score))

        if not candidates:
            out.append(EdgeOutcome(
                outcome_id=f"oc-{uuid.uuid4().hex[:10]}", run_id=run_id,
                original_edge_id=be["edge_id"], outcome_type="DISAPPEARED",
                matched_edge_id=None, relation_after=None,
                confidence_after=None, match_score=0.0,
            ))
            continue

        # Prefer EXACT_SAME, then any non-DISAPPEARED with highest score.
        priority = {"EXACT_SAME": 0, "TYPE_FLIP": 1, "OBJECT_FLIP": 1, "SUBJECT_FLIP": 1}
        candidates.sort(key=lambda x: (priority.get(x[0], 9), -x[2]))
        best_cat, best_ce, best_score = candidates[0]
        ambiguous = sum(1 for c in candidates if c[0] == best_cat) > 1 and best_cat != "EXACT_SAME"
        used_cf.add(best_ce["edge_id"])
        out.append(EdgeOutcome(
            outcome_id=f"oc-{uuid.uuid4().hex[:10]}", run_id=run_id,
            original_edge_id=be["edge_id"],
            outcome_type="AMBIGUOUS" if ambiguous else best_cat,
            matched_edge_id=best_ce["edge_id"],
            relation_after=best_ce["relation"],
            confidence_after=best_ce["confidence"],
            match_score=best_score,
        ))
    return out


def persist_outcomes(conn: sqlite3.Connection, outcomes: list[EdgeOutcome]) -> None:
    conn.executemany(
        "INSERT OR REPLACE INTO edge_outcomes("
        "outcome_id, run_id, original_edge_id, outcome_type, matched_edge_id, "
        "relation_after, confidence_after, match_score) VALUES (?,?,?,?,?,?,?,?)",
        [(o.outcome_id, o.run_id, o.original_edge_id, o.outcome_type,
          o.matched_edge_id, o.relation_after, o.confidence_after, o.match_score)
         for o in outcomes],
    )
    conn.commit()
