"""
Tests for Enterprise Rate Limiter and Quota Headers.
"""

import os
import sys
import pytest

_src = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if _src not in sys.path:
    sys.path.insert(0, _src)

from core.security import RateLimiter


def test_rate_limiter_allows_under_quota():
    limiter = RateLimiter(max_requests=5, window_seconds=10)
    for _ in range(5):
        allowed, retry = limiter.is_allowed("192.168.1.100")
        assert allowed is True
        assert retry == 0

    assert limiter.get_remaining("192.168.1.100") == 0


def test_rate_limiter_blocks_over_quota():
    limiter = RateLimiter(max_requests=3, window_seconds=10)
    for _ in range(3):
        limiter.is_allowed("10.0.0.1")

    allowed, retry_after = limiter.is_allowed("10.0.0.1")
    assert allowed is False
    assert retry_after > 0


def test_rate_limiter_reset():
    limiter = RateLimiter(max_requests=2, window_seconds=10)
    limiter.is_allowed("10.0.0.2")
    limiter.is_allowed("10.0.0.2")
    assert limiter.get_remaining("10.0.0.2") == 0

    limiter.reset_client("10.0.0.2")
    assert limiter.get_remaining("10.0.0.2") == 2
