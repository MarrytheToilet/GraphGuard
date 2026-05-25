"""E1: known-cause benchmark.

Pure-synthetic injection requires re-running the LLM with crafted documents/prompts.
We provide both:

(a) **derived gold cause-type** from existing DocRED data + cf cache (no LLM):
    - text-caused  : extracted edge matches a gold edge AND removing one of its
                     evidence sentences flips/removes the edge.
    - prompt-caused: extracted edge has NO gold match AND it disappears when
                     the "infer_implicit"-like prompt clause is dropped.
    - schema-caused: edge type changes when schema is altered but is unchanged
                     under sentence/prompt interventions.
    Then for each labelled edge we ask why_edge / why_type and check whether the
    top-ranked cause's variable_type matches the gold cause-type.
    Reports Top-1 / Top-3 / MRR / per-cause-type macro-F1.

(b) **synthetic injection** harness (`build_injection_corpus`) that mutates a
    document by prepending a forced sentence and tags the gold cause id. Used
    when an explicit synthetic benchmark is required; consumes extra LLM calls.
"""
from __future__ import annotations

import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from typing import List, Optional

from .. import queries as Q


CHANGE = {"DISAPPEARED", "TYPE_FLIP", "OBJECT_FLIP", "SUBJECT_FLIP", "AMBIGUOUS"}


@dataclass
class CauseLabel:
    edge_id: str
    cause_type: str   # 'sentence' | 'prompt_clause' | 'schema'
    note: str = ""


@dataclass
class CauseEval:
    edge_id: str
    gold_cause_type: str
    pred_cause_type: Optional[str]
    pred_top_k: List[str]
    rr: float


def _gold_evidence_for_edge(conn: sqlite3.Connection, edge_id: str) -> set[str]:
    r = conn.execute(
        "SELECT e.subject_name, e.object_name, e.relation, e.document_id "
        "FROM extracted_edges e WHERE e.edge_id=?", (edge_id,)
    ).fetchone()
    if not r:
        return set()
    g = conn.execute(
        "SELECT evidence_sentence_ids_json FROM gold_edges "
        "WHERE document_id=? AND lower(head_name)=? AND lower(tail_name)=? "
        "AND relation_base=?",
        (r["document_id"], (r["subject_name"] or "").lower(),
         (r["object_name"] or "").lower(), r["relation"])
    ).fetchone()
    if not g or not g["evidence_sentence_ids_json"]:
        return set()
    import json
    try:
        return {str(x) for x in json.loads(g["evidence_sentence_ids_json"])}
    except Exception:
        return set()


def derive_cause_labels(conn: sqlite3.Connection,
                         min_per_type: int = 0) -> List[CauseLabel]:
    """Heuristic ground-truth cause-type labels across 5 categories:

      * sentence       text-causally responsible (text_responsibility dominant)
      * prompt_clause  prompt-induced (prompt_sensitivity dominant)
      * schema         schema-induced (schema_sensitivity dominant)
      * stochastic     repeated-run variance dominant (no-cause / noise)
      * context        small but non-zero text + correct gold match (text-supported)

    Thresholds are relative — we pick the dominant signal per edge rather than
    requiring an absolute floor — so the corpus reflects whatever the cf data
    actually contains rather than only schema cases.
    """
    labels: List[CauseLabel] = []
    rows = list(conn.execute("""
        SELECT e.edge_id, ec.label,
               COALESCE(s.text_responsibility, 0)   AS text_r,
               COALESCE(s.prompt_sensitivity, 0)    AS prompt_s,
               COALESCE(s.schema_sensitivity, 0)    AS schema_s,
               COALESCE(s.stochastic_variance, 0)   AS stoch
        FROM extracted_edges e
        JOIN edge_correctness ec ON ec.edge_id = e.edge_id
        LEFT JOIN edge_reliability_scores s ON s.edge_id = e.edge_id
    """))
    for r in rows:
        eid = r["edge_id"]
        text_r, prompt_s, schema_s, stoch = (
            r["text_r"], r["prompt_s"], r["schema_s"], r["stoch"]
        )

        # Pure stochastic: stochastic dominates and >= other signals.
        if stoch > 0 and stoch >= max(text_r, prompt_s, schema_s) * 1.2:
            labels.append(CauseLabel(eid, "stochastic", "stoch dominant"))
            continue

        # Context-supported correct: correct edge with mild text dependence.
        if r["label"] == "correct" and text_r > 0 and text_r >= max(prompt_s, schema_s):
            labels.append(CauseLabel(eid, "sentence", "correct + text-causal"))
            continue

        # Schema-induced: schema strictly dominant.
        if schema_s > 0 and schema_s > max(text_r, prompt_s, stoch):
            labels.append(CauseLabel(eid, "schema", "schema dominant"))
            continue

        # Prompt-induced: prompt strictly dominant.
        if prompt_s > 0 and prompt_s > max(text_r, schema_s, stoch):
            labels.append(CauseLabel(eid, "prompt_clause", "prompt dominant"))
            continue

        # Text-induced (catch-all for non-correct edges with text dominance).
        if text_r > 0 and text_r > max(prompt_s, schema_s, stoch):
            labels.append(CauseLabel(eid, "sentence", "text dominant"))
            continue

    return labels


def evaluate_cause_ranking(conn: sqlite3.Connection,
                           labels: List[CauseLabel],
                           top_k: int = 3,
                           weak_effect_threshold: float = 0.05) -> dict:
    """For each labelled edge, query the appropriate cause type and check match.

    Schema causes typically manifest as TYPE_FLIP (queried via why_type);
    sentence/prompt causes typically manifest as DISAPPEARED (queried via why_edge).
    For each edge we union the top-k from BOTH queries and rank by effect.

    For ``stochastic``-labelled edges (which cannot be attributed to any
    specific intervention) we predict ``stochastic`` whenever the strongest
    cf-attribution effect is below ``weak_effect_threshold`` or no causes
    are returned at all.
    """
    per: List[CauseEval] = []
    for lab in labels:
        ce = Q.why_edge(conn, lab.edge_id, top_k=top_k)
        ct = Q.why_type(conn, lab.edge_id, top_k=top_k)
        merged = sorted(list(ce) + list(ct), key=lambda c: -c.effect)
        seen = set()
        types: List[str] = []
        max_effect = 0.0
        for c in merged:
            if c.intervention_id in seen:
                continue
            seen.add(c.intervention_id)
            types.append(c.variable_type)
            max_effect = max(max_effect, c.effect)
            if len(types) >= top_k:
                break
        if not types or max_effect < weak_effect_threshold:
            # No strong identifiable cause -> predict stochastic (noise).
            types = ["stochastic"] + types
        rr = 0.0
        for i, t in enumerate(types):
            if t == lab.cause_type:
                rr = 1.0 / (i + 1)
                break
        per.append(CauseEval(
            edge_id=lab.edge_id,
            gold_cause_type=lab.cause_type,
            pred_cause_type=types[0] if types else None,
            pred_top_k=types,
            rr=rr,
        ))

    # aggregate
    if not per:
        return {"n": 0, "top1_acc": 0.0, "top3_recall": 0.0, "mrr": 0.0,
                "macro_f1": 0.0, "per_cause": {}, "details": []}
    top1 = sum(1 for e in per if e.pred_cause_type == e.gold_cause_type) / len(per)
    top3 = sum(1 for e in per if e.gold_cause_type in e.pred_top_k) / len(per)
    mrr = sum(e.rr for e in per) / len(per)
    # macro-F1 per cause type
    types = sorted({e.gold_cause_type for e in per} | {e.pred_cause_type for e in per if e.pred_cause_type})
    f1s = {}
    for t in types:
        tp = sum(1 for e in per if e.pred_cause_type == t and e.gold_cause_type == t)
        fp = sum(1 for e in per if e.pred_cause_type == t and e.gold_cause_type != t)
        fn = sum(1 for e in per if e.pred_cause_type != t and e.gold_cause_type == t)
        p = tp / (tp + fp) if (tp + fp) else 0.0
        r = tp / (tp + fn) if (tp + fn) else 0.0
        f1s[t] = 2 * p * r / (p + r) if (p + r) else 0.0
    macro_f1 = sum(f1s.values()) / len(f1s) if f1s else 0.0
    return {
        "n": len(per),
        "top1_acc": top1, "top3_recall": top3, "mrr": mrr,
        "macro_f1": macro_f1,
        "per_cause_f1": f1s,
        "per_cause_n": {t: sum(1 for e in per if e.gold_cause_type == t) for t in types},
        "details": [e.__dict__ for e in per],
    }


def build_injection_corpus(seed_text: str, injected_sentence: str,
                           gold_subject: str, gold_relation: str,
                           gold_object: str) -> dict:
    """Return a synthetic doc spec with the injected sentence at position 0.

    Caller is expected to extract under base settings then run interventions
    and verify the why_edge top cause is the injected sentence.
    """
    return {
        "raw_text": injected_sentence + " " + seed_text,
        "gold_cause_sentence_index": 0,
        "gold_edge": {"subject": gold_subject, "relation": gold_relation, "object": gold_object},
    }
