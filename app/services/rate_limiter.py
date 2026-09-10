"""
In-memory sliding-window rate limiter — shared service, ไม่มี decision logic ของ domain

ใช้กับ endpoint ที่มี external API cost (POST /api/qa/chat) — ดู CLAUDE.md changelog 2026-09-10
Tech stack ระบุ redis เป็น optional โดยมี in-memory fallback (Section 11) — pilot ใช้ fallback นี้
ข้อจำกัด: state อยู่ใน process เดียว (uvicorn 1 worker) — พอสำหรับ closed pilot
"""

from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass

MINUTE = 60
DAY = 86400


@dataclass
class RateLimitDecision:
    allowed: bool
    retry_after_seconds: int = 0
    reason: str = ""  # "per_minute" | "per_day" | ""


class SlidingWindowRateLimiter:
    """นับ request ต่อ key (เช่น client IP) ใน window 60 วิ และ 24 ชม."""

    def __init__(self, per_minute: int, per_day: int, clock=time.monotonic):
        self.per_minute = per_minute
        self.per_day = per_day
        self._clock = clock
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def check_and_record(self, key: str) -> RateLimitDecision:
        now = self._clock()
        with self._lock:
            q = self._hits.setdefault(key, deque())
            while q and now - q[0] > DAY:
                q.popleft()

            if len(q) >= self.per_day:
                retry = int(DAY - (now - q[0])) + 1
                return RateLimitDecision(False, retry, "per_day")

            in_last_minute = sum(1 for t in q if now - t <= MINUTE)
            if in_last_minute >= self.per_minute:
                oldest_in_minute = next(t for t in q if now - t <= MINUTE)
                retry = int(MINUTE - (now - oldest_in_minute)) + 1
                return RateLimitDecision(False, retry, "per_minute")

            q.append(now)
            self._prune_stale_keys(now)
            return RateLimitDecision(True)

    def _prune_stale_keys(self, now: float) -> None:
        # กัน memory โตจาก IP ที่ไม่กลับมาแล้ว — เช็คแบบหยาบพอ (pilot scale)
        if len(self._hits) > 1000:
            for k in [k for k, q in self._hits.items() if not q or now - q[-1] > DAY]:
                del self._hits[k]
