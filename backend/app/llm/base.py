"""
LLMClient: the single seam between your app and whatever model is doing the reasoning.

Everything that needs an LLM (the classifier now; synthesis/dedup later) calls THIS,
never the Gemini or Groq SDK directly. So switching Gemini -> Groq -> a paid model
is one new subclass + one config line, and nothing else in the codebase changes.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class LLMResponse:
    text: str
    model: str
    # room to grow: token counts, latency, finish_reason, etc.


class LLMClient(ABC):
    @abstractmethod
    async def complete(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.0,   # default 0: classification wants determinism
        max_tokens: int = 512,
    ) -> LLMResponse:
        """Send a prompt, get text back. Implementations handle auth + retries."""
        ...
