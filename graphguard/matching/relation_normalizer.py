"""Map an LLM-emitted relation token back to the BASE schema relation id.

Used during edge matching, since counterfactual extractions may use a coarse
or otherwise modified schema. We project relations back to base ids so we can
compare a base edge against a counterfactual edge.
"""
from __future__ import annotations

from typing import Optional

from ..interventions.schema import COARSE_GROUPS, RELATION_RENAMES

_INVERSE_COARSE: dict[str, list[str]] = {bucket: ids for bucket, ids in COARSE_GROUPS.items()}
_INVERSE_RENAME: dict[str, str] = {v: k for k, v in RELATION_RENAMES.items()}


def project_to_base(rel: str, *, base_relation_ids: set[str]) -> Optional[str]:
    """If `rel` is already a base id, return it. If it's a known rename alias for
    a base id (presentation-only schema variant), return the base id. Otherwise
    return None (caller treats as TYPE_FLIP).
    """
    if rel in base_relation_ids:
        return rel
    base = _INVERSE_RENAME.get(rel)
    if base and base in base_relation_ids:
        return base
    return None


def is_coarse_bucket(rel: str) -> bool:
    return rel in _INVERSE_COARSE
