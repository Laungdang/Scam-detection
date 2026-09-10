"""
Pattern Service — scan ข้อความหา "คำสัญญาณ" ตาม lexicon (data/lexicon/scam_lexicon.yaml)

หลักการ (CLAUDE.md Section 2.1, 5.2, 6.8):
- service นี้ **ไม่ตัดสิน** — คืนแค่ข้อเท็จจริงว่า "พบคำอะไร ในมิติไหน"
- ไม่มี status / severity / weight — ผู้ตัดสิน (Claude ใน Q&A, model ใน ML) ชั่งน้ำหนักเอง
- match แบบตัดคำ (PyThaiNLP newmm) ไม่ใช่ substring → "ด่วน" ไม่ match "รถด่วน"
- regex รายงานแค่ **ชื่อ** ไม่รายงานข้อความที่ match → ไม่มี PII หลุดออกจาก service นี้

Lexicon เป็นไฟล์ YAML ใน git (มี provenance ต่อคำ) ไม่ใช่ hardcode ใน Python (CLAUDE.md ข้อ 8)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import yaml
from pythainlp.tokenize import word_tokenize


DEFAULT_LEXICON_PATH = Path("data/lexicon/scam_lexicon.yaml")


@dataclass(frozen=True)
class LexiconTerm:
    term: str
    tokens: tuple[str, ...]  # tokenized + lowercased — ใช้ match


@dataclass(frozen=True)
class LexiconRegex:
    name: str
    pattern: re.Pattern


@dataclass(frozen=True)
class LexiconDimension:
    key: str
    label_th: str
    principle: str
    terms: tuple[LexiconTerm, ...]
    regexes: tuple[LexiconRegex, ...]
    caveat: str = ""  # ข้อควรระวังในการตีความมิตินี้ — พิมพ์กำกับใน evidence เมื่อพบ


@dataclass(frozen=True)
class Lexicon:
    version: str
    dimensions: tuple[LexiconDimension, ...]

    @property
    def dimension_keys(self) -> list[str]:
        return [d.key for d in self.dimensions]


@dataclass
class DimensionMatch:
    """ข้อเท็จจริงต่อ 1 มิติ — ไม่มี verdict"""

    dimension: str
    label_th: str
    principle: str
    terms_found: list[str] = field(default_factory=list)
    regex_hits: list[str] = field(default_factory=list)  # ชื่อ regex เท่านั้น
    caveat: str = ""

    @property
    def has_hits(self) -> bool:
        return bool(self.terms_found or self.regex_hits)


# ─────────────────────────────────────────────────────────────
# Tokenization
# ─────────────────────────────────────────────────────────────

_ELONGATION_RE = re.compile(r"([฀-๿])\1{2,}")


def collapse_elongation(text: str) -> str:
    """ยุบตัวอักษรไทยที่ซ้ำ ≥3 เป็น 1 ("นะะะ" → "นะ", "ด่วนนน" → "ด่วน") — เพิ่ม recall ของ lexicon
    (typo ซ้ำ 2 ตัวเช่น "โอนน" ไม่แตะ เพราะแยกจากคำจริงไม่ได้)"""
    return _ELONGATION_RE.sub(r"\1", text)


def tokenize(text: str) -> list[str]:
    """ตัดคำ + lowercase — ใช้ทั้งกับ text และ term เพื่อให้ match กันได้"""
    if not text:
        return []
    text = collapse_elongation(text)
    # วงเล็บ/เครื่องหมายคำพูดติดคำ ทำให้ newmm ตัด "(inbox" เป็น token เดียว → แยกออกก่อน
    text = re.sub(r"[()\[\]{}\"'“”‘’]", " ", text)
    return [t.strip().lower() for t in word_tokenize(text, engine="newmm", keep_whitespace=False) if t.strip()]


def _contains_subsequence(haystack: list[str], needle: tuple[str, ...]) -> bool:
    n = len(needle)
    if n == 0 or n > len(haystack):
        return False
    first = needle[0]
    for i in range(len(haystack) - n + 1):
        if haystack[i] == first and tuple(haystack[i : i + n]) == needle:
            return True
    return False


# ─────────────────────────────────────────────────────────────
# Lexicon loading
# ─────────────────────────────────────────────────────────────

@lru_cache(maxsize=4)
def load_lexicon(path: str | None = None) -> Lexicon:
    """โหลด + tokenize lexicon ครั้งเดียว (cache per path)"""
    lex_path = Path(path) if path else DEFAULT_LEXICON_PATH
    raw = yaml.safe_load(lex_path.read_text(encoding="utf-8"))

    dimensions: list[LexiconDimension] = []
    for d in raw.get("dimensions", []):
        terms = tuple(
            LexiconTerm(term=str(t["term"]), tokens=tuple(tokenize(str(t["term"]))))
            for t in d.get("terms", [])
            if str(t.get("term", "")).strip()
        )
        regexes = tuple(
            LexiconRegex(name=str(r["name"]), pattern=re.compile(str(r["pattern"]), re.IGNORECASE))
            for r in d.get("regex", []) or []
        )
        dimensions.append(
            LexiconDimension(
                key=str(d["key"]),
                label_th=str(d.get("label_th", d["key"])),
                principle=str(d.get("principle", "")),
                terms=terms,
                regexes=regexes,
                caveat=" ".join(str(d.get("caveat", "")).split()),
            )
        )
    return Lexicon(version=str(raw.get("version", "0")), dimensions=tuple(dimensions))


# ─────────────────────────────────────────────────────────────
# Scanning
# ─────────────────────────────────────────────────────────────

def scan_text(text: str, lexicon: Lexicon | None = None) -> list[DimensionMatch]:
    """คืน DimensionMatch ของทุกมิติ (รวมมิติที่ไม่พบ — เพื่อรายงาน "ไม่พบ" ได้)

    ลำดับตาม lexicon — caller filter `has_hits` เองถ้าต้องการเฉพาะที่พบ
    """
    lexicon = lexicon or load_lexicon()
    if not text or not text.strip():
        return [DimensionMatch(d.key, d.label_th, d.principle, caveat=d.caveat) for d in lexicon.dimensions]

    tokens = tokenize(text)
    results: list[DimensionMatch] = []
    for dim in lexicon.dimensions:
        found: list[str] = []
        for t in dim.terms:
            if _contains_subsequence(tokens, t.tokens):
                found.append(t.term)
        hits = [r.name for r in dim.regexes if r.pattern.search(text)]
        results.append(DimensionMatch(dim.key, dim.label_th, dim.principle, found, hits, caveat=dim.caveat))
    return results


def format_evidence(matches: list[DimensionMatch]) -> str:
    """แปลงเป็นข้อความหลักฐานดิบสำหรับ prompt / log — ไม่มีคำตัดสิน

    ตัวอย่าง:
        คำสัญญาณที่พบ (ข้อเท็จจริง ไม่ใช่คำตัดสิน — ข้อความปกติก็มีคำพวกนี้ได้):
        - เร่งให้รีบตัดสินใจ: "ด่วน"
        - ให้กดลิงก์/ติดตั้งแอป: "ลิงก์" + รูปแบบ: url, suspicious_tld
        ไม่พบ: ขอให้โอน/จ่ายเงิน, ขอข้อมูลส่วนตัว/รหัส, ...
    """
    found = [m for m in matches if m.has_hits]
    missing = [m for m in matches if not m.has_hits]
    lines: list[str] = []
    if found:
        lines.append("คำสัญญาณที่พบ (ข้อเท็จจริง ไม่ใช่คำตัดสิน — ข้อความปกติก็มีคำพวกนี้ได้):")
        for m in found:
            parts = []
            if m.terms_found:
                parts.append(", ".join(f'"{t}"' for t in m.terms_found))
            if m.regex_hits:
                parts.append("รูปแบบ: " + ", ".join(m.regex_hits))
            line = f"- {m.label_th}: " + " + ".join(parts)
            if m.dimension == "link_action" and m.terms_found and "url" not in m.regex_hits:
                # ข้อเท็จจริงสำคัญ (guideline v1.1 Q5): พูดถึงลิงก์แต่ไม่มี URL ให้ประเมินโดเมน
                line += " — พูดถึงลิงก์แต่ไม่พบ URL ในข้อความ (ประเมินโดเมน/shortener ไม่ได้)"
            if m.caveat:
                line += f" (หมายเหตุ: {m.caveat})"
            lines.append(line)
    else:
        lines.append("คำสัญญาณที่พบ: ไม่พบคำสัญญาณใดๆ ใน lexicon")
    if missing and found:
        lines.append("ไม่พบ: " + ", ".join(m.label_th for m in missing))
    # lexicon จับได้เฉพาะคำที่รู้จัก — "ไม่พบ" ≠ "ไม่มีการขอ" (บทเรียน kaggle_tu comparison: "inbox ได้" เคยไม่อยู่ใน lexicon)
    lines.append("(รายการนี้มาจากคำใน lexicon เท่านั้น — การขอที่ใช้คำอื่นอาจไม่ถูกจับ ให้อ่านข้อความเองประกอบ)")
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────
# Backward-compatible API (legacy callers: analysis_service, streamlit_app)
# ─────────────────────────────────────────────────────────────

def find_matching_patterns(db=None, text: str = "") -> list[dict]:  # noqa: ARG001 — db ไม่ใช้แล้ว (lexicon อยู่ใน YAML)
    """คืนรายการ term ที่พบ ในรูปแบบเดิม (pattern_name/keyword/description)

    pattern_name = label ของมิติ (ไม่ใช่การตีความ), keyword = คำที่พบจริง
    """
    if not text:
        return []
    matched: list[dict] = []
    for m in scan_text(text):
        for term in m.terms_found:
            matched.append({"pattern_name": m.label_th, "keyword": term, "description": m.principle})
        for name in m.regex_hits:
            matched.append({"pattern_name": m.label_th, "keyword": f"[{name}]", "description": m.principle})
    return matched


def extract_unique_pattern_names(matches: list[dict]) -> list[str]:
    unique_names: list[str] = []
    seen: set[str] = set()
    for item in matches:
        name = item.get("pattern_name")
        if name and name not in seen:
            seen.add(name)
            unique_names.append(name)
    return unique_names
