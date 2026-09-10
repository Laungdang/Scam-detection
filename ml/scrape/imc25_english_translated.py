"""
Translate English entries from IMC25 Smishing Dataset to Thai

ใช้ Google Translate ผ่าน deep-translator
ทุก record ติด tag source = english_translated_imc25 + เก็บ original_text ใน annotator_notes
เพื่อ traceability + เปรียบเทียบ verbatim vs translated ใน thesis

วิธีใช้:
    python -m ml.scrape.imc25_english_translated --max-per-category 80 --delay 0.5

CLAUDE.md Section 10 รุ่นแก้: Cross-lingual transfer learning approach
"""

import argparse
import csv
import io
import time
from collections import Counter, defaultdict
from pathlib import Path

import requests
from deep_translator import GoogleTranslator

from ml.scrape.schema import (
    ScamRecord,
    SourceAttribution,
    append_records,
    make_id,
    now_iso,
)


CSV_URL = (
    "https://raw.githubusercontent.com/reportsmishing/"
    "Smishing-Dataset-IMC25/main/dataset/final_dataset_output.csv"
)
SOURCE_NAME = "IMC 2025 Smishing Dataset (English-translated to Thai)"
SOURCE_URL = "https://github.com/reportsmishing/Smishing-Dataset-IMC25"
CACHE_PATH = Path("data/raw/sources/imc25_raw.csv")
OUTPUT_PATH = Path("data/raw/scam_corpus.jsonl")

SCAM_TYPE_MAP = {
    "delivery": "phishing_link",
    "banking": "phishing_link",
    "wrong number": "romance_scam",
    "others": "other",
    "investment": "investment_scam",
    "prize": "prize_scam",
    "loan": "loan_offer",
    "tax": "impersonation_authority",
}


def download_csv() -> str:
    """download + cache (ไม่โหลดซ้ำถ้ามีอยู่แล้ว)"""
    if CACHE_PATH.exists():
        print(f"Using cached {CACHE_PATH}")
        return CACHE_PATH.read_text(encoding="utf-8")
    print(f"Downloading {CSV_URL} ...")
    resp = requests.get(CSV_URL, timeout=30)
    resp.raise_for_status()
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(resp.text, encoding="utf-8")
    return resp.text


def _looks_english_only(text: str) -> bool:
    """ตรวจว่า text เป็นภาษาอังกฤษล้วน (ไม่มีอักษรไทย/จีน)"""
    return text.isprintable() and not any(ord(c) > 127 and not c.isspace() for c in text)


def collect_english_subset(csv_text: str, max_per_category: int) -> list[dict]:
    """sample English records, balance ตาม category"""
    reader = csv.DictReader(io.StringIO(csv_text))
    by_category: dict[str, list[dict]] = defaultdict(list)
    seen_texts: set[str] = set()

    for row in reader:
        text = (row.get("text") or "").strip()
        if not text or text in seen_texts:
            continue
        language = (row.get("language") or "").strip().lower()
        if language != "english":
            continue
        if not _looks_english_only(text):
            continue
        if len(text) < 10 or len(text) > 600:
            continue

        seen_texts.add(text)
        scam_type = (row.get("scam_type") or "others").strip().lower()
        category = SCAM_TYPE_MAP.get(scam_type, "other")

        if len(by_category[category]) >= max_per_category:
            continue
        by_category[category].append({
            "text": text,
            "category": category,
            "scam_type": scam_type,
            "lure": row.get("lure_principles", ""),
            "published": row.get("time", ""),
        })

    print(f"English subset by category: {dict(Counter({k: len(v) for k, v in by_category.items()}))}")
    return [r for records in by_category.values() for r in records]


def translate_with_retry(text: str, translator: GoogleTranslator, retries: int = 3) -> str | None:
    """แปลพร้อม retry — fail → return None"""
    for attempt in range(retries):
        try:
            result = translator.translate(text)
            if result and result.strip():
                return result.strip()
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
                continue
            print(f"  translation failed: {e!r}")
            return None
    return None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-per-category", type=int, default=80,
                       help="จำกัดจำนวนต่อ category (default 80)")
    parser.add_argument("--delay", type=float, default=0.5,
                       help="หน่วงเวลาระหว่าง translation request (วินาที)")
    parser.add_argument("--limit", type=int, default=None,
                       help="จำกัดจำนวนรวมที่จะแปล (สำหรับ test)")
    args = parser.parse_args()

    csv_text = download_csv()
    english_subset = collect_english_subset(csv_text, args.max_per_category)
    if args.limit:
        english_subset = english_subset[: args.limit]
    print(f"Total English records to translate: {len(english_subset)}")

    translator = GoogleTranslator(source="en", target="th")
    ts = now_iso()
    records: list[ScamRecord] = []
    skipped = 0

    for i, row in enumerate(english_subset, 1):
        thai_text = translate_with_retry(row["text"], translator)
        if not thai_text:
            skipped += 1
            print(f"  [{i}/{len(english_subset)}] SKIP — translation failed")
            continue

        notes_bits = [
            f"original_text_en={row['text'][:200]}",
            f"imc25_scam_type={row['scam_type']}",
        ]
        if row["lure"]:
            notes_bits.append(f"lure={row['lure']}")

        records.append(
            ScamRecord(
                id=make_id("imc25en", thai_text),
                text=thai_text,
                verdict="danger",
                category=row["category"],
                tier="B",  # real_foreign — train/val only, ห้ามอยู่ใน test (CLAUDE.md 10.2)
                source=SourceAttribution(
                    name=SOURCE_NAME,
                    url=SOURCE_URL,
                    scraped_at=ts,
                    extraction_method="translated",
                    published_date=row["published"] or None,
                    license="CC-BY-4.0",
                    license_note=(
                        "CC-BY-4.0 (IMC 2025) | Translated: Google Translate "
                        "via deep-translator | English original in annotator_notes"
                    ),
                ),
                annotator_notes=" | ".join(notes_bits),
            )
        )

        if i % 25 == 0:
            print(f"  [{i}/{len(english_subset)}] translated")
        time.sleep(args.delay)

    added = append_records(records, OUTPUT_PATH)
    total = sum(1 for _ in OUTPUT_PATH.open(encoding="utf-8"))
    print(f"\nIMC25-EN: {len(records)} translated, {skipped} skipped, {added} new appended")
    print(f"Total corpus now: {total} records")


if __name__ == "__main__":
    main()
