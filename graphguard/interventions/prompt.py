"""Prompt-clause interventions: produce a new prompt_def with clauses removed/added."""
from __future__ import annotations

import copy
from typing import Iterable


def remove_clauses(prompt_def: dict, clause_ids: Iterable[str]) -> dict:
    drop = set(clause_ids)
    p = copy.deepcopy(prompt_def)
    p["clauses"] = [c for c in p.get("clauses", []) if c["id"] not in drop]
    suffix = "_drop_" + "_".join(sorted(drop))
    p["id"] = prompt_def["id"] + suffix
    p["name"] = (prompt_def.get("name") or prompt_def["id"]) + f" (drop {','.join(sorted(drop))})"
    return p


def add_clause(prompt_def: dict, clause: dict) -> dict:
    p = copy.deepcopy(prompt_def)
    p["clauses"] = list(p.get("clauses", [])) + [clause]
    p["id"] = prompt_def["id"] + f"_add_{clause['id']}"
    p["name"] = (prompt_def.get("name") or prompt_def["id"]) + f" (add {clause['id']})"
    return p


# ------------------- presentation-level prompt variants -------------------

ROLE_VARIANTS: dict[str, str] = {
    "expert":   "You are a senior knowledge-graph engineer with a PhD in NLP.",
    "novice":   "You are a curious student who is just learning about extraction.",
    "auditor":  "You are a meticulous data auditor who triple-checks every fact.",
    "concise":  "You are a precise extractor; answer only with the structured output.",
}


def role_swap(prompt_def: dict, role_name: str) -> dict:
    """Replace/insert a 'role' clause without changing the task instructions."""
    p = copy.deepcopy(prompt_def)
    text = ROLE_VARIANTS.get(role_name, ROLE_VARIANTS["expert"])
    clauses = [c for c in p.get("clauses", []) if c.get("id") != "C0_role"]
    clauses.insert(0, {"id": "C0_role", "text": text})
    p["clauses"] = clauses
    p["id"] = prompt_def["id"] + f"_role_{role_name}"
    p["name"] = (prompt_def.get("name") or prompt_def["id"]) + f" (role={role_name})"
    return p


TONE_VARIANTS: dict[str, str] = {
    "strict":     "Be extremely strict: only emit a relation when explicitly stated.",
    "permissive": "Be inclusive: emit any plausibly supported relation.",
    "polite":     "Please carefully consider each candidate relation before emitting.",
    "terse":      "Output the JSON only. No commentary.",
}


def tone(prompt_def: dict, tone_name: str) -> dict:
    p = copy.deepcopy(prompt_def)
    text = TONE_VARIANTS.get(tone_name, TONE_VARIANTS["terse"])
    clauses = [c for c in p.get("clauses", []) if c.get("id") != "C9_tone"]
    clauses.append({"id": "C9_tone", "text": text})
    p["clauses"] = clauses
    p["id"] = prompt_def["id"] + f"_tone_{tone_name}"
    p["name"] = (prompt_def.get("name") or prompt_def["id"]) + f" (tone={tone_name})"
    return p
