"""
GeminiClient: the concrete LLMClient backed by Google Gemini (AI Studio free tier).

This is the ONLY file that imports the Gemini SDK. Everything else in Nereus talks
to the LLMClient interface, so swapping Gemini -> Groq -> a paid model later is a new
sibling file + one line in main.py, with nothing else touched.

The model name is read from GEMINI_MODEL (default below) rather than hardcoded, because
free-tier models get rotated/retired — see BUILD_BRIEF "free-tier landmines". For the
same reason we use the supported `google-genai` SDK, not the deprecated
`google-generativeai` one.
"""
from __future__ import annotations

import os

from google import genai
from google.genai import types

from app.llm.base import LLMClient, LLMResponse

DEFAULT_MODEL = "gemini-2.5-flash"


class GeminiClient(LLMClient):
    def __init__(self, api_key: str | None = None, model: str | None = None):
        self._key = api_key or os.getenv("GEMINI_API_KEY")
        self._model_name = model or os.getenv("GEMINI_MODEL") or DEFAULT_MODEL
        # Client is cheap to hold; only build it if we actually have a key.
        self._client = genai.Client(api_key=self._key) if self._key else None

    def healthcheck(self) -> bool:
        """Cheap 'is a key present?' check — no network call."""
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
            raise RuntimeError("GEMINI_API_KEY is not set")

        resp = await self._client.aio.models.generate_content(
            model=self._model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system,
                temperature=temperature,
                max_output_tokens=max_tokens,
                # Gemini 2.5 models "think" before answering, and thinking tokens count
                # against max_output_tokens — a small budget gets fully consumed by
                # thinking and returns EMPTY text. Classification needs no chain-of-thought,
                # so disable it: fixes the empty-output failure AND saves quota.
                thinking_config=types.ThinkingConfig(thinking_budget=0),
            ),
        )
        return LLMResponse(text=(resp.text or "").strip(), model=self._model_name)
