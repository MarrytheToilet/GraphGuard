"""Sentence-level text interventions.

Operates on a list of `Sentence`-like rows (sqlite Row or dict) and produces a
modified list. Sentence indices are preserved (so evidence ids still align):
- remove: drop the sentence; downstream renderer just won't include it
- mask:   replace text with [MASKED]
"""
from __future__ import annotations

from copy import copy as _copy
from typing import Iterable


class _S:
    """Lightweight mutable row wrapping sqlite Row or dict."""
    __slots__ = ("sentence_id", "document_id", "sentence_index", "text")

    def __init__(self, src):
        self.sentence_id = src["sentence_id"]
        self.document_id = src["document_id"]
        self.sentence_index = src["sentence_index"]
        self.text = src["text"]

    def __getitem__(self, k):
        return getattr(self, k)


def to_mutable(sentences: Iterable) -> list[_S]:
    return [_S(s) for s in sentences]


def remove_sentence(sentences: list[_S], target_sentence_id: str) -> list[_S]:
    return [s for s in sentences if s.sentence_id != target_sentence_id]


def mask_sentence(sentences: list[_S], target_sentence_id: str,
                  mask_token: str = "[MASKED]") -> list[_S]:
    out: list[_S] = []
    for s in sentences:
        if s.sentence_id == target_sentence_id:
            ns = _S({"sentence_id": s.sentence_id, "document_id": s.document_id,
                     "sentence_index": s.sentence_index, "text": mask_token})
            out.append(ns)
        else:
            out.append(s)
    return out


# ------------------- presentation-level evidence variants -------------------

def swap_paragraphs(sentences: list[_S], seed: int = 7) -> list[_S]:
    """Reverse the sentence order while preserving indices in the wrapped row.
    Pure presentation: same content, different ordering."""
    import random as _r
    rng = _r.Random(seed)
    arr = list(sentences)
    rng.shuffle(arr)
    out: list[_S] = []
    for new_pos, src in enumerate(arr):
        ns = _S({"sentence_id": src.sentence_id, "document_id": src.document_id,
                 "sentence_index": new_pos, "text": src.text})
        out.append(ns)
    return out


_ALIAS_TABLE: dict[str, str] = {
    "United States": "the U.S.",
    "United Kingdom": "the U.K.",
    "New York City": "NYC",
    "Los Angeles": "LA",
    "World War II": "WWII",
    "the United Nations": "the UN",
    "European Union": "EU",
    "Soviet Union": "USSR",
    "United Nations": "UN",
}


def entity_alias_rewrite(sentences: list[_S],
                         alias_table: dict[str, str] | None = None) -> list[_S]:
    """Rewrite well-known entity surface forms with their common aliases.
    Meaning-preserving in principle; tests the model's robustness to surface form."""
    table = alias_table or _ALIAS_TABLE
    out: list[_S] = []
    for s in sentences:
        text = s.text
        for canon, alias in table.items():
            text = text.replace(canon, alias)
        ns = _S({"sentence_id": s.sentence_id, "document_id": s.document_id,
                 "sentence_index": s.sentence_index, "text": text})
        out.append(ns)
    return out
