"""Load prompt and schema configs and render the base prompt."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import yaml

from ..db import repositories as repo


def load_yaml(path: str | Path) -> dict:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def get_prompt_def(prompts_yaml: dict, prompt_id: str) -> dict:
    for p in prompts_yaml["prompts"]:
        if p["id"] == prompt_id:
            return p
    raise KeyError(f"prompt '{prompt_id}' not found")


def get_schema_def(schemas_yaml: dict, schema_id: str) -> dict:
    for s in schemas_yaml["schemas"]:
        if s["id"] == schema_id:
            return s
    raise KeyError(f"schema '{schema_id}' not found")


def render_clauses(prompt_def: dict, active_clause_ids: Optional[list[str]] = None) -> str:
    clauses = prompt_def.get("clauses", [])
    if active_clause_ids is not None:
        active = set(active_clause_ids)
        clauses = [c for c in clauses if c["id"] in active]
    lines = [f"- {c['text']}" for c in clauses]
    return "\n".join(lines)


def render_schema(schema_def: dict) -> str:
    out = [f"Schema id: {schema_def['id']}",
           f"Description: {schema_def.get('description', '')}",
           "Relations:"]
    for r in schema_def["relations"]:
        out.append(f"  - {r['id']} ({r['label']}): {r.get('description','').strip()}")
    return "\n".join(out)


def render_document(sentences: list[dict | object]) -> str:
    lines = []
    for s in sentences:
        idx = s["sentence_index"] if isinstance(s, dict) else s["sentence_index"]
        text = s["text"] if isinstance(s, dict) else s["text"]
        lines.append(f"[{idx + 1}] {text}")
    return "\n".join(lines)


def render_entities(entities: list) -> str:
    lines = []
    for e in entities:
        name = e["canonical_name"]
        ent_type = e["entity_type"] or "ENT"
        lines.append(f"- {name} (type={ent_type}, id={e['entity_id']})")
    return "\n".join(lines)


def render_prompt(prompt_def: dict, schema_def: dict,
                  sentences: list, entities: list,
                  active_clause_ids: Optional[list[str]] = None) -> str:
    template: str = prompt_def["template"]
    return template.format(
        clauses=render_clauses(prompt_def, active_clause_ids),
        schema=render_schema(schema_def),
        document=render_document(sentences),
        entities=render_entities(entities),
    )


def register_prompt(conn, prompt_def: dict) -> None:
    """Persist prompt + clauses (idempotent) for lineage tracking."""
    clause_ids = [c["id"] for c in prompt_def.get("clauses", [])]
    repo.upsert_prompt(conn, repo.PromptRow(
        prompt_id=prompt_def["id"],
        name=prompt_def.get("name", prompt_def["id"]),
        full_prompt=prompt_def["template"],
        clause_ids=clause_ids,
    ))
    repo.upsert_prompt_clauses(conn, [
        repo.PromptClause(
            clause_id=c["id"], prompt_id=prompt_def["id"],
            clause_type=c.get("type", ""), clause_text=c["text"],
        ) for c in prompt_def.get("clauses", [])
    ])


def register_schema(conn, schema_def: dict) -> None:
    repo.upsert_schema(conn, repo.SchemaRow(
        schema_id=schema_def["id"],
        name=schema_def.get("name", schema_def["id"]),
        description=schema_def.get("description", ""),
        relation_types=schema_def["relations"],
    ))
