"""E0: phenomenon study — repeat-run stability of LLM extraction.

For each document we run the same prompt/schema multiple times with different
seeds (and a small temperature so the model can vary). We then compute:

* avg_edge_overlap     mean pairwise Jaccard over edge triples (subj,rel,obj)
* type_agreement       for entity-pairs present in every run, fraction with the same relation
* disappearance_rate   mean fraction of run-A edges missing in run-B
* type_flip_rate       mean fraction of shared (subj,obj) pairs whose relation changed
* new_edge_rate        mean fraction of run-B edges absent in run-A
* stochastic_variance  per base edge: fraction of *other* runs where it is not EXACT_SAME

Results land in `stability_reports` (document level) and update
`edge_reliability_scores.stochastic_variance` for each base edge so that
`scoring/risk` recomputation can incorporate variance.
"""
from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from itertools import combinations
from typing import List, Optional

from ..db import repositories as repo
from ..extraction.extractor import extract_document
from ..llm.client import LLMClient
from ..matching.edge_matcher import match_edges

log = logging.getLogger(__name__)

# Default seeds; varied so cache misses naturally and the LLM has
# distinct random states across the n_runs.
DEFAULT_SEEDS: tuple[int, ...] = (7, 13, 23, 37, 53, 71, 97, 113)


@dataclass
class StabilityResult:
    document_id: str
    event_ids: List[str]
    n_runs: int
    avg_edge_overlap: float
    type_agreement: float
    disappearance_rate: float
    type_flip_rate: float
    new_edge_rate: float


def _edges_of_event(conn, event_id: str) -> list[sqlite3.Row]:
    return list(conn.execute(
        "SELECT * FROM extracted_edges WHERE event_id = ?", (event_id,)))


def _triples(edges: list[sqlite3.Row]) -> set[tuple[str, str, str]]:
    return {(e["subject_name"], e["relation"], e["object_name"]) for e in edges}


def _pair_keys(edges: list[sqlite3.Row]) -> dict[tuple[str, str], str]:
    out: dict[tuple[str, str], str] = {}
    for e in edges:
        out.setdefault((e["subject_name"], e["object_name"]), e["relation"])
    return out


def run_stability_for_document(
    conn,
    llm: LLMClient,
    *,
    document_row: sqlite3.Row,
    prompt_def: dict,
    schema_def: dict,
    n_runs: int = 3,
    temperature: float = 0.3,
    max_tokens: int = 2048,
    seeds: Optional[tuple[int, ...]] = None,
) -> List[str]:
    """Run `n_runs` independent extractions for one document. Returns event_ids."""
    if seeds is None:
        seeds = DEFAULT_SEEDS
    if n_runs > len(seeds):
        raise ValueError(f"need {n_runs} seeds; have {len(seeds)}")
    event_ids: list[str] = []
    for i in range(n_runs):
        try:
            event_id, n_edges = extract_document(
                conn, llm,
                document_row=document_row,
                prompt_def=prompt_def, schema_def=schema_def,
                temperature=temperature, seed=int(seeds[i]),
                max_tokens=max_tokens,
            )
            log.info("e0 run %d/%d for %s -> event=%s edges=%d",
                     i + 1, n_runs, document_row["document_id"], event_id, n_edges)
            event_ids.append(event_id)
        except Exception as e:
            log.exception("e0 run failed for %s: %s", document_row["document_id"], e)
    return event_ids


def compute_metrics(conn, document_id: str, event_ids: List[str]) -> StabilityResult:
    edges_per = [_edges_of_event(conn, eid) for eid in event_ids]
    triples_per = [_triples(es) for es in edges_per]
    pairs_per = [_pair_keys(es) for es in edges_per]

    overlaps: list[float] = []
    disappearance: list[float] = []
    new_edge: list[float] = []
    type_flip: list[float] = []
    for a, b in combinations(range(len(edges_per)), 2):
        ta, tb = triples_per[a], triples_per[b]
        union = ta | tb
        overlaps.append(len(ta & tb) / len(union) if union else 1.0)
        if ta:
            disappearance.append(len(ta - tb) / len(ta))
        if tb:
            new_edge.append(len(tb - ta) / len(tb))
        common_pairs = set(pairs_per[a]) & set(pairs_per[b])
        if common_pairs:
            flips = sum(1 for p in common_pairs if pairs_per[a][p] != pairs_per[b][p])
            type_flip.append(flips / len(common_pairs))

    # type agreement: pairs that appear in every run with same relation
    if pairs_per:
        common_all = set(pairs_per[0])
        for pp in pairs_per[1:]:
            common_all &= set(pp)
        if common_all:
            same_rel = sum(
                1 for p in common_all
                if all(pp[p] == pairs_per[0][p] for pp in pairs_per)
            )
            type_agreement = same_rel / len(common_all)
        else:
            type_agreement = 0.0
    else:
        type_agreement = 0.0

    def _mean(xs: list[float]) -> float:
        return sum(xs) / len(xs) if xs else 0.0

    return StabilityResult(
        document_id=document_id, event_ids=event_ids, n_runs=len(event_ids),
        avg_edge_overlap=_mean(overlaps),
        type_agreement=type_agreement,
        disappearance_rate=_mean(disappearance),
        type_flip_rate=_mean(type_flip),
        new_edge_rate=_mean(new_edge),
    )


def update_stochastic_variance(conn, base_event_id: str, other_event_ids: List[str],
                               base_relation_ids: set[str]) -> int:
    """For each edge in `base_event_id`, set its stochastic_variance to the
    fraction of `other_event_ids` whose extraction did NOT contain an EXACT_SAME match.

    Returns the number of base edges updated.
    """
    base_edges = _edges_of_event(conn, base_event_id)
    if not base_edges or not other_event_ids:
        return 0
    runs_changed: dict[str, int] = {e["edge_id"]: 0 for e in base_edges}
    for oid in other_event_ids:
        cf_edges = _edges_of_event(conn, oid)
        outcomes = match_edges(base_edges, cf_edges, run_id=f"e0::{oid}",
                               base_relation_ids=base_relation_ids)
        for o in outcomes:
            if o.outcome_type != "EXACT_SAME":
                runs_changed[o.original_edge_id] = runs_changed.get(o.original_edge_id, 0) + 1
    n = len(other_event_ids)
    written = 0
    for edge_id, changed in runs_changed.items():
        var = changed / n
        cur = conn.execute(
            "SELECT * FROM edge_reliability_scores WHERE edge_id = ?", (edge_id,)
        ).fetchone()
        if cur is None:
            conn.execute(
                "INSERT INTO edge_reliability_scores(edge_id, stochastic_variance, computed_at)"
                " VALUES (?, ?, datetime('now'))",
                (edge_id, var),
            )
        else:
            conn.execute(
                "UPDATE edge_reliability_scores SET stochastic_variance = ?, "
                "computed_at = datetime('now') WHERE edge_id = ?",
                (var, edge_id),
            )
        written += 1
    conn.commit()
    return written
