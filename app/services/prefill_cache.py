"""
Prefill Cache — เก็บ raw input ชั่วคราวสำหรับ ML→Q&A handoff

ดู CLAUDE.md Section 4.7 (ML → Q&A Handoff)
- โอนแค่ raw input เท่านั้น (ไม่โอน evidence bundle) — กัน Mode Isolation
- TTL 5 นาที (configurable)
- Default backend = in-memory dict, สามารถ swap เป็น Redis ได้ถ้า scale

API:
    token = store_input("ข้อความที่ user พิมพ์")
    text = retrieve_input(token)  # คืน None ถ้าหมดอายุ/ไม่เจอ
"""

from __future__ import annotations

import secrets
import threading
import time
from dataclasses import dataclass


DEFAULT_TTL_SECONDS = 300  # 5 นาที


@dataclass
class _CacheEntry:
    value: str
    expires_at: float


class _InMemoryStore:
    """thread-safe in-memory cache พร้อม TTL"""

    def __init__(self) -> None:
        self._data: dict[str, _CacheEntry] = {}
        self._lock = threading.Lock()

    def set(self, key: str, value: str, ttl: int) -> None:
        with self._lock:
            self._data[key] = _CacheEntry(value=value, expires_at=time.time() + ttl)
            self._evict_expired_locked()

    def get(self, key: str) -> str | None:
        with self._lock:
            entry = self._data.get(key)
            if entry is None:
                return None
            if entry.expires_at < time.time():
                self._data.pop(key, None)
                return None
            return entry.value

    def delete(self, key: str) -> None:
        with self._lock:
            self._data.pop(key, None)

    def _evict_expired_locked(self) -> None:
        now = time.time()
        expired = [k for k, e in self._data.items() if e.expires_at < now]
        for k in expired:
            self._data.pop(k, None)


_store = _InMemoryStore()


def store_input(text: str, ttl: int = DEFAULT_TTL_SECONDS) -> str:
    """เก็บ raw input + return token ที่ใช้ retrieve กลับมา"""
    token = secrets.token_urlsafe(24)
    _store.set(token, text, ttl)
    return token


def retrieve_input(token: str) -> str | None:
    """ดึง raw input จาก token — คืน None ถ้าหมดอายุ/ไม่เจอ"""
    if not token:
        return None
    return _store.get(token)


def consume_input(token: str) -> str | None:
    """ดึง + ลบทันที (one-shot, ใช้ครั้งเดียว)"""
    value = _store.get(token)
    if value is not None:
        _store.delete(token)
    return value
