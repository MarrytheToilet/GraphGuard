"""OpenAI-compatible client.

Reads OPENAI_API_KEY / OPENAI_BASE_URL / OPENAI_MODEL from env unless overridden.
JSON mode is requested via response_format={"type": "json_object"} and tolerates
servers that don't support it (falls back gracefully).
"""
from __future__ import annotations

import itertools
import logging
import os
import threading
import time
from typing import List, Optional

from openai import OpenAI

from .client import LLMResponse

logger = logging.getLogger(__name__)


def _load_keys() -> List[str]:
    multi = os.environ.get("OPENAI_API_KEYS", "").strip()
    keys: List[str] = []
    if multi:
        keys.extend([k.strip() for k in multi.split(",") if k.strip()])
    single = os.environ.get("OPENAI_API_KEY", "").strip()
    if single and single not in keys:
        keys.insert(0, single)
    return keys


class OpenAICompatClient:
    """OpenAI-compatible client with round-robin multi-key load balancing.

    On 429/5xx/timeouts it rotates to the next key and retries up to N keys * 2 attempts.
    """

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None,
                 model: Optional[str] = None, timeout: float = 120.0,
                 json_mode: bool = True, max_attempts: Optional[int] = None):
        if api_key:
            self.keys = [api_key]
        else:
            self.keys = _load_keys()
        if not self.keys:
            raise RuntimeError("OPENAI_API_KEY(S) is not set")
        self.base_url = base_url or os.environ.get("OPENAI_BASE_URL")
        self.model_id = model or os.environ.get("OPENAI_MODEL") or "gpt-4o-mini"
        self.json_mode = json_mode
        self.timeout = timeout
        self.max_attempts = max_attempts or max(2 * len(self.keys), 4)
        self._rr_lock = threading.Lock()
        self._rr = itertools.cycle(range(len(self.keys)))
        # build clients lazily
        self._clients = [None] * len(self.keys)

    @property
    def api_key(self) -> str:
        return self.keys[0]

    def _get_client(self, idx: int) -> OpenAI:
        if self._clients[idx] is None:
            kw = {"api_key": self.keys[idx], "timeout": self.timeout}
            if self.base_url:
                kw["base_url"] = self.base_url
            self._clients[idx] = OpenAI(**kw)
        return self._clients[idx]

    def _next_idx(self) -> int:
        with self._rr_lock:
            return next(self._rr)

    def complete_json(self, prompt: str, *, temperature: float = 0.0,
                      max_tokens: int = 2048, seed: Optional[int] = None) -> LLMResponse:
        last_err: Optional[Exception] = None
        for attempt in range(self.max_attempts):
            idx = self._next_idx()
            client = self._get_client(idx)
            t0 = time.time()
            kwargs = dict(
                model=self.model_id,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a strict JSON generator. Return exactly one "
                            "valid JSON object and no markdown, prose, code fences, "
                            "advertisements, or non-JSON text."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
            )
            if seed is not None:
                kwargs["seed"] = seed
            if self.json_mode:
                kwargs["response_format"] = {"type": "json_object"}
            # DashScope (Bailian) Qwen "thinking" models reject non-streaming
            # calls unless we explicitly disable thinking mode.
            mid_lower = (self.model_id or "").lower()
            if mid_lower.startswith("qwen") or "qwen3" in mid_lower:
                kwargs["extra_body"] = {"enable_thinking": False}
            try:
                resp = client.chat.completions.create(**kwargs)
            except Exception as e:
                msg = str(e)
                if self.json_mode and "response_format" in msg:
                    kwargs.pop("response_format", None)
                    try:
                        resp = client.chat.completions.create(**kwargs)
                    except Exception as e2:
                        last_err = e2
                        logger.warning("LLM key #%d failed (%s); rotating", idx, e2.__class__.__name__)
                        time.sleep(min(2 ** attempt, 10))
                        continue
                else:
                    last_err = e
                    logger.warning("LLM key #%d failed (%s: %s); rotating",
                                   idx, e.__class__.__name__, msg[:120])
                    time.sleep(min(2 ** attempt, 10))
                    continue
            elapsed = int((time.time() - t0) * 1000)
            choice = resp.choices[0]
            text = choice.message.content or ""
            usage = getattr(resp, "usage", None)
            return LLMResponse(
                text=text,
                model=self.model_id,
                prompt_tokens=getattr(usage, "prompt_tokens", None) if usage else None,
                completion_tokens=getattr(usage, "completion_tokens", None) if usage else None,
                latency_ms=elapsed,
                raw={"finish_reason": getattr(choice, "finish_reason", None)},
            )
        raise RuntimeError(f"All LLM attempts failed after {self.max_attempts} tries: {last_err}")
