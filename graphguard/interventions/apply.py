"""Apply an intervention candidate to (sentences, prompt_def, schema_def).

Returns the modified inputs without mutating the originals. The caller is
responsible for re-rendering the prompt and re-invoking the LLM.
"""
from __future__ import annotations

import sqlite3
from typing import Optional

from . import prompt as iv_prompt
from . import schema as iv_schema
from . import text as iv_text


def apply(conn: sqlite3.Connection, intervention: sqlite3.Row, *,
          sentences, prompt_def: dict, schema_def: dict,
          drop_relation_for_doc: Optional[str] = None) -> tuple:
    """Returns (sentences', prompt_def', schema_def')."""
    target_type = intervention["target_type"]
    operator = intervention["operator"]
    target_id = intervention["target_id"]

    if target_type == "sentence":
        muts = iv_text.to_mutable(sentences)
        if operator == "remove":
            muts = iv_text.remove_sentence(muts, target_id)
        elif operator == "mask":
            muts = iv_text.mask_sentence(muts, target_id)
        elif operator == "para_swap":
            muts = iv_text.swap_paragraphs(muts)
        elif operator == "entity_alias":
            muts = iv_text.entity_alias_rewrite(muts)
        else:
            raise ValueError(f"unknown sentence operator: {operator}")
        return muts, prompt_def, schema_def

    if target_type == "prompt_clause":
        if operator == "remove" or target_id.startswith("C"):
            new_prompt = iv_prompt.remove_clauses(prompt_def, [target_id])
        elif operator == "role_swap":
            new_prompt = iv_prompt.role_swap(prompt_def, target_id)
        elif operator == "tone":
            new_prompt = iv_prompt.tone(prompt_def, target_id)
        else:
            new_prompt = iv_prompt.remove_clauses(prompt_def, [target_id])
        return sentences, new_prompt, schema_def

    if target_type == "schema":
        if target_id == "with_other":
            new_schema = iv_schema.schema_with_other(schema_def)
        elif target_id == "coarse":
            new_schema = iv_schema.schema_coarse(schema_def)
        elif target_id.startswith("drop:"):
            new_schema = iv_schema.schema_without_specific(schema_def, target_id.split(":", 1)[1])
        elif target_id == "ambiguous":
            rels = [drop_relation_for_doc] if drop_relation_for_doc else [
                r["id"] for r in schema_def.get("relations", [])
                if r.get("id") not in {"OTHER", "related_to"}
            ][:3]
            new_schema = iv_schema.schema_ambiguous(schema_def, rels)
        elif target_id.startswith("ambiguous:"):
            rels = [r for r in target_id.split(":", 1)[1].split(",") if r]
            new_schema = iv_schema.schema_ambiguous(schema_def, rels)
        elif target_id == "rename":
            new_schema = iv_schema.schema_rename(schema_def)
        elif target_id == "reorder":
            new_schema = iv_schema.schema_reorder(schema_def)
        elif target_id == "desc_added":
            new_schema = iv_schema.schema_description_added(schema_def)
        elif target_id == "desc_removed":
            new_schema = iv_schema.schema_description_removed(schema_def)
        elif target_id == "hierarchical":
            new_schema = iv_schema.schema_hierarchical(schema_def)
        else:
            raise ValueError(f"unknown schema variant: {target_id}")
        return sentences, prompt_def, new_schema

    if target_type == "noop":
        # Same inputs; downstream changes only the seed/temperature to elicit
        # stochastic variation. Caller (runner) bumps seed when it sees noop.
        return sentences, prompt_def, schema_def

    if target_type == "model":
        # Model swap is handled at the LLM-client level by the multi-model runner;
        # for in-process runs we treat as no-op so the bookkeeping stays clean.
        return sentences, prompt_def, schema_def

    raise ValueError(f"unknown target_type: {target_type}")
