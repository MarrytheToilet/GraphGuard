"""E3: schema debugging — show that schema choices distort relation types.

Inputs (in DB):
    extracted_edges joined by counterfactual_runs whose intervention.target_type='schema'.
    The base extraction edges are the baseline graph for each (document, base_event).

Outputs:
    confusion_matrix : dict[str -> dict[str -> int]]
        Maps base relation -> cf relation -> count, where cf relation is
        the relation of the matched cf edge (or 'DISAPPEARED' / 'OTHER').
    flip_rates       : dict[str -> dict] per schema variant:
        type_flip_rate, disappearance_rate, percent_downgraded_to_other,
        percent_correct_to_wrong (vs gold), percent_wrong_to_correct (vs gold).
"""
from __future__ import annotations

import sqlite3
from collections import defaultdict
from typing import Dict, List, Tuple


CHANGE = {"DISAPPEARED", "TYPE_FLIP", "OBJECT_FLIP", "SUBJECT_FLIP", "AMBIGUOUS"}


def _gold_relations_per_doc(conn: sqlite3.Connection) -> Dict[str, Dict[Tuple[str, str], str]]:
    """document_id -> {(head_name_lower, tail_name_lower): relation_base}"""
    out: Dict[str, Dict[Tuple[str, str], str]] = defaultdict(dict)
    for r in conn.execute(
        "SELECT document_id, head_name, tail_name, relation_base FROM gold_edges"
    ):
        if not (r["head_name"] and r["tail_name"] and r["relation_base"]):
            continue
        out[r["document_id"]][(r["head_name"].lower(), r["tail_name"].lower())] = r["relation_base"]
    return out


def evaluate_schema(conn: sqlite3.Connection) -> dict:
    gold_lookup = _gold_relations_per_doc(conn)

    # Confusion matrix at base-edge level (relation_before -> relation_after)
    confusion: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    by_variant: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))

    rows = list(conn.execute("""
        SELECT eo.outcome_type, eo.relation_after,
               be.relation AS base_relation, be.document_id,
               be.subject_name, be.object_name,
               ic.target_id AS schema_variant, ic.intervention_id
        FROM edge_outcomes eo
        JOIN counterfactual_runs cfr ON cfr.run_id = eo.run_id
        JOIN intervention_candidates ic ON ic.intervention_id = cfr.intervention_id
        JOIN extracted_edges be ON be.edge_id = eo.original_edge_id
        WHERE ic.target_type = 'schema'
    """))

    for r in rows:
        base_rel = r["base_relation"]
        if r["outcome_type"] == "DISAPPEARED":
            cf_rel = "<DISAPPEARED>"
        elif r["outcome_type"] == "EXACT_SAME":
            cf_rel = base_rel
        else:
            cf_rel = r["relation_after"] or "<UNKNOWN>"
        confusion[base_rel][cf_rel] += 1

        v = r["schema_variant"]
        bucket = by_variant[v]
        bucket["n"] += 1
        if r["outcome_type"] in CHANGE:
            bucket["changed"] += 1
        if r["outcome_type"] == "TYPE_FLIP":
            bucket["type_flip"] += 1
        if r["outcome_type"] == "DISAPPEARED":
            bucket["disappeared"] += 1
        if cf_rel.lower() in ("other", "<unknown>"):
            bucket["downgraded_other"] += 1

        # vs gold: did this base edge correspond to a gold triple?
        gold_map = gold_lookup.get(r["document_id"], {})
        gold_rel = gold_map.get(((r["subject_name"] or "").lower(),
                                 (r["object_name"] or "").lower()))
        if gold_rel is not None:
            base_correct = (base_rel == gold_rel)
            cf_correct = (cf_rel == gold_rel)
            if base_correct and not cf_correct:
                bucket["correct_to_wrong"] += 1
            elif (not base_correct) and cf_correct:
                bucket["wrong_to_correct"] += 1

    # finalize percentages
    flip_rates: Dict[str, dict] = {}
    for v, b in by_variant.items():
        n = b.get("n", 0) or 1
        flip_rates[v] = {
            "n_observations": b.get("n", 0),
            "type_flip_rate": b.get("type_flip", 0) / n,
            "disappearance_rate": b.get("disappeared", 0) / n,
            "percent_downgraded_to_other": b.get("downgraded_other", 0) / n,
            "percent_correct_to_wrong": b.get("correct_to_wrong", 0) / n,
            "percent_wrong_to_correct": b.get("wrong_to_correct", 0) / n,
        }

    # confusion matrix: convert to plain dict
    confusion_plain = {k: dict(v) for k, v in confusion.items()}
    return {"confusion_matrix": confusion_plain, "flip_rates": flip_rates}
