"""
IMC25 Smishing Dataset — Thai entries extraction

Source: Fishing for Smishing (IMC 2025)
GitHub: https://github.com/reportsmishing/Smishing-Dataset-IMC25
License: CC-BY-4.0 (requires attribution)

Dataset columns:
- time, sender_id, telephone_number_type, original_network_name, original_network_country
- text, translation, language, url_shortener, named_entity, scam_type, lure_principles

วิธีใช้:
    python -m ml.scrape.imc25_dataset

จะ download CSV, filter Thai entries, save เข้า scam_corpus.jsonl
"""

import csv
import io
from pathlib import Path

import requests

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
SOURCE_NAME = "IMC 2025 Smishing Dataset (Fishing for Smishing)"
SOURCE_URL = "https://github.com/reportsmishing/Smishing-Dataset-IMC25"
OUTPUT_PATH = Path("data/raw/scam_corpus.jsonl")


# IMC25 scam_type → our category
SCAM_TYPE_MAP = {
    "delivery": "phishing_link",
    "banking": "phishing_link",
    "wrong number": "romance_scam",  # often pretext to start romance scam
    "others": "other",
    "investment": "investment_scam",
    "prize": "prize_scam",
    "loan": "loan_offer",
    "tax": "impersonation_authority",
}


def _looks_like_thai(text: str) -> bool:
    """ตรวจว่ามีอักษรไทยใน text หรือไม่ (Thai Unicode block U+0E00–U+0E7F)"""
    return any("฀" <= ch <= "๿" for ch in text)


def download_csv() -> str:
    print(f"Downloading {CSV_URL} ...")
    resp = requests.get(CSV_URL, timeout=30)
    resp.raise_for_status()
    return resp.text


def parse_thai_records(csv_text: str) -> list[ScamRecord]:
    """parse CSV, filter เฉพาะ row ที่ text เป็นภาษาไทย"""
    reader = csv.DictReader(io.StringIO(csv_text))
    records: list[ScamRecord] = []
    ts = now_iso()
    scanned = 0
    thai_found = 0

    for row in reader:
        scanned += 1
        text = (row.get("text") or "").strip()
        if not text:
            continue

        language = (row.get("language") or "").strip().lower()
        country = (row.get("original_network_country") or "").strip().upper()
        # ยึดเกณฑ์: language เป็น thai หรือ country = THA + text มีอักษรไทย
        is_thai = "thai" in language or (country == "THA" and _looks_like_thai(text))
        if not is_thai:
            continue
        # ถ้า language ระบุไทยแต่ text ไม่มีอักษรไทย → skip (อาจเป็น noise)
        if not _looks_like_thai(text):
            continue

        thai_found += 1
        scam_type_raw = (row.get("scam_type") or "").strip().lower()
        category = SCAM_TYPE_MAP.get(scam_type_raw, "other")

        published = (row.get("time") or "").strip() or None
        attribution = SourceAttribution(
            name=SOURCE_NAME,
            url=SOURCE_URL,
            scraped_at=ts,
            extraction_method="verbatim_html",  # CSV row คือ verbatim text
            published_date=published,
            license="CC-BY-4.0",
            license_note="CC-BY-4.0 — Fishing for Smishing (IMC 2025)",
        )
        notes_bits = []
        if scam_type_raw:
            notes_bits.append(f"imc25_scam_type={scam_type_raw}")
        if row.get("lure_principles"):
            notes_bits.append(f"lure={row['lure_principles']}")
        if row.get("original_network_name"):
            notes_bits.append(f"network={row['original_network_name']}")

        records.append(
            ScamRecord(
                id=make_id("imc25", text),
                text=text,
                verdict="danger",
                category=category,
                source=attribution,
                tier="A",  # SMS ไทยจริงจาก peer-reviewed dataset (CLAUDE.md 10.2)
                annotator_notes="; ".join(notes_bits) if notes_bits else None,
            )
        )

    print(f"Scanned {scanned} rows total — found {thai_found} Thai records")
    return records


def main() -> None:
    csv_text = download_csv()
    records = parse_thai_records(csv_text)
    added = append_records(records, OUTPUT_PATH)
    total = sum(1 for _ in OUTPUT_PATH.open(encoding="utf-8"))
    print(f"IMC25: {len(records)} Thai records, {added} new appended")
    print(f"Total corpus now: {total} records")


if __name__ == "__main__":
    main()
