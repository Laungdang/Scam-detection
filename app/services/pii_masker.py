"""
PII Masker — PDPA compliance layer

ดู CLAUDE.md Section 2.8 (PII Minimization) และ Section 6.7 สำหรับ design rationale

Mask policy ต่อ field type:
- thai_id    strict: x-xxxx-xxxxx-xx-x   display: เหมือน strict
- bank_acct  strict: xxx-x-xx{last4}      display: เหมือน strict
- phone      strict: xxx-xxx-{last4}      display: {first3}-xxx-{last4}
- person     strict: {first1}***          display: {first1}***
- url        strict: {scheme}://{host}/...  display: เหมือน strict

ทุก function ต้อง pure (ไม่ side effect, ไม่ I/O, ไม่ log)
"""

import hashlib
import re
from dataclasses import dataclass, field
from typing import Literal
from urllib.parse import urlparse

from app.config.settings import Settings


PIIType = Literal["thai_id", "bank_acct", "phone", "person", "url"]
MaskMode = Literal["strict", "display"]


@dataclass(frozen=True)
class PIIMatch:
    """ตำแหน่งและประเภท PII ที่เจอใน text (สำหรับ audit log)"""
    pii_type: PIIType
    start: int
    end: int
    original: str
    masked: str


@dataclass
class MaskedResult:
    masked: str
    pii_hash: str
    pii_found: list[PIIMatch] = field(default_factory=list)


# ─────────────────────────────────────────────────────────────────
# Pattern definitions
# ─────────────────────────────────────────────────────────────────

_URL_RE = re.compile(
    r"https?://[^\s฀-๿]+",
    flags=re.IGNORECASE,
)

_PHONE_RE = re.compile(
    r"(?<!\d)(?:\+66|0)\d{8,9}(?!\d)"
)

# 13-digit Thai ID — อาจมี hyphens ภายใน
_THAI_ID_RE = re.compile(
    r"(?<!\d)\d(?:[- ]?\d){12}(?!\d)"
)

# Bank account = ตัวเลข 9-15 หลักต่อกัน (ไม่ใช่ phone หรือ ID)
_BANK_RE = re.compile(
    r"(?<!\d)\d{9,15}(?!\d)"
)


def _is_valid_thai_id(digits: str) -> bool:
    """ตรวจ checksum เลขบัตรประชาชนไทยด้วย Mod 11 — ลด false positive"""
    if len(digits) != 13 or not digits.isdigit():
        return False
    total = sum(int(digits[i]) * (13 - i) for i in range(12))
    check = (11 - total % 11) % 10
    return check == int(digits[12])


# ─────────────────────────────────────────────────────────────────
# Field-level masking (รู้ประเภทล่วงหน้า)
# ─────────────────────────────────────────────────────────────────

def mask_field(value: str, field_type: PIIType, mode: MaskMode = "strict") -> str:
    """มาส์กค่าเดี่ยวที่รู้ประเภทล่วงหน้าแล้ว (จาก form input ที่แยก type)"""
    if not value:
        return ""

    if field_type == "thai_id":
        digits = re.sub(r"\D", "", value)
        if len(digits) != 13:
            return _generic_mask(value)
        return f"{digits[0]}-xxxx-xxxxx-xx-{digits[-1]}"

    if field_type == "bank_acct":
        digits = re.sub(r"\D", "", value)
        if len(digits) < 4:
            return _generic_mask(value)
        last4 = digits[-4:]
        return f"xxx-x-xx{last4}"

    if field_type == "phone":
        digits = re.sub(r"\D", "", value)
        if len(digits) < 4:
            return _generic_mask(value)
        last4 = digits[-4:]
        if mode == "display" and len(digits) >= 7:
            first3 = digits[:3]
            return f"{first3}-xxx-{last4}"
        return f"xxx-xxx-{last4}"

    if field_type == "person":
        # รองรับทั้งไทย/อังกฤษ, แยก first / last ด้วย whitespace
        parts = value.strip().split()
        masked_parts = []
        for p in parts:
            if len(p) == 0:
                continue
            masked_parts.append(f"{p[0]}***")
        return " ".join(masked_parts) if masked_parts else "***"

    if field_type == "url":
        return _mask_url(value)

    return _generic_mask(value)


def _mask_url(value: str) -> str:
    try:
        parsed = urlparse(value.strip())
        if not parsed.scheme or not parsed.netloc:
            return _generic_mask(value)
        return f"{parsed.scheme}://{parsed.netloc}/..."
    except Exception:
        return _generic_mask(value)


def _generic_mask(value: str) -> str:
    """fallback สำหรับค่าที่มาส์กตาม policy ไม่ได้"""
    if len(value) <= 2:
        return "*" * len(value)
    return value[0] + "*" * (len(value) - 2) + value[-1]


# ─────────────────────────────────────────────────────────────────
# Text-level masking (detect + mask PII ที่ฝังในข้อความ)
# ─────────────────────────────────────────────────────────────────

def find_pii_in_text(text: str) -> list[PIIMatch]:
    """detect PII patterns ใน free text — order: URL → phone → Thai ID → bank"""
    if not text:
        return []

    matches: list[PIIMatch] = []
    consumed: list[tuple[int, int]] = []

    def _overlaps(s: int, e: int) -> bool:
        return any(not (e <= cs or s >= ce) for cs, ce in consumed)

    def _add(pii_type: PIIType, m: re.Match, masked: str) -> None:
        s, e = m.span()
        if _overlaps(s, e):
            return
        consumed.append((s, e))
        matches.append(PIIMatch(pii_type, s, e, m.group(), masked))

    for m in _URL_RE.finditer(text):
        _add("url", m, _mask_url(m.group()))

    for m in _PHONE_RE.finditer(text):
        _add("phone", m, mask_field(m.group(), "phone"))

    for m in _THAI_ID_RE.finditer(text):
        digits = re.sub(r"\D", "", m.group())
        if _is_valid_thai_id(digits):
            _add("thai_id", m, mask_field(digits, "thai_id"))

    for m in _BANK_RE.finditer(text):
        _add("bank_acct", m, mask_field(m.group(), "bank_acct"))

    matches.sort(key=lambda x: x.start)
    return matches


def mask_pii(text: str, mode: MaskMode = "strict") -> MaskedResult:
    """มาส์ก PII ทั้งหมดใน text — ใช้ก่อนส่ง Claude / log DB / แสดง UI"""
    if not text:
        return MaskedResult(masked="", pii_hash=hash_value(""), pii_found=[])

    pii_found = find_pii_in_text(text)
    if not pii_found:
        return MaskedResult(masked=text, pii_hash=hash_value(text), pii_found=[])

    # rebuild text โดย replace ตำแหน่ง PII จากท้ายมาหน้า (รักษา index)
    parts: list[str] = []
    cursor = 0
    for pii in pii_found:
        parts.append(text[cursor:pii.start])
        if mode == "display" and pii.pii_type == "phone":
            digits = re.sub(r"\D", "", pii.original)
            parts.append(mask_field(digits, "phone", "display"))
        else:
            parts.append(pii.masked)
        cursor = pii.end
    parts.append(text[cursor:])

    masked = "".join(parts)
    return MaskedResult(masked=masked, pii_hash=hash_value(text), pii_found=pii_found)


# ─────────────────────────────────────────────────────────────────
# Hash (สำหรับ dedup/analytics โดยไม่เก็บค่าจริง)
# ─────────────────────────────────────────────────────────────────

def hash_value(value: str) -> str:
    """SHA256(value + PII_SALT) — pure hash, ไม่มาส์ก"""
    salt = Settings.PII_SALT
    if not salt:
        raise RuntimeError(
            "PII_SALT ไม่ได้ตั้งค่าใน environment — PDPA compliance ต้องมี salt"
        )
    h = hashlib.sha256()
    h.update(salt.encode("utf-8"))
    h.update(value.encode("utf-8"))
    return h.hexdigest()
