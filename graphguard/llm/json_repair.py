"""Best-effort JSON parsing for LLM outputs.

LLMs in JSON mode usually return clean JSON; when not, we strip code fences,
trim leading/trailing text, and try to locate the outermost {...} block.
"""
from __future__ import annotations

import json
import re
from typing import Any

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)


def _strip_fences(text: str) -> str:
    m = _FENCE_RE.search(text)
    return m.group(1) if m else text


def _slice_outermost(text: str) -> str:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        return text
    return text[start:end + 1]


def parse_json_lenient(text: str) -> Any:
    """Try direct parse, then a couple of cheap repairs. Raises ValueError on failure."""
    if text is None:
        raise ValueError("empty response")
    text = text.strip()
    for candidate in (text, _strip_fences(text), _slice_outermost(_strip_fences(text))):
        try:
            return json.loads(candidate)
        except Exception:
            continue
    # last resort: drop trailing commas
    cleaned = re.sub(r",(\s*[}\]])", r"\1", _slice_outermost(_strip_fences(text)))
    return json.loads(cleaned)
