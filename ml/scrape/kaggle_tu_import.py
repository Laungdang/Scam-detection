"""
Import Kaggle "Thai Scam From online Platforms Dataset" (kkorakott) → tier C (synthetic, pending_review)

ข้อเท็จจริงที่ตรวจแล้ว (2026-08-29, ดู DATACARD.md §2.3):
- 2,999 แถว แต่เป็น template ~1,214 แบบ × augmentation (emoji/typo/spacing) — column `noise_type` บอกเอง
- label = threshold ของ `risk_score_expected` (ทำนายได้ 100%) ซึ่งเป็นสูตร rule จาก keyword flag
  → label คือ rule-label ไม่ใช่ human label; ข้อความเดียวกันไม่เคยได้ label ต่างกัน
- placeholder domain (`example.invalid`, `@fakeid`, `[URL]`) 656 แถว, platform 9 ค่ากระจายเท่ากันเป๊ะ
- Kaggle card อ้างว่า "obtain from many online platforms" — ไม่สอดคล้องกับข้อมูล → จัดเป็น tier C
- License: CC BY-NC-SA 4.0 — ใช้วิจัยได้ ต้อง cite; ส่วนนี้ของ corpus ถ้าเผยแพร่ต้อง share-alike

การใช้: ห้าม test/val/RAG (10.2); train ได้เฉพาะหลัง human review; หลัก ๆ ใช้เป็น external comparison
(ml/kaggle_tu_compare.py) และ class normal เป็น tier S candidate หลังคนกวาดตา

รัน: python -m ml.scrape.kaggle_tu_import [--dry-run]
"""

from __future__ import annotations

import argparse
import os
import re
from collections import Counter
from pathlib import Path

import pandas as pd

os.environ.setdefault("PII_SALT", "import-local")

from app.services.pii_masker import mask_pii  # noqa: E402
from ml.scrape.schema import (  # noqa: E402
    Annotation,
    AnnotationLabel,
    PiiInfo,
    Review,
    ScamRecord,
    SourceAttribution,
    append_records,
    make_id,
    now_iso,
)

CSV_PATH = Path("data/raw/sources/tu_scam_dataset.csv")
CORPUS_PATH = Path("data/raw/scam_corpus.jsonl")
SOURCE_NAME = "Kaggle: Thai Scam From online Platforms Dataset (kkorakott)"
SOURCE_URL = "https://www.kaggle.com/datasets/kkorakott/thai-scam-from-online-platforms-dataset"

LABEL_MAP = {"scam": "danger", "suspicious": "caution", "normal": "safe"}

# Kaggle category → schema category (CLAUDE.md 4.5) — ตาม "กลไกหลัก" ใน ANNOTATION_GUIDELINE §2
# *_risk (suspicious) ใช้ base เดียวกัน
CATEGORY_MAP = {
    "phishing": "phishing_link",
    "delivery_scam": "phishing_link",
    "otp": "phishing_link",              # ขอ OTP/รหัส = ขโมย credential (ไม่มีหมวดแยก)
    "impersonation": "impersonation_authority",
    "job_scam": "investment_scam",       # งานออนไลน์ได้เงินวันละ N = รายได้เกินจริง (guideline §2)
    "job": "investment_scam",
    "fake_scholarship": "prize_scam",    # ล่อด้วยทุน แล้วขอค่าดำเนินการ = advance-fee reward
    "refund_scam": "prize_scam",         # เงินคืนค่าธรรมเนียม กดลิงก์
    "marketplace_scam": "financial_fraud",
    "marketplace": "financial_fraud",
    "tu_scam": "other",
}


EMOJI_RE = re.compile(r"[\U0001F300-\U0001FAFF☀-➿⬀-⯿️‼️❗]")
# suffix augmentation ที่ generator ต่อท้าย template (วัด 2026-08-29: แต่ละแบบ ~50-200 แถว)
AUG_SUFFIX_RE = re.compile(
    r"(\s*(line:\s*@fakeid|ส่งในกลุ่มได้เลย|ASAP|DM me|now|pls|verify pls|ok\?|ทัก DM|inbox ได้|"
    r"tel:\s*\S+|โทร\s*\d[\d-]+)\s*)+$",
    re.I,
)


def normalize(text: str) -> str:
    """key สำหรับ dedupe template: ตัด emoji, suffix augmentation, วรรค/เครื่องหมาย
    2,999 แถว → 1,214 (ตัด emoji) → 473 (ตัด suffix ด้วย)"""
    s = EMOJI_RE.sub("", text)
    s = AUG_SUFFIX_RE.sub("", s.strip())
    return re.sub(r"[^฀-๿A-Za-z0-9]", "", s).lower()


def map_category(kaggle_cat: str, verdict: str) -> str | None:
    if verdict == "safe":
        return None
    base = re.sub(r"_risk$", "", kaggle_cat)
    return CATEGORY_MAP.get(base, "other")


def build_records(df: pd.DataFrame) -> tuple[list[ScamRecord], pd.DataFrame]:
    df = df.copy()
    df["norm"] = df["text"].map(normalize)
    # 1 record ต่อ template: เลือก variant ที่ noise น้อยที่สุด (none > อื่น) และสั้นสุด
    df["noise_rank"] = (df["noise_type"] != "none").astype(int)
    df = df.sort_values(["norm", "noise_rank", "text_length"])
    variants = df.groupby("norm").size().rename("n_variants")
    reps = df.drop_duplicates("norm").join(variants, on="norm")

    ts = now_iso()
    records: list[ScamRecord] = []
    for _, row in reps.iterrows():
        verdict = LABEL_MAP[row["label"]]
        category = map_category(str(row["category"]), verdict)
        text = mask_pii(str(row["text"]).strip(), mode="strict")
        records.append(
            ScamRecord(
                id=make_id("kaggle-tu", row["norm"]),
                text=text.masked,
                verdict=verdict,
                category=category,
                tier="C",
                source=SourceAttribution(
                    name=SOURCE_NAME,
                    url=SOURCE_URL,
                    scraped_at=ts,
                    extraction_method="llm_generated",  # template-generated + augmentation (ดู docstring)
                    published_date=None,
                    license="CC-BY-NC-SA-4.0",
                    license_note=(
                        "CC BY-NC-SA 4.0 (Kaggle, kkorakott, v1). Template-generated synthetic with "
                        "rule-derived labels (risk_score threshold) — verified 2026-08-29; NOT real platform data "
                        "despite dataset card claim. Non-commercial, share-alike."
                    ),
                ),
                annotation=Annotation(
                    labels=[AnnotationLabel(
                        annotator="source:kaggle-rule-label",
                        verdict=verdict,
                        category=category,
                        confidence=None,
                        notes=f"kaggle_label={row['label']} kaggle_category={row['category']} "
                              f"risk_score={row['risk_score_expected']} platform={row['platform']}",
                    )],
                    final={"verdict": verdict, "category": category, "resolved_by": "source_weak_label"},
                    guideline_version=None,
                ),
                review=Review(status="pending_review"),
                pii=PiiInfo(masked=True, masker_version="pii_masker@2026-08", pii_found_count=len(text.pii_found)),
                annotator_notes=(
                    f"kaggle_ids={','.join(str(i) for i in df[df['norm'] == row['norm']]['id'].tolist()[:50])} | "
                    f"n_variants={int(row['n_variants'])} | noise_types="
                    f"{','.join(sorted(df[df['norm'] == row['norm']]['noise_type'].unique()))}"
                ),
            )
        )
    return records, reps


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    df = pd.read_csv(CSV_PATH)
    records, reps = build_records(df)
    print(f"rows {len(df)} → templates {len(records)}")
    print("verdict:", dict(Counter(r.verdict for r in records)))
    print("category:", dict(Counter(r.category for r in records)))
    print("variants per template: median", int(reps["n_variants"].median()), "max", int(reps["n_variants"].max()))
    for r in records[:3]:
        print("  --", r.verdict, r.category, "|", r.text[:80])
    if args.dry_run:
        print("(dry-run)")
        return 0
    added = append_records(records, CORPUS_PATH)
    print(f"appended {added} tier C (pending_review) records → {CORPUS_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
