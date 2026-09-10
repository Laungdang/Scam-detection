"""
Wisesight Sentiment — safe-class baseline สำหรับ binary classification

Source: PyThaiNLP Wisesight Sentiment Corpus
HF: https://huggingface.co/datasets/pythainlp/wisesight_sentiment
License: CC0 1.0 (public domain)

ใช้เฉพาะ label = neutral / positive / negative (non-question) เป็นตัวอย่าง
"safe" Thai text (ข้อความปกติ ไม่ใช่ scam)

วิธีใช้:
    python -m ml.scrape.wisesight_safe --limit 200
"""

import argparse
from pathlib import Path

from datasets import load_dataset

from ml.scrape.schema import (
    ScamRecord,
    SourceAttribution,
    append_records,
    make_id,
    now_iso,
)


SOURCE_NAME = "PyThaiNLP Wisesight Sentiment (CC0)"
SOURCE_URL = "https://huggingface.co/datasets/pythainlp/wisesight_sentiment"
OUTPUT_PATH = Path("data/raw/scam_corpus.jsonl")

# Wisesight label mapping:
# 0 = positive, 1 = neutral, 2 = negative, 3 = question
SAFE_LABELS = {0, 1, 2}  # exclude question


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=200,
                       help="จำนวน safe records ที่จะ sample (default 200)")
    parser.add_argument("--split", type=str, default="train",
                       help="split ที่ใช้ (train/validation/test)")
    args = parser.parse_args()

    print(f"Loading Wisesight Sentiment ({args.split} split) ...")
    ds = load_dataset("pythainlp/wisesight_sentiment", split=args.split)
    print(f"Total in split: {len(ds)}")

    ts = now_iso()
    records: list[ScamRecord] = []
    skipped = 0

    for i, row in enumerate(ds):
        if len(records) >= args.limit:
            break
        text = (row.get("texts") or "").strip()
        category_label = row.get("category")
        if not text or category_label not in SAFE_LABELS:
            skipped += 1
            continue
        if len(text) < 10 or len(text) > 600:
            skipped += 1
            continue

        sentiment_name = {0: "positive", 1: "neutral", 2: "negative"}[category_label]

        records.append(
            ScamRecord(
                id=make_id("wisesight", text),
                text=text,
                verdict="safe",
                category=None,  # safe ไม่มี scam category
                tier="S",  # safe_real — social media text จริง (ไม่ใช่ SMS; ลดสัดส่วนเมื่อได้ SMS จริงจาก form)
                source=SourceAttribution(
                    name=SOURCE_NAME,
                    url=SOURCE_URL,
                    scraped_at=ts,
                    extraction_method="verbatim_html",
                    license="CC0",
                    license_note="CC0 1.0 — public domain",
                ),
                annotator_notes=f"wisesight_sentiment={sentiment_name}",
            )
        )

    added = append_records(records, OUTPUT_PATH)
    total = sum(1 for _ in OUTPUT_PATH.open(encoding="utf-8"))
    print(f"Wisesight safe: {len(records)} records, {skipped} skipped, {added} new appended")
    print(f"Total corpus now: {total} records")


if __name__ == "__main__":
    main()
