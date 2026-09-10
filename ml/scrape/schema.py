"""
Dataset schema สำหรับ scam corpus — **v2** (CLAUDE.md Section 10, 2026-08-29)

หลักการ v2: ทุก record ต้อง defend ได้
- `tier` บังคับ — บอกว่า record นี้ใช้ train/val/test/RAG ได้ไหม (10.2)
- `source` ต้องมี url + snapshot_hash หรือ consent_id (10.3)
- `annotation` เก็บ label ต่อ annotator + final (10.4)
- `review` สำหรับ tier C (synthetic) — pending_review = ยังไม่มีอยู่
- `pii` ยืนยันว่า text ผ่าน masker แล้ว

Backward compat: record v1 (ไม่มี tier) ถูก migrate ด้วย ml/scrape/migrate_v2.py
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal


Verdict = Literal["danger", "caution", "safe"]
ScamCategory = Literal[
    "financial_fraud",            # หลอกขอ/โอนเงิน
    "impersonation_authority",    # อ้างเป็นเจ้าหน้าที่/หน่วยงาน
    "phishing_link",              # ลิงก์ปลอม
    "romance_scam",               # หลอกความรัก
    "investment_scam",            # หลอกลงทุน
    "prize_scam",                 # หลอกว่าได้รางวัล
    "borrowing_scam",             # หลอกขอยืม
    "loan_offer",                 # เสนอเงินกู้
    "other",
]
CATEGORIES: tuple[str, ...] = (
    "financial_fraud", "impersonation_authority", "phishing_link", "romance_scam",
    "investment_scam", "prize_scam", "borrowing_scam", "loan_offer", "other",
)

ExtractionMethod = Literal[
    "verbatim_html",   # คัดมาตรง ๆ จาก HTML
    "verbatim_pdf",    # คัดมาจาก PDF text
    "verbatim_ocr",    # OCR จาก screenshot (ต้องมีคน verify)
    "ocr_image",       # (v1 alias ของ verbatim_ocr)
    "consent_form",    # ผู้ร่วมส่งผ่าน collection form (มี consent_id)
    "translated",      # แปลจากภาษาอื่น (tier B)
    "llm_generated",   # LLM สร้าง (tier C)
    "manual_entry",    # (v1) ผู้ค้นคว้าใส่เอง — ใน v1 ใช้กับทั้ง translated และ llm_generated
]

# ─────────────────────────────────────────────────────────────
# Tier system (CLAUDE.md 10.2)
# ─────────────────────────────────────────────────────────────

Tier = Literal["A", "S", "B", "C", "N"]
TIER_NAMES: dict[str, str] = {
    "A": "real_thai",      # scam ไทยจริง มี URL/consent
    "S": "safe_real",      # ข้อความไทยปกติจริง
    "B": "real_foreign",   # scam จริงภาษาอื่น แปลไทย
    "C": "synthetic",      # LLM generate
    "N": "narrative",      # เคสเล่าเรื่องจากข่าว (RAG only)
}
TIERS: tuple[str, ...] = tuple(TIER_NAMES)

# ใช้ที่ไหนได้บ้าง — single source of truth ให้ preprocess.py / setup_rag ใช้
TIER_ALLOWED_IN: dict[str, dict[str, bool]] = {
    #        train  val    test   rag
    "A": {"train": True,  "val": True,  "test": True,  "rag": True},
    "S": {"train": True,  "val": True,  "test": True,  "rag": True},
    "B": {"train": True,  "val": True,  "test": False, "rag": False},
    "C": {"train": True,  "val": False, "test": False, "rag": False},  # train เฉพาะ review.status == approved
    "N": {"train": False, "val": False, "test": False, "rag": True},
}

License = Literal["fair_use_academic", "CC0", "CC-BY-4.0", "consent_form", "synthetic"]


@dataclass
class SourceAttribution:
    """แหล่งที่มาของ record — tier A/S/N ต้องมี url (หรือ consent_id) ที่ตามได้"""
    name: str
    url: str | None
    scraped_at: str                       # ISO timestamp (v1 name; = retrieved_at)
    extraction_method: str
    published_date: str | None = None
    license_note: str | None = None
    license: str | None = None            # License literal
    snapshot_hash: str | None = None      # sha256 ของ HTML/screenshot ต้นทาง (data/raw/snapshots/{hash}.*)
    consent_id: str | None = None         # สำหรับ extraction_method=consent_form


@dataclass
class AnnotationLabel:
    annotator: str                        # "A1", "A2", "adjudicator", "llm:<model>", "source:<name>"
    verdict: str
    category: str | None
    confidence: int | None = None         # 1-5
    notes: str | None = None


@dataclass
class Annotation:
    labels: list[AnnotationLabel] = field(default_factory=list)
    final: dict | None = None             # {"verdict", "category", "resolved_by": agreement|adjudicator|source_weak_label}
    guideline_version: str | None = None  # None = ยังไม่ annotate ตาม v2 guideline


@dataclass
class Review:
    """สำหรับ tier C — pending_review ถือว่า record ยังไม่มีอยู่สำหรับ training"""
    status: str = "pending_review"        # pending_review | approved | rejected
    reviewer: str | None = None
    reviewed_at: str | None = None
    notes: str | None = None


@dataclass
class PiiInfo:
    masked: bool = False
    masker_version: str | None = None
    pii_found_count: int = 0


@dataclass
class ScamRecord:
    id: str
    text: str
    verdict: str
    category: str | None
    source: SourceAttribution
    tier: str = "C"                       # default ปลอดภัยที่สุด: ถ้าไม่รู้ที่มา = synthetic
    annotation: Annotation = field(default_factory=Annotation)
    review: Review | None = None          # เฉพาะ tier C
    pii: PiiInfo = field(default_factory=PiiInfo)
    annotator_notes: str | None = None    # (v1) free text

    def to_dict(self) -> dict:
        return asdict(self)


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def make_id(source_slug: str, text: str) -> str:
    """deterministic ID จาก source + content hash — กัน duplicate"""
    h = hashlib.sha1(text.encode("utf-8")).hexdigest()[:8]
    return f"{source_slug}-{h}"


def snapshot_hash(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def is_usable_for(record: dict, purpose: str) -> bool:
    """record นี้ใช้กับ purpose (train|val|test|rag) ได้ไหม ตาม tier + review"""
    tier = record.get("tier")
    if tier not in TIER_ALLOWED_IN:
        return False
    if not TIER_ALLOWED_IN[tier].get(purpose, False):
        return False
    if tier == "C":
        review = record.get("review") or {}
        return review.get("status") == "approved"
    return True


def validate_record(record: dict) -> list[str]:
    """คืนรายการปัญหา (ว่าง = ผ่าน) — ใช้ใน validate_corpus + append"""
    problems: list[str] = []
    rid = record.get("id", "?")
    for k in ("id", "text", "verdict", "source", "tier"):
        if k not in record:
            problems.append(f"{rid}: missing {k}")
    tier = record.get("tier")
    if tier not in TIERS:
        problems.append(f"{rid}: tier {tier!r} ไม่อยู่ใน {TIERS}")
    if record.get("verdict") not in ("danger", "caution", "safe"):
        problems.append(f"{rid}: verdict {record.get('verdict')!r} ไม่ถูกต้อง")
    if record.get("verdict") != "safe" and record.get("category") not in CATEGORIES:
        problems.append(f"{rid}: category {record.get('category')!r} ไม่ถูกต้องสำหรับ verdict≠safe")
    src = record.get("source") or {}
    if tier in ("A", "S", "N"):
        if not src.get("url") and not src.get("consent_id"):
            problems.append(f"{rid}: tier {tier} ต้องมี source.url หรือ consent_id")
    if tier == "C" and not record.get("review"):
        problems.append(f"{rid}: tier C ต้องมี review block")
    return problems


def append_records(records: list[ScamRecord], output_path: Path) -> int:
    """append records ลง JSONL — ไม่ซ้ำ id เดิม; record ที่ validate ไม่ผ่านจะ raise"""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    existing_ids: set[str] = set()
    if output_path.exists():
        with output_path.open("r", encoding="utf-8") as f:
            for line in f:
                try:
                    existing_ids.add(json.loads(line)["id"])
                except (json.JSONDecodeError, KeyError):
                    continue

    added = 0
    with output_path.open("a", encoding="utf-8") as f:
        for r in records:
            if r.id in existing_ids:
                continue
            d = r.to_dict()
            problems = validate_record(d)
            if problems:
                raise ValueError("record ไม่ผ่าน schema v2: " + "; ".join(problems))
            f.write(json.dumps(d, ensure_ascii=False) + "\n")
            existing_ids.add(r.id)
            added += 1
    return added


def load_records(input_path: Path) -> list[dict]:
    if not input_path.exists():
        return []
    records = []
    with input_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records
