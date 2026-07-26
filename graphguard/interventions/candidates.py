"""Enumerate controlled intervention candidates for a document.

Candidates cover presentation, semantic, stochastic, and model perturbations.
Each receives a deterministic intervention ID so repeated generation is
idempotent.
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from collections import Counter
from typing import Iterable, Optional

from ..db import repositories as repo


@dataclass
class InterventionCandidate:
    intervention_id: str
    document_id: str
    target_type: str   # sentence | prompt_clause | schema | model | noop
    target_id: str
    operator: str
    description: str
    estimated_cost: float = 1.0
    group_id: Optional[str] = None
    semantic_class: str = "semantic"     # semantic | presentation | stochastic | model
    cause_family: str = "evidence"       # evidence | prompt | schema | entity_alias | model | stochastic


def _persist(conn: sqlite3.Connection, items: list[InterventionCandidate]) -> None:
    conn.executemany(
        "INSERT OR REPLACE INTO intervention_candidates"
        "(intervention_id, document_id, target_type, target_id, operator, description, "
        " estimated_cost, group_id, semantic_class, cause_family) "
        "VALUES (?,?,?,?,?,?,?,?,?,?)",
        [(i.intervention_id, i.document_id, i.target_type, i.target_id, i.operator,
          i.description, i.estimated_cost, i.group_id, i.semantic_class, i.cause_family)
         for i in items],
    )
    conn.commit()


# ---- preset operator catalogues with semantic_class / cause_family ----
PROMPT_TONE_PRESETS = ("strict", "permissive", "terse")
PROMPT_ROLE_PRESETS = ("expert", "novice", "auditor")
PRESENTATION_SCHEMA_VARIANTS = ("rename", "reorder", "desc_added", "desc_removed", "hierarchical")


def generate_for_document(conn: sqlite3.Connection,
                          document_id: str,
                          *,
                          base_prompt_id: str,
                          base_schema_id: str,
                          prompt_clauses_to_drop: Iterable[str] = ("C1_evidence_only",
                                                                   "C2_infer_implicit",
                                                                   "C3_use_schema",
                                                                   "C4_allow_other",
                                                                   "C5_cite_evidence",
                                                                   "C6_return_confidence"),
                          schema_variants: Iterable[str] = ("with_other", "coarse", "ambiguous"),
                          presentation_schema_variants: Iterable[str] = PRESENTATION_SCHEMA_VARIANTS,
                          prompt_tone_presets: Iterable[str] = PROMPT_TONE_PRESETS,
                          prompt_role_presets: Iterable[str] = PROMPT_ROLE_PRESETS,
                          include_drop_specific_for_relations: Iterable[str] = (),
                          max_drop_specific: int = 3,
                          mask_sentences: bool = True,
                          remove_sentences: bool = True,
                          evidence_presentation: bool = True,
                          noop_repeats: int = 2,
                          model_swap_targets: Iterable[str] = (),
                          ) -> list[InterventionCandidate]:
    items: list[InterventionCandidate] = []
    sents = repo.get_sentences(conn, document_id)
    base = f"{document_id}::iv"

    # ---- evidence (semantic) ----
    for s in sents:
        sid = s["sentence_id"]
        if remove_sentences:
            items.append(InterventionCandidate(
                intervention_id=f"{base}::sent::{sid}::remove",
                document_id=document_id, target_type="sentence", target_id=sid,
                operator="remove", description=f"Remove sentence {s['sentence_index']+1}",
                group_id=f"{document_id}::sent_remove",
                semantic_class="semantic", cause_family="evidence",
            ))
        if mask_sentences:
            items.append(InterventionCandidate(
                intervention_id=f"{base}::sent::{sid}::mask",
                document_id=document_id, target_type="sentence", target_id=sid,
                operator="mask", description=f"Mask sentence {s['sentence_index']+1}",
                group_id=f"{document_id}::sent_mask",
                semantic_class="semantic", cause_family="evidence",
            ))

    # ---- evidence (presentation) ----
    if evidence_presentation:
        items.append(InterventionCandidate(
            intervention_id=f"{base}::sent::doc::para_swap",
            document_id=document_id, target_type="sentence", target_id="doc",
            operator="para_swap", description="Reorder sentences (paragraph swap)",
            group_id=f"{document_id}::evidence_pres",
            semantic_class="presentation", cause_family="evidence",
        ))
        items.append(InterventionCandidate(
            intervention_id=f"{base}::sent::doc::entity_alias",
            document_id=document_id, target_type="sentence", target_id="doc",
            operator="entity_alias", description="Rewrite entities with aliases",
            group_id=f"{document_id}::entity_alias",
            semantic_class="presentation", cause_family="entity_alias",
        ))

    # ---- prompt (semantic: drop clauses) ----
    for cid in prompt_clauses_to_drop:
        items.append(InterventionCandidate(
            intervention_id=f"{base}::prompt::{base_prompt_id}::drop::{cid}",
            document_id=document_id, target_type="prompt_clause", target_id=cid,
            operator="remove", description=f"Drop prompt clause {cid} from {base_prompt_id}",
            group_id=f"{document_id}::prompt_drop",
            semantic_class="semantic", cause_family="prompt",
        ))

    # ---- prompt (presentation) ----
    for tone_name in prompt_tone_presets:
        items.append(InterventionCandidate(
            intervention_id=f"{base}::prompt::{base_prompt_id}::tone::{tone_name}",
            document_id=document_id, target_type="prompt_clause", target_id=tone_name,
            operator="tone", description=f"Switch prompt tone to {tone_name}",
            group_id=f"{document_id}::prompt_tone",
            semantic_class="presentation", cause_family="prompt",
        ))
    for role_name in prompt_role_presets:
        items.append(InterventionCandidate(
            intervention_id=f"{base}::prompt::{base_prompt_id}::role::{role_name}",
            document_id=document_id, target_type="prompt_clause", target_id=role_name,
            operator="role_swap", description=f"Switch prompt role to {role_name}",
            group_id=f"{document_id}::prompt_role",
            semantic_class="presentation", cause_family="prompt",
        ))

    # ---- schema (semantic) ----
    doc_relations = _doc_relation_candidates(conn, document_id, max_drop_specific)
    explicit_drop = list(include_drop_specific_for_relations)

    for variant in schema_variants:
        if variant == "ambiguous" and doc_relations:
            target_id = "ambiguous:" + ",".join(doc_relations[: min(3, len(doc_relations))])
        else:
            target_id = variant
        items.append(InterventionCandidate(
            intervention_id=f"{base}::schema::{base_schema_id}::{target_id}",
            document_id=document_id, target_type="schema", target_id=target_id,
            operator="switch_schema",
            description=f"Switch schema to variant '{target_id}' of {base_schema_id}",
            group_id=f"{document_id}::schema_sem",
            semantic_class="semantic", cause_family="schema",
        ))

    drop_rels = explicit_drop or doc_relations
    for rel in drop_rels[:max_drop_specific]:
        if not rel or rel == "OTHER":
            continue
        items.append(InterventionCandidate(
            intervention_id=f"{base}::schema::{base_schema_id}::drop::{rel}",
            document_id=document_id, target_type="schema", target_id=f"drop:{rel}",
            operator="switch_schema",
            description=f"Schema variant: drop relation {rel}",
            group_id=f"{document_id}::schema_sem",
            semantic_class="semantic", cause_family="schema",
        ))

    # ---- schema (presentation) ----
    for variant in presentation_schema_variants:
        items.append(InterventionCandidate(
            intervention_id=f"{base}::schema::{base_schema_id}::{variant}",
            document_id=document_id, target_type="schema", target_id=variant,
            operator="switch_schema",
            description=f"Presentation schema variant '{variant}'",
            group_id=f"{document_id}::schema_pres",
            semantic_class="presentation", cause_family="schema",
        ))

    # ---- stochastic (noop repeats) ----
    for k in range(int(noop_repeats)):
        items.append(InterventionCandidate(
            intervention_id=f"{base}::noop::repeat::{k}",
            document_id=document_id, target_type="noop", target_id=f"seed{k}",
            operator="repeat", description=f"No-op re-run #{k}",
            group_id=f"{document_id}::noop",
            semantic_class="stochastic", cause_family="stochastic",
        ))

    # ---- model swap (handled by multi-model runner) ----
    for m in model_swap_targets:
        items.append(InterventionCandidate(
            intervention_id=f"{base}::model::swap::{m}",
            document_id=document_id, target_type="model", target_id=m,
            operator="swap", description=f"Re-extract with model {m}",
            group_id=f"{document_id}::model",
            semantic_class="model", cause_family="model",
        ))

    _persist(conn, items)
    return items


def _doc_relation_candidates(conn: sqlite3.Connection, document_id: str, limit: int) -> list[str]:
    """Relations worth probing with drop-specific/ambiguous schema variants.

    Prefer relations already produced by the base extractor (what schema changes can
    plausibly flip), then backfill with gold relations for coverage before
    correctness labels exist.
    """
    counts: Counter[str] = Counter()
    for r in conn.execute(
        "SELECT relation, COUNT(*) AS n FROM extracted_edges "
        "WHERE document_id=? GROUP BY relation",
        (document_id,),
    ):
        if r["relation"] and r["relation"] != "OTHER":
            counts[r["relation"]] += int(r["n"])
    for r in conn.execute(
        "SELECT relation_base, COUNT(*) AS n FROM gold_edges "
        "WHERE document_id=? GROUP BY relation_base",
        (document_id,),
    ):
        if r["relation_base"] and r["relation_base"] != "OTHER":
            counts[r["relation_base"]] += int(r["n"])
    return [rel for rel, _ in counts.most_common(limit)]


def list_for_document(conn: sqlite3.Connection, document_id: str) -> list[sqlite3.Row]:
    return list(conn.execute(
        "SELECT * FROM intervention_candidates WHERE document_id = ? ORDER BY intervention_id",
        (document_id,)
    ))
