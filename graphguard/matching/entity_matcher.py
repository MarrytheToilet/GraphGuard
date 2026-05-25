"""Entity matching across base and counterfactual edges.

We strongly prefer entity_id matching: both the base extractor and the cf
extractor pass the same canonical entity list, so when normalize_edges
attaches an entity_id the comparison is exact.

Surface-form fallback: case-insensitive equality, then containment.
"""
from __future__ import annotations

from typing import Optional


def same_entity(base_entity_id: Optional[str], base_name: str,
                cf_entity_id: Optional[str], cf_name: str) -> bool:
    if base_entity_id and cf_entity_id:
        return base_entity_id == cf_entity_id
    bn, cn = (base_name or "").strip().lower(), (cf_name or "").strip().lower()
    if not bn or not cn:
        return False
    if bn == cn:
        return True
    return bn in cn or cn in bn
