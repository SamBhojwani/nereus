"""The retry policy that fixed the 10-minute hang: never sit and retry a limit that
won't clear within the request (a daily cap, or a multi-second 'try again' hint)."""
from __future__ import annotations

import httpx
import groq
import pytest

from app.llm.groq import GroqClient, _retry_hint, _is_daily_cap


def _api_error(message: str, status: int = 429) -> groq.APIStatusError:
    req = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    resp = httpx.Response(status, request=req)
    return groq.APIStatusError(message, response=resp, body=None)


def test_retry_hint_parses_minutes_and_seconds():
    assert _retry_hint(Exception("Please try again in 4m43.392s")) == pytest.approx(283.392)
    assert _retry_hint(Exception("try again in 6.5s")) == pytest.approx(6.5)


def test_retry_hint_absent_returns_none():
    assert _retry_hint(Exception("some other error")) is None


def test_daily_cap_detected():
    assert _is_daily_cap(Exception("... on tokens per day (TPD): Limit 100000")) is True
    assert _is_daily_cap(Exception("... tokens per minute (TPM) ...")) is False


async def test_daily_cap_fails_fast_without_retrying():
    gc = GroqClient(api_key="test-key", model="llama-3.1-8b-instant")
    err = _api_error("Rate limit reached ... on tokens per day (TPD): Limit 100000, "
                     "Used 99999. Please try again in 4m43s.")

    calls = 0
    async def fake_create(**kwargs):
        nonlocal calls
        calls += 1
        raise err
    gc._client.chat.completions.create = fake_create

    with pytest.raises(groq.APIStatusError):
        await gc.complete("hi")
    assert calls == 1  # a daily cap must NOT be retried inside a request
