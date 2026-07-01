"""
make_llm(): the single place that chooses which LLMClient to construct.

Swapping the model provider is now one env var — LLM_PROVIDER=gemini|groq — with no
change to the classifier, the endpoints, or the eval harness. This is the LLMClient
socket from the brief, made concrete.
"""
from __future__ import annotations

import os

from app.llm.base import LLMClient

DEFAULT_PROVIDER = "gemini"


def make_llm(provider: str | None = None) -> LLMClient:
    name = (provider or os.getenv("LLM_PROVIDER") or DEFAULT_PROVIDER).strip().lower()
    if name == "gemini":
        from app.llm.gemini import GeminiClient
        return GeminiClient()
    if name == "groq":
        from app.llm.groq import GroqClient
        return GroqClient()
    raise ValueError(f"Unknown LLM_PROVIDER {name!r} (expected 'gemini' or 'groq')")
