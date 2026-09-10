"""
Migrate scam_corpus.jsonl v1 → v2 (tier system) — CLAUDE.md Section 10.7

ทำอะไร:
1. backup corpus v1 → data/archive/scam_corpus.v1.jsonl
2. ย้าย artifact v1 (before_relabel, relabel_proposals) → data/archive/
3. copy xlsx RAG เดิม (LLM-generated) → data/archive/v1_rag_llm_generated.xlsx (ถ้ามี)
4. ทุก record: ใส่ tier / annotation (weak label จาก source) / review (tier C) / pii (mask strict) / source.license
5. เขียนทับ data/raw/scam_corpus.jsonl + พิมพ์สถิติต่อ tier

Idempotent: record ที่มี tier แล้วจะไม่ถูกเดาใหม่ (แต่ยัง mask PII ซ้ำได้ — masker idempotent)

รัน: python -m ml.scrape.migrate_v2 [--dry-run]
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
from collections import Counter
from pathlib import Path

os.environ.setdefault("PII_SALT", "migration-local")  # masker ต้องการ salt — hash ไม่ถูกเก็บใน corpus

from app.services.pii_masker import mask_pii  # noqa: E402
from ml.scrape.schema import TIER_NAMES, now_iso, validate_record  # noqa: E402


CORPUS = Path("data/raw/scam_corpus.jsonl")
ARCHIVE = Path("data/archive")
LEGACY_FILES = [
    Path("data/raw/scam_corpus.before_relabel.jsonl"),
    Path("data/raw/sources/relabel_proposals.jsonl"),
]
LEGACY_RAG_XLSX = [
    Path.home() / "Downloads" / "scam_dataset_v3_fixed.xlsx",
    Path.home() / "Downloads" / "scam_dataset_Actually_final.xlsx",
]
MASKER_VERSION = "pii_masker@2026-08"


def infer_tier(r: dict) -> tuple[str, str, str]:
    """คืน (tier, license, extraction_method_v2) จาก source ของ v1"""
    src = r.get("source") or {}
    name = (src.get("name") or "").lower()
    method = src.get("extraction_method") or ""
    verdict = r.get("verdict")

    if "wisesight" in name:
        return "S", "CC0", "verbatim_html"
    if "typhoon" in name or "synthetic" in name:
        return "C", "synthetic", "llm_generated"
    if "english-translated" in name or "translated" in name:
        return "B", "CC-BY-4.0", "translated"
    if "imc 2025" in name or "imc25" in name:
        return ("A" if verdict != "safe" else "S"), "CC-BY-4.0", "verbatim_html"
    if method in ("verbatim_html", "verbatim_pdf", "ocr_image", "verbatim_ocr"):
        return ("A" if verdict != "safe" else "S"), "fair_use_academic", method
    # ไม่รู้ที่มา → synthetic (ปลอดภัยที่สุด)
    return "C", "synthetic", "llm_generated"


def migrate_record(r: dict) -> dict:
    out = dict(r)
    src = dict(r.get("source") or {})

    if "tier" not in out:
        tier, license_, method_v2 = infer_tier(r)
        out["tier"] = tier
        src.setdefault("license", license_)
        if src.get("extraction_method") == "manual_entry":
            src["extraction_method"] = method_v2
    src.setdefault("snapshot_hash", None)
    src.setdefault("consent_id", None)
    src.setdefault("license", None)
    out["source"] = src

    # annotation: label v1 เป็น weak label จาก source — ยังไม่ผ่าน guideline v2
    if "annotation" not in out:
        out["annotation"] = {
            "labels": [{
                "annotator": f"source:{src.get('name', 'unknown')}",
                "verdict": r.get("verdict"),
                "category": r.get("category"),
                "confidence": None,
                "notes": r.get("annotator_notes"),
            }],
            "final": {
                "verdict": r.get("verdict"),
                "category": r.get("category"),
                "resolved_by": "source_weak_label",
            },
            "guideline_version": None,
        }

    if out["tier"] == "C" and not out.get("review"):
        notes = r.get("annotator_notes") or ""
        status = "approved" if "status=approved" in notes else "pending_review"
        out["review"] = {"status": status, "reviewer": None, "reviewed_at": None, "notes": None}

    # PII: mask strict (idempotent) — text ที่เปลี่ยน = เคยมี PII ดิบ
    masked = mask_pii(out["text"], mode="strict")
    out["pii"] = {
        "masked": True,
        "masker_version": MASKER_VERSION,
        "pii_found_count": len(masked.pii_found),
    }
    out["text"] = masked.masked
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if not CORPUS.exists():
        print(f"ERROR: {CORPUS} not found")
        return 1

    records = [json.loads(l) for l in CORPUS.read_text(encoding="utf-8").splitlines() if l.strip()]
    print(f"loaded {len(records)} records from {CORPUS}")

    migrated = [migrate_record(r) for r in records]

    problems: list[str] = []
    for m in migrated:
        problems.extend(validate_record(m))
    changed_text = sum(1 for a, b in zip(records, migrated) if a["text"] != b["text"])

    print("\n=== By tier ===")
    for k, v in sorted(Counter(m["tier"] for m in migrated).items()):
        print(f"  {v:5}  {k} ({TIER_NAMES[k]})")
    print("\n=== tier × verdict ===")
    for (t, v), n in sorted(Counter((m["tier"], m["verdict"]) for m in migrated).items()):
        print(f"  {n:5}  {t} / {v}")
    print(f"\nrecords with text changed by PII masking: {changed_text}")
    print(f"tier C pending_review: {sum(1 for m in migrated if m['tier']=='C' and (m.get('review') or {}).get('status')=='pending_review')}")
    print(f"validation problems: {len(problems)}")
    for p in problems[:20]:
        print("   -", p)

    if args.dry_run:
        print("\n(dry-run — nothing written)")
        return 0
    if problems:
        print("\nABORT: แก้ปัญหา validation ก่อน migrate")
        return 1

    ARCHIVE.mkdir(parents=True, exist_ok=True)
    backup = ARCHIVE / "scam_corpus.v1.jsonl"
    if not backup.exists():
        shutil.copy2(CORPUS, backup)
        print(f"\nbackup → {backup}")
    for f in LEGACY_FILES:
        if f.exists():
            dest = ARCHIVE / f.name
            shutil.move(str(f), str(dest))
            print(f"archived {f} → {dest}")
    for x in LEGACY_RAG_XLSX:
        if x.exists():
            dest = ARCHIVE / f"v1_rag_llm_generated__{x.name}"
            if not dest.exists():
                shutil.copy2(x, dest)
                print(f"archived RAG xlsx (LLM-generated, fabricated attribution) → {dest}")

    with CORPUS.open("w", encoding="utf-8") as f:
        for m in migrated:
            f.write(json.dumps(m, ensure_ascii=False) + "\n")
    print(f"\nwrote {len(migrated)} records → {CORPUS} (schema v2)")

    (ARCHIVE / "README.md").write_text(
        "# data/archive — Data v1 artifacts (2026-08-29)\n\n"
        "เก็บไว้เพื่อ reproducibility ของผล v1 ใน thesis — **ห้ามใช้ train/eval v2**\n\n"
        "| ไฟล์ | คืออะไร |\n|---|---|\n"
        "| scam_corpus.v1.jsonl | corpus ก่อน migrate เป็น tier schema |\n"
        "| scam_corpus.before_relabel.jsonl | backup ก่อน Week 4 relabel experiment |\n"
        "| relabel_proposals.jsonl | audit trail ของ LLM relabel (rollback แล้ว) |\n"
        "| v1_rag_llm_generated__*.xlsx | RAG cases ชุดแรก — LLM (Claude) generate โดยอ้างชื่อสำนักข่าว "
        "ไม่มี URL, text/source ไม่ตรงกัน → จัดเป็น tier C, ถอดออกจาก chroma (CLAUDE.md 10.7) |\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
