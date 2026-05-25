"""Normalize raw LLM extraction output into ExtractedEdge rows."""
from __future__ import annotations

import json
import uuid
from typing import Optional

from ..db import repositories as repo
from .schemas import normalize_relation


def _match_entity(name: str, entities_by_lc: dict[str, dict]) -> Optional[dict]:
    if not name:
        return None
    direct = entities_by_lc.get(name.lower())
    if direct:
        return direct
    for canon_lc, ent in entities_by_lc.items():
        # cheap alias match: substring overlap on canonical name only (M1 keeps it minimal)
        if canon_lc in name.lower() or name.lower() in canon_lc:
            return ent
    return None


def normalize_edges(raw_obj: dict, *,
                    event_id: str,
                    document_id: str,
                    sentences: list,
                    entities: list,
                    schema_def: dict) -> list[repo.ExtractedEdge]:
    edges_in = raw_obj.get("edges") or []
    if not isinstance(edges_in, list):
        return []

    # canonical -> entity row (sqlite Row supports __getitem__ by key)
    entities_by_lc = {e["canonical_name"].lower(): e for e in entities}
    n_sent = len(sentences)

    out: list[repo.ExtractedEdge] = []
    for raw_edge in edges_in:
        if not isinstance(raw_edge, dict):
            continue
        subj_name = (raw_edge.get("subject") or "").strip()
        obj_name = (raw_edge.get("object") or "").strip()
        rel_raw = (raw_edge.get("relation") or "").strip()
        if not subj_name or not obj_name or not rel_raw:
            continue

        rel = normalize_relation(rel_raw, schema_def)
        subj = _match_entity(subj_name, entities_by_lc)
        obj = _match_entity(obj_name, entities_by_lc)

        ev_raw = raw_edge.get("evidence_sentences") or []
        ev_sentence_ids: list[str] = []
        if isinstance(ev_raw, list):
            for v in ev_raw:
                try:
                    one_based = int(v)
                except Exception:
                    continue
                idx0 = one_based - 1
                if 0 <= idx0 < n_sent:
                    ev_sentence_ids.append(sentences[idx0]["sentence_id"])

        conf = raw_edge.get("confidence")
        try:
            conf = float(conf) if conf is not None else None
        except Exception:
            conf = None

        out.append(repo.ExtractedEdge(
            edge_id=f"{event_id}::{uuid.uuid4().hex[:10]}",
            event_id=event_id,
            document_id=document_id,
            subject_entity_id=subj["entity_id"] if subj else None,
            subject_name=subj_name,
            relation=rel,
            object_entity_id=obj["entity_id"] if obj else None,
            object_name=obj_name,
            evidence_sentence_ids=ev_sentence_ids,
            confidence=conf,
            raw_json=json.dumps(raw_edge, ensure_ascii=False),
        ))
    return out
