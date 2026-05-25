"""Schema convenience helpers."""
from __future__ import annotations


def relation_id_set(schema_def: dict) -> set[str]:
    return {r["id"] for r in schema_def["relations"]} | {r["label"] for r in schema_def["relations"]}


def normalize_relation(raw: str, schema_def: dict) -> str:
    """Map an LLM-emitted relation token to a canonical schema relation id (or 'OTHER')."""
    if not raw:
        return "OTHER"
    raw_norm = raw.strip()
    by_id = {r["id"]: r["id"] for r in schema_def["relations"]}
    by_label = {r["label"].lower(): r["id"] for r in schema_def["relations"]}
    if raw_norm in by_id:
        return by_id[raw_norm]
    if raw_norm.lower() in by_label:
        return by_label[raw_norm.lower()]
    return "OTHER"
