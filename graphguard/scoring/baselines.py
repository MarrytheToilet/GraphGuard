"""Baseline detector signals for E2/E5.

Per README §15, the audit-prioritization claim must compare GraphGuard
risk against several cheap, deterministic baselines so that reviewers cannot
say "your reliability score isn't better than confidence/NLI". This module
computes and persists those baselines into ``edge_baseline_scores`` so that
E2 and E5 evaluators can score them uniformly alongside our risk score.

Signals are normalised so that **higher = more likely to be wrong** (so the
same ranking code in E2/E5 works without sign flips).

Cheap, no-LLM baselines populated here:

* ``confidence_inv``        1 - LLM self-confidence (extracted_edges.confidence)
* ``majority_vote_inv``     across cf prompt-clause runs, fraction in which
                            the edge does NOT survive intact (DISAPPEARED /
                            TYPE_FLIP / OBJECT_FLIP / SUBJECT_FLIP / AMBIGUOUS).
                            This is exactly "majority voting across prompts"
                            from README §15.
* ``source_prov_inv``       1 if no evidence sentence id was cited, else 0.
* ``subj_obj_cooccur_inv``  1 if subject *or* object surface form is absent
                            from the cited evidence sentences (proxy for
                            "AEVS-style character provenance").

The NLI baseline is populated by ``scripts/run_nli_baseline.py`` which writes
``signal='nli_inv'`` directly.
"""
from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timezone
from typing import Iterable

log = logging.getLogger(__name__)

CHANGE_OUTCOMES = {"DISAPPEARED", "TYPE_FLIP", "OBJECT_FLIP", "SUBJECT_FLIP", "AMBIGUOUS"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _persist(conn: sqlite3.Connection, edge_id: str, signal: str, score: float) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO edge_baseline_scores(edge_id, signal, score, computed_at) "
        "VALUES (?, ?, ?, ?)",
        (edge_id, signal, float(score), _now()),
    )


def _base_edges(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Edges that came from a base extraction event (not a counterfactual run).

    Matches the convention used by the E2 labeller: only base events are
    referenced as ``base_event_id`` in ``counterfactual_runs``. We additionally
    accept events whose document has no cf runs at all (e.g. stability subset).
    """
    return list(conn.execute("""
        SELECT e.edge_id, e.document_id, e.event_id, e.subject_name,
               e.object_name, e.relation, e.confidence,
               e.evidence_sentence_ids_json
        FROM extracted_edges e
        JOIN extraction_events ev ON ev.event_id = e.event_id
        WHERE ev.event_id IN (SELECT base_event_id FROM counterfactual_runs)
           OR ev.event_id NOT IN (SELECT run_id FROM counterfactual_runs)
    """))


def compute_confidence(conn: sqlite3.Connection) -> int:
    n = 0
    for e in _base_edges(conn):
        c = e["confidence"]
        if c is None:
            continue
        _persist(conn, e["edge_id"], "confidence_inv", 1.0 - float(c))
        n += 1
    conn.commit()
    return n


def compute_source_provenance(conn: sqlite3.Connection) -> int:
    """1 if no evidence sentence cited, else 0. Higher = more risky."""
    n = 0
    for e in _base_edges(conn):
        try:
            ids = json.loads(e["evidence_sentence_ids_json"]) if e["evidence_sentence_ids_json"] else []
        except Exception:
            ids = []
        score = 0.0 if ids else 1.0
        _persist(conn, e["edge_id"], "source_prov_inv", score)
        n += 1
    conn.commit()
    return n


def compute_subj_obj_cooccurrence(conn: sqlite3.Connection) -> int:
    """1 if subject OR object name absent from the cited evidence sentences."""
    n = 0
    for e in _base_edges(conn):
        try:
            ids = json.loads(e["evidence_sentence_ids_json"]) if e["evidence_sentence_ids_json"] else []
        except Exception:
            ids = []
        if not ids:
            _persist(conn, e["edge_id"], "subj_obj_cooccur_inv", 1.0)
            n += 1
            continue
        placeholders = ",".join("?" * len(ids))
        rows = conn.execute(
            f"SELECT text FROM sentences WHERE document_id = ? AND sentence_id IN ({placeholders})",
            (e["document_id"], *ids),
        ).fetchall()
        text = " ".join((r["text"] or "").lower() for r in rows)
        s_ok = (e["subject_name"] or "").lower() in text if e["subject_name"] else False
        o_ok = (e["object_name"] or "").lower() in text if e["object_name"] else False
        score = 0.0 if (s_ok and o_ok) else 1.0
        _persist(conn, e["edge_id"], "subj_obj_cooccur_inv", score)
        n += 1
    conn.commit()
    return n


def compute_majority_vote(conn: sqlite3.Connection,
                          target_types: Iterable[str] = ("prompt_clause",)) -> int:
    """1 - fraction of cf runs (over given target_types) where the edge survives unchanged.

    A high score means the edge fails majority vote across prompt variants:
    most prompt-clause ablations either remove or change the edge. This is
    the README §15 'majority voting across prompts' baseline.
    """
    target_set = tuple(target_types)
    placeholders = ",".join("?" * len(target_set))
    n = 0
    for e in _base_edges(conn):
        rows = conn.execute(
            f"SELECT eo.outcome_type FROM edge_outcomes eo "
            f"JOIN counterfactual_runs cr ON cr.run_id = eo.run_id "
            f"JOIN intervention_candidates ic ON ic.intervention_id = cr.intervention_id "
            f"WHERE eo.original_edge_id = ? AND ic.target_type IN ({placeholders})",
            (e["edge_id"], *target_set),
        ).fetchall()
        if not rows:
            # No prompt cf runs for this edge; skip rather than fabricate a score.
            continue
        n_change = sum(1 for r in rows if r["outcome_type"] in CHANGE_OUTCOMES)
        score = n_change / len(rows)  # higher = fails majority vote
        _persist(conn, e["edge_id"], "majority_vote_inv", score)
        n += 1
    conn.commit()
    return n


def compute_all(conn: sqlite3.Connection) -> dict:
    return {
        "confidence_inv": compute_confidence(conn),
        "source_prov_inv": compute_source_provenance(conn),
        "subj_obj_cooccur_inv": compute_subj_obj_cooccurrence(conn),
        "majority_vote_inv": compute_majority_vote(conn),
    }


def list_signals(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute(
        "SELECT DISTINCT signal FROM edge_baseline_scores ORDER BY signal"
    ).fetchall()
    return [r[0] for r in rows]


def load_for_edges(conn: sqlite3.Connection, edge_ids: list[str]) -> dict[str, dict[str, float]]:
    """Returns {edge_id: {signal: score}}."""
    if not edge_ids:
        return {}
    out: dict[str, dict[str, float]] = {eid: {} for eid in edge_ids}
    chunk = 500
    for i in range(0, len(edge_ids), chunk):
        batch = edge_ids[i:i + chunk]
        placeholders = ",".join("?" * len(batch))
        for r in conn.execute(
            f"SELECT edge_id, signal, score FROM edge_baseline_scores "
            f"WHERE edge_id IN ({placeholders})",
            batch,
        ):
            out[r[0]][r[1]] = float(r[2])
    return out
