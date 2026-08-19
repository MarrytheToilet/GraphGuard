"""Controlled perturbation-magnitude experiment utilities.

The confirmatory design applies one nested information-attenuation operator to
three configuration axes:

* schema: mask tokens in non-``OTHER`` relation descriptions;
* prompt: mask tokens in task clauses C1--C6;
* evidence: mask tokens in sentence text.

For every family, an occurrence-level stable hash defines one ordering of the
eligible tokens.  A level masks the first ``ceil(q * n)`` occurrences, so the
changed sets are deterministic and strictly nested.  The helpers in this
module are pure: they neither call a model nor write experiment artifacts.
"""
from __future__ import annotations

import copy
import hashlib
import math
import re
from dataclasses import dataclass
from typing import Any, Iterable, Sequence


NOMINAL_LEVELS: tuple[float, ...] = (0.10, 0.25, 0.50, 0.75)
PROMPT_TASK_CLAUSES: frozenset[str] = frozenset(
    {
        "C1_evidence_only",
        "C2_infer_implicit",
        "C3_use_schema",
        "C4_allow_other",
        "C5_cite_evidence",
        "C6_return_confidence",
    }
)
MASK_TOKEN = "[MASK]"
TOKEN_PATTERN = re.compile(r"\S+")


@dataclass(frozen=True)
class TokenOccurrence:
    """One eligible whitespace-token occurrence."""

    field_id: str
    token_index: int

    @property
    def key(self) -> str:
        return f"{self.field_id}::{self.token_index}"


@dataclass(frozen=True)
class MaskPlan:
    """Deterministic nested target set for one family and nominal level."""

    family: str
    nominal_magnitude: float
    changed: int
    eligible: int
    actual_magnitude: float
    changed_keys: tuple[str, ...]
    changed_digest: str


@dataclass(frozen=True)
class MaskedVariant:
    """A transformed payload plus its inspectable masking plan."""

    payload: Any
    plan: MaskPlan


def whitespace_tokens(text: str) -> list[str]:
    """Return the tokens counted by the registered magnitude denominator."""
    return TOKEN_PATTERN.findall(text or "")


def _stable_order(
    occurrences: Iterable[TokenOccurrence],
    *,
    design_seed: str,
    corpus: str,
    document_id: str,
    family: str,
) -> list[TokenOccurrence]:
    def order_key(occ: TokenOccurrence) -> tuple[str, str]:
        material = "\x1f".join(
            (design_seed, corpus, document_id, family, occ.field_id, str(occ.token_index))
        )
        return hashlib.sha256(material.encode("utf-8")).hexdigest(), occ.key

    return sorted(occurrences, key=order_key)


def _plan(
    occurrences: Sequence[TokenOccurrence],
    *,
    q: float,
    design_seed: str,
    corpus: str,
    document_id: str,
    family: str,
) -> MaskPlan:
    if not 0 < q < 1:
        raise ValueError(f"nominal magnitude must lie in (0,1), got {q}")
    if not occurrences:
        raise ValueError(f"{family}: no eligible tokens")
    ordered = _stable_order(
        occurrences,
        design_seed=design_seed,
        corpus=corpus,
        document_id=document_id,
        family=family,
    )
    changed = min(len(ordered), max(1, math.ceil(q * len(ordered))))
    changed_keys = tuple(sorted(occ.key for occ in ordered[:changed]))
    digest = hashlib.sha256("\n".join(changed_keys).encode("utf-8")).hexdigest()
    return MaskPlan(
        family=family,
        nominal_magnitude=q,
        changed=changed,
        eligible=len(ordered),
        actual_magnitude=changed / len(ordered),
        changed_keys=changed_keys,
        changed_digest=digest,
    )


def _mask_text(text: str, selected_token_indices: set[int]) -> str:
    token_index = 0

    def replace(match: re.Match[str]) -> str:
        nonlocal token_index
        out = MASK_TOKEN if token_index in selected_token_indices else match.group(0)
        token_index += 1
        return out

    return TOKEN_PATTERN.sub(replace, text or "")


def _validate_nested(plans: Sequence[MaskPlan]) -> None:
    previous: set[str] = set()
    previous_changed = 0
    for plan in plans:
        current = set(plan.changed_keys)
        if not previous < current and previous:
            raise ValueError(
                f"{plan.family}: levels are not strictly nested at "
                f"q={plan.nominal_magnitude}"
            )
        if plan.changed <= previous_changed:
            raise ValueError(
                f"{plan.family}: duplicate rounded level at q={plan.nominal_magnitude}"
            )
        previous = current
        previous_changed = plan.changed


def schema_variants(
    schema_def: dict,
    *,
    corpus: str,
    document_id: str,
    design_seed: str,
    levels: Sequence[float] = NOMINAL_LEVELS,
) -> list[MaskedVariant]:
    """Mask relation-description tokens while preserving schema structure."""
    occurrences: list[TokenOccurrence] = []
    base_by_id: dict[str, dict] = {}
    for relation in schema_def.get("relations", []):
        relation_id = str(relation.get("id") or "")
        base_by_id[relation_id] = relation
        if relation_id == "OTHER":
            continue
        for token_index, _ in enumerate(whitespace_tokens(relation.get("description", ""))):
            occurrences.append(TokenOccurrence(f"relation:{relation_id}", token_index))

    plans = [
        _plan(
            occurrences,
            q=q,
            design_seed=design_seed,
            corpus=corpus,
            document_id=document_id,
            family="schema",
        )
        for q in levels
    ]
    _validate_nested(plans)
    variants: list[MaskedVariant] = []
    for plan in plans:
        selected = set(plan.changed_keys)
        variant = copy.deepcopy(schema_def)
        for relation in variant.get("relations", []):
            relation_id = str(relation.get("id") or "")
            indices = {
                int(key.rsplit("::", 1)[1])
                for key in selected
                if key.startswith(f"relation:{relation_id}::")
            }
            if indices:
                relation["description"] = _mask_text(
                    relation.get("description", ""), indices
                )

        # The displayed schema identity and every structural field stay fixed.
        assert variant.get("id") == schema_def.get("id")
        assert variant.get("name") == schema_def.get("name")
        assert variant.get("description") == schema_def.get("description")
        assert [
            (r.get("id"), r.get("label")) for r in variant.get("relations", [])
        ] == [
            (r.get("id"), r.get("label")) for r in schema_def.get("relations", [])
        ]
        assert next(
            (r for r in variant.get("relations", []) if r.get("id") == "OTHER"),
            None,
        ) == next(
            (r for r in schema_def.get("relations", []) if r.get("id") == "OTHER"),
            None,
        )
        variants.append(MaskedVariant(variant, plan))
    return variants


def prompt_variants(
    prompt_def: dict,
    *,
    corpus: str,
    document_id: str,
    design_seed: str,
    levels: Sequence[float] = NOMINAL_LEVELS,
) -> list[MaskedVariant]:
    """Mask C1--C6 instruction tokens while preserving C7 and the scaffold."""
    occurrences: list[TokenOccurrence] = []
    for clause in prompt_def.get("clauses", []):
        clause_id = str(clause.get("id") or "")
        if clause_id not in PROMPT_TASK_CLAUSES:
            continue
        for token_index, _ in enumerate(whitespace_tokens(clause.get("text", ""))):
            occurrences.append(TokenOccurrence(f"clause:{clause_id}", token_index))

    plans = [
        _plan(
            occurrences,
            q=q,
            design_seed=design_seed,
            corpus=corpus,
            document_id=document_id,
            family="prompt",
        )
        for q in levels
    ]
    _validate_nested(plans)
    variants: list[MaskedVariant] = []
    for plan in plans:
        selected = set(plan.changed_keys)
        variant = copy.deepcopy(prompt_def)
        for clause in variant.get("clauses", []):
            clause_id = str(clause.get("id") or "")
            indices = {
                int(key.rsplit("::", 1)[1])
                for key in selected
                if key.startswith(f"clause:{clause_id}::")
            }
            if indices:
                clause["text"] = _mask_text(clause.get("text", ""), indices)

        assert variant.get("id") == prompt_def.get("id")
        assert variant.get("template") == prompt_def.get("template")
        base_non_task = {
            c.get("id"): c for c in prompt_def.get("clauses", [])
            if c.get("id") not in PROMPT_TASK_CLAUSES
        }
        variant_non_task = {
            c.get("id"): c for c in variant.get("clauses", [])
            if c.get("id") not in PROMPT_TASK_CLAUSES
        }
        assert variant_non_task == base_non_task
        variants.append(MaskedVariant(variant, plan))
    return variants


def evidence_variants(
    sentences: Sequence[dict],
    *,
    corpus: str,
    document_id: str,
    design_seed: str,
    levels: Sequence[float] = NOMINAL_LEVELS,
) -> list[MaskedVariant]:
    """Mask sentence-text tokens while preserving sentence identity and order."""
    occurrences: list[TokenOccurrence] = []
    for sentence in sentences:
        sentence_id = str(sentence.get("sentence_id") or "")
        for token_index, _ in enumerate(whitespace_tokens(sentence.get("text", ""))):
            occurrences.append(TokenOccurrence(f"sentence:{sentence_id}", token_index))

    plans = [
        _plan(
            occurrences,
            q=q,
            design_seed=design_seed,
            corpus=corpus,
            document_id=document_id,
            family="evidence",
        )
        for q in levels
    ]
    _validate_nested(plans)
    variants: list[MaskedVariant] = []
    base_structure = [
        (s.get("sentence_id"), s.get("sentence_index"), s.get("document_id"))
        for s in sentences
    ]
    for plan in plans:
        selected = set(plan.changed_keys)
        variant = copy.deepcopy(list(sentences))
        for sentence in variant:
            sentence_id = str(sentence.get("sentence_id") or "")
            indices = {
                int(key.rsplit("::", 1)[1])
                for key in selected
                if key.startswith(f"sentence:{sentence_id}::")
            }
            if indices:
                sentence["text"] = _mask_text(sentence.get("text", ""), indices)
        assert [
            (s.get("sentence_id"), s.get("sentence_index"), s.get("document_id"))
            for s in variant
        ] == base_structure
        variants.append(MaskedVariant(variant, plan))
    return variants


def edge_dicts(edges: Iterable[Any]) -> list[dict]:
    """Convert normalized edge dataclasses or mappings to metric-ready dicts."""
    out: list[dict] = []
    for edge in edges:
        if isinstance(edge, dict):
            out.append(dict(edge))
        else:
            out.append(dict(vars(edge)))
    return out
