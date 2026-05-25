"""SQLite-backed cache for LLM JSON completions.

Wraps any LLMClient. Key = sha256(model || temperature || seed || prompt).
Cached responses are stored as JSON envelopes including the raw text and token
usage so re-replay is bit-identical from the consumer's perspective.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import asdict
from typing import Optional

from .client import LLMClient, LLMResponse


def _key(model: str, temperature: float, seed, prompt: str) -> str:
    h = hashlib.sha256()
    h.update(f"m={model}|t={temperature}|s={seed}\n".encode())
    h.update(prompt.encode("utf-8"))
    return h.hexdigest()


class CachedLLMClient:
    """Decorator: same interface as LLMClient, with read-through SQLite cache."""

    def __init__(self, inner: LLMClient, conn: sqlite3.Connection):
        self.inner = inner
        self.conn = conn
        self.model_id = inner.model_id
        self.hits = 0
        self.misses = 0

    def complete_json(self, prompt: str, *, temperature: float = 0.0,
                      max_tokens: int = 2048, seed: Optional[int] = None) -> LLMResponse:
        key = _key(self.model_id, temperature, seed, prompt)
        row = self.conn.execute(
            "SELECT response FROM llm_call_cache WHERE cache_key = ?", (key,)
        ).fetchone()
        if row is not None:
            self.hits += 1
            data = json.loads(row[0])
            return LLMResponse(
                text=data["text"], model=data.get("model", self.model_id),
                prompt_tokens=data.get("prompt_tokens"),
                completion_tokens=data.get("completion_tokens"),
                latency_ms=data.get("latency_ms"),
            )
        self.misses += 1
        resp = self.inner.complete_json(prompt, temperature=temperature,
                                        max_tokens=max_tokens, seed=seed)
        envelope = {
            "text": resp.text, "model": resp.model,
            "prompt_tokens": resp.prompt_tokens,
            "completion_tokens": resp.completion_tokens,
            "latency_ms": resp.latency_ms,
        }
        self.conn.execute(
            "INSERT OR REPLACE INTO llm_call_cache(cache_key, response, created_at) "
            "VALUES (?, ?, datetime('now'))",
            (key, json.dumps(envelope, ensure_ascii=False)),
        )
        self.conn.commit()
        return resp
