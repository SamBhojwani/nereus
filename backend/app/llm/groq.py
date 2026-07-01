"""
GroqClient: the fallback LLMClient, backed by Groq's free tier.

The brief plans Groq as the fallback behind the one LLMClient interface — this is that.
Groq's free tier is far more generous than Gemini's (far higher daily request budget),
which is exactly what you want when Gemini's daily quota is spent.

This is the ONLY file that imports the Groq SDK. Selecting it over Gemini is one env var
(LLM_PROVIDER=groq) — see app/llm/factory.py. Nothing downstream changes.
"""
from __future__ import annotations

import asyncio
import os
import re

import groq
from groq import AsyncGroq

from app.llm.base import LLMClient, LLMResponse

DEFAULT_MODEL = "llama-3.3-70b-versatile"
MAX_RETRIES = 5
BASE_BACKOFF = 8.0


def _retry_after(err: Exception) -> float | None:
    m = re.search(r"retry.?after['\"]?\s*[:=]\s*['\"]?(\d+(?:\.\d+)?)", str(err), re.IGNORECASE)
    return float(m.group(1)) if m else None


class GroqClient(LLMClient):
    def __init__(self, api_key: str | None = None, model: str | None = None):
        self._key = api_key or os.getenv("GROQ_API_KEY")
        self._model_name = model or os.getenv("GROQ_MODEL") or DEFAULT_MODEL
        self._client = AsyncGroq(api_key=self._key) if self._key else None

    def healthcheck(self) -> bool:
        return bool(self._key)

    async def complete(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 512,
    ) -> LLMResponse:
        if self._client is None:
            raise RuntimeError("GROQ_API_KEY is not set")

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        backoff = BASE_BACKOFF
        for attempt in range(MAX_RETRIES):
            try:
                resp = await self._client.chat.completions.create(
                    model=self._model_name,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                text = (resp.choices[0].message.content or "").strip()
                return LLMResponse(text=text, model=self._model_name)
            except groq.APIStatusError as e:
                code = getattr(e, "status_code", None)
                transient = code == 429 or (isinstance(code, int) and code >= 500)
                if not transient or attempt == MAX_RETRIES - 1:
                    raise
                await asyncio.sleep(_retry_after(e) or backoff)
                backoff = min(backoff * 2, 60.0)
            except groq.APIConnectionError:
                if attempt == MAX_RETRIES - 1:
                    raise
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 60.0)
