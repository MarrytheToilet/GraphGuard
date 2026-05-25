"""Programmatic schema variants for counterfactual extraction.

S_full              : original schema (passthrough)
S_with_other        : add OTHER if missing (often already present)
S_coarse            : merge fine-grained relations into coarse buckets
S_without_specific  : drop a single relation id to test schema-induced flips
S_ambiguous         : replace several relations with `related_to`
"""
from __future__ import annotations

import copy
from typing import Optional

# Coarse bucket mapping for the DocRED subset shipped in configs/schemas.yaml.
COARSE_GROUPS: dict[str, list[str]] = {
    "person_origin":   ["P19", "P27", "P569"],
    "person_endpoint": ["P20", "P570"],
    "person_relation": ["P26", "P40"],
    "career":          ["P54", "P69", "P108", "P463", "P54"],
    "location":        ["P17", "P131", "P150", "P159", "P361", "P527"],
    "creation":        ["P50", "P57", "P161", "P175", "P495", "P577"],
    "time":            ["P580", "P582"],
}


def schema_full(schema_def: dict) -> dict:
    s = copy.deepcopy(schema_def)
    s["id"] = schema_def["id"]
    return s


def schema_with_other(schema_def: dict) -> dict:
    s = copy.deepcopy(schema_def)
    rel_ids = {r["id"] for r in s["relations"]}
    if "OTHER" not in rel_ids:
        s["relations"].append({"id": "OTHER", "label": "other",
                               "description": "Use only if no schema relation fits."})
    s["id"] = schema_def["id"] + "_with_other"
    s["name"] = (s.get("name") or s["id"]) + " + OTHER"
    return s


def schema_coarse(schema_def: dict,
                  groups: Optional[dict[str, list[str]]] = None) -> dict:
    groups = groups or COARSE_GROUPS
    rel_to_group: dict[str, str] = {}
    for g, ids in groups.items():
        for rid in ids:
            rel_to_group[rid] = g
    grouped: dict[str, dict] = {}
    leftovers: list[dict] = []
    for r in schema_def["relations"]:
        g = rel_to_group.get(r["id"])
        if g is None:
            leftovers.append(r)
            continue
        grouped.setdefault(g, {
            "id": g, "label": g,
            "description": f"Coarse bucket of {', '.join(groups[g])}",
        })
    coarse_relations = list(grouped.values()) + leftovers
    return {
        "id": schema_def["id"] + "_coarse",
        "name": (schema_def.get("name", "") + " (coarse)").strip(),
        "description": "Coarse-grained schema variant",
        "relations": coarse_relations,
        "_coarse_map": rel_to_group,
    }


def schema_without_specific(schema_def: dict, drop_relation_id: str) -> dict:
    s = copy.deepcopy(schema_def)
    s["relations"] = [r for r in s["relations"] if r["id"] != drop_relation_id]
    s["id"] = f"{schema_def['id']}_drop_{drop_relation_id}"
    s["name"] = f"{schema_def.get('name', schema_def['id'])} (drop {drop_relation_id})"
    return s


def schema_ambiguous(schema_def: dict, replace_ids: list[str]) -> dict:
    s = copy.deepcopy(schema_def)
    replace_ids = [rid for rid in replace_ids if rid and rid != "OTHER"]
    keep = [r for r in s["relations"] if r["id"] not in replace_ids and r["id"] != "related_to"]
    keep.append({"id": "related_to", "label": "related_to",
                 "description": f"Ambiguous merge of {replace_ids}"})
    s["relations"] = keep
    suffix = "_".join(replace_ids[:4]) or "generic"
    s["id"] = f"{schema_def['id']}_ambig_{suffix}"
    s["name"] = f"{schema_def.get('name', schema_def['id'])} (ambiguous {suffix})"
    return s


# ------------------- presentation-level (semantic-preserving) variants -------------------

# Human-readable labels used by the "rename" variant. Kept stable and meaning-equivalent
# so any drift it produces is by definition presentation-induced.
RELATION_RENAMES: dict[str, str] = {
    "P17":  "located_in_country",
    "P19":  "place_of_birth",
    "P20":  "place_of_death",
    "P26":  "spouse",
    "P27":  "country_of_citizenship",
    "P40":  "child",
    "P50":  "author",
    "P54":  "member_of_sports_team",
    "P57":  "director",
    "P69":  "educated_at",
    "P108": "employer",
    "P131": "located_in_admin_unit",
    "P150": "contains_admin_unit",
    "P159": "headquarters_location",
    "P161": "cast_member",
    "P175": "performer",
    "P194": "legislative_body",
    "P361": "part_of",
    "P463": "member_of",
    "P495": "country_of_origin",
    "P527": "has_part",
    "P569": "date_of_birth",
    "P570": "date_of_death",
    "P577": "publication_date",
    "P580": "start_time",
    "P582": "end_time",
    "P1336": "territory_claimed_by",
}


def schema_rename(schema_def: dict, mapping: dict[str, str] | None = None) -> dict:
    """Rename relation ids to natural-language labels. The relation id token the LLM
    is asked to emit changes, but the meaning (description) does not. Drift here is
    pure presentation sensitivity.

    The returned schema carries a ``_rename_map_to_base`` so the matcher can
    project predictions back to base ids.
    """
    mapping = mapping or RELATION_RENAMES
    s = copy.deepcopy(schema_def)
    rev: dict[str, str] = {}
    for r in s["relations"]:
        new_id = mapping.get(r["id"])
        if new_id and new_id != r["id"]:
            rev[new_id] = r["id"]
            r["label"] = new_id
            r["id"] = new_id
    s["id"] = schema_def["id"] + "_rename"
    s["name"] = (schema_def.get("name") or schema_def["id"]) + " (rename)"
    s["_rename_map_to_base"] = rev
    return s


def schema_reorder(schema_def: dict, seed: int = 7) -> dict:
    """Shuffle the relation list. Pure presentation."""
    import random as _r
    s = copy.deepcopy(schema_def)
    rng = _r.Random(seed)
    rels = list(s["relations"])
    rng.shuffle(rels)
    s["relations"] = rels
    s["id"] = schema_def["id"] + "_reorder"
    s["name"] = (schema_def.get("name") or schema_def["id"]) + " (reorder)"
    return s


def schema_description_added(schema_def: dict) -> dict:
    """Augment relations with a short canonical description if missing."""
    s = copy.deepcopy(schema_def)
    for r in s["relations"]:
        if not r.get("description"):
            r["description"] = f"Relation {r['id']} (auto-described)."
        else:
            r["description"] = r["description"] + " Provide an answer only when supported by the text."
    s["id"] = schema_def["id"] + "_desc_added"
    s["name"] = (schema_def.get("name") or schema_def["id"]) + " (+desc)"
    return s


def schema_description_removed(schema_def: dict) -> dict:
    """Strip relation descriptions, leaving only ids/labels."""
    s = copy.deepcopy(schema_def)
    for r in s["relations"]:
        r["description"] = ""
    s["id"] = schema_def["id"] + "_desc_removed"
    s["name"] = (schema_def.get("name") or schema_def["id"]) + " (-desc)"
    return s


# Two-stage hierarchical schema: first ask coarse bucket, then keep only the
# fine-grained relations under that bucket. We approximate this in a single
# rendering by tagging each relation with its coarse parent in the description.
def schema_hierarchical(schema_def: dict,
                        groups: Optional[dict[str, list[str]]] = None) -> dict:
    groups = groups or COARSE_GROUPS
    parent: dict[str, str] = {}
    for g, ids in groups.items():
        for rid in ids:
            parent[rid] = g
    s = copy.deepcopy(schema_def)
    for r in s["relations"]:
        p = parent.get(r["id"])
        if p:
            r["description"] = f"[group={p}] " + (r.get("description") or "")
    s["id"] = schema_def["id"] + "_hierarchical"
    s["name"] = (schema_def.get("name") or schema_def["id"]) + " (hierarchical)"
    return s
