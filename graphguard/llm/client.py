"""Abstract LLM client interface."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol


@dataclass
class LLMResponse:
    text: str
    model: str
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    latency_ms: Optional[int] = None
    raw: Optional[dict] = None


class LLMClient(Protocol):
    model_id: str

    def complete_json(self, prompt: str, *, temperature: float = 0.0,
                      max_tokens: int = 2048, seed: Optional[int] = None) -> LLMResponse: ...
