"""Tests สำหรับ app/services/rate_limiter.py — sliding window ต่อ key"""

from app.services.rate_limiter import SlidingWindowRateLimiter


class FakeClock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t

    def advance(self, seconds):
        self.t += seconds


def make(per_minute=3, per_day=10):
    clock = FakeClock()
    return SlidingWindowRateLimiter(per_minute, per_day, clock=clock), clock


def test_allows_under_limit():
    limiter, _ = make()
    for _ in range(3):
        assert limiter.check_and_record("ip1").allowed


def test_blocks_over_per_minute_and_reports_retry_after():
    limiter, clock = make(per_minute=3)
    for _ in range(3):
        limiter.check_and_record("ip1")
    decision = limiter.check_and_record("ip1")
    assert not decision.allowed
    assert decision.reason == "per_minute"
    assert 0 < decision.retry_after_seconds <= 61


def test_minute_window_slides():
    limiter, clock = make(per_minute=3)
    for _ in range(3):
        limiter.check_and_record("ip1")
    clock.advance(61)
    assert limiter.check_and_record("ip1").allowed


def test_per_day_cap():
    limiter, clock = make(per_minute=100, per_day=5)
    for _ in range(5):
        assert limiter.check_and_record("ip1").allowed
    decision = limiter.check_and_record("ip1")
    assert not decision.allowed
    assert decision.reason == "per_day"
    # ผ่านไป 1 วัน → ใช้ได้อีก
    clock.advance(86401)
    assert limiter.check_and_record("ip1").allowed


def test_keys_are_isolated():
    limiter, _ = make(per_minute=1)
    assert limiter.check_and_record("ip1").allowed
    assert not limiter.check_and_record("ip1").allowed
    assert limiter.check_and_record("ip2").allowed
