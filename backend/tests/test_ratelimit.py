"""Per-IP sliding-window limiter."""
from __future__ import annotations

import time

from app.ratelimit import SlidingWindowLimiter


def test_allows_up_to_limit_then_blocks():
    lim = SlidingWindowLimiter(max_requests=3, window_seconds=60)
    assert [lim.check("ip")[0] for _ in range(3)] == [True, True, True]
    allowed, retry_after = lim.check("ip")
    assert allowed is False
    assert 0 < retry_after <= 60


def test_separate_ips_have_separate_budgets():
    lim = SlidingWindowLimiter(max_requests=1, window_seconds=60)
    assert lim.check("a")[0] is True
    assert lim.check("a")[0] is False
    assert lim.check("b")[0] is True  # b is unaffected by a


def test_window_frees_up_after_expiry():
    lim = SlidingWindowLimiter(max_requests=1, window_seconds=0.05)
    assert lim.check("ip")[0] is True
    assert lim.check("ip")[0] is False
    time.sleep(0.06)
    assert lim.check("ip")[0] is True  # old hit aged out of the window
