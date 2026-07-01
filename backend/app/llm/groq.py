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
# Bounded, fail-fast retries. This runs INSIDE a user request, so the worst case must
# be a few seconds, not minutes. A short per-minute (TPM) blip is worth one quick retry;
# a daily (TPD) cap or a multi-second "try again in …" hint is not — we surface it
# immediately and let the classifier degrade the batch to UNCLASSIFIED.
MAX_RETRIES = 2
BASE_BACKOFF = 1.5
BACKOFF_CAP = 6.0
# If Groq asks us to wait longer than this, retrying inside the request is pointless.
MAX_WAIT_HINT = 5.0


def _retry_hint(err: Exception) -> float | None:
    """Seconds Groq suggests waiting, parsed from either a `retry-after` field or its
    human phrasing ("Please try again in 4m43.392s" / "in 6.5s"). None if absent."""
    text = str(err)
    m = re.search(r"retry.?after['\"]?\s*[:=]\s*['\"]?(\d+(?:\.\d+)?)", text, re.IGNORECASE)
    if m:
        return float(m.group(1))
    m = re.search(r"try again in\s+(?:(\d+)m)?\s*(\d+(?:\.\d+)?)s", text, re.IGNORECASE)
    if m:
        minutes = float(m.group(1)) if m.group(1) else 0.0
        return minutes * 60 + float(m.group(2))
    return None


def _is_daily_cap(err: Exception) -> bool:
    """A per-DAY token/request cap won't clear within a request — don't retry it."""
    return bool(re.search(r"per day|\bTPD\b|\bRPD\b", str(err), re.IGNORECASE))


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
                hint = _retry_hint(e)
                # Fail fast when waiting can't help within a request: a daily cap, a
                # long suggested wait, a non-transient error, or the last attempt.
                if (
                    not transient
                    or _is_daily_cap(e)
                    or (hint is not None and hint > MAX_WAIT_HINT)
                    or attempt == MAX_RETRIES - 1
                ):
                    raise
                await asyncio.sleep(min(hint or backoff, BACKOFF_CAP))
                backoff = min(backoff * 2, BACKOFF_CAP)
            except groq.APIConnectionError:
                if attempt == MAX_RETRIES - 1:
                    raise
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, BACKOFF_CAP)
