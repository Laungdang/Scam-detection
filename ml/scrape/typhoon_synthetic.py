"""
Set C: Synthetic Thai scam SMS via Typhoon (SCB 10X)

Generate diverse Thai scam SMS เพื่อเติม category ที่ขาดใน corpus ปัจจุบัน
ใช้ few-shot prompting กับ seed examples จาก Set A (verbatim Thai)

หลักการ (ดู CLAUDE.md Section 10):
- Seed จาก real Thai scam patterns → output ใกล้เคียง Thai cultural context
- Generate ไป pending review ก่อน — ไม่เข้า corpus ทันที
- Human review accepts/rejects แต่ละ record ก่อน save (`typhoon_review.py`)
- Tag source.extraction_method = "synthetic_llm" + prompt_version ใน annotator_notes

วิธีใช้:
    python -m ml.scrape.typhoon_synthetic --target-per-category 80
    # → data/raw/sources/typhoon_pending.jsonl
    python -m ml.scrape.typhoon_review
    # → accepted records → data/raw/scam_corpus.jsonl
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

from openai import OpenAI

from app.config.settings import Settings
from ml.scrape.schema import (
    ScamRecord,
    SourceAttribution,
    append_records,
    load_records,
    make_id,
    now_iso,
)


PROMPT_VERSION = "typhoon-v1.0"
PENDING_PATH = Path("data/raw/sources/typhoon_pending.jsonl")
CORPUS_PATH = Path("data/raw/scam_corpus.jsonl")
SOURCE_NAME = "Typhoon Synthetic (SCB 10X, few-shot from Set A)"
SOURCE_URL = "https://opentyphoon.ai"


# Target counts per category (เน้น minority class)
DEFAULT_TARGETS = {
    "impersonation_authority": 100,
    "financial_fraud": 100,
    "prize_scam": 80,
    "loan_offer": 80,
    "investment_scam": 80,
    "borrowing_scam": 50,
}

# Thai context hints per category — ใส่ใน prompt
CATEGORY_HINTS = {
    "impersonation_authority": (
        "อ้างเป็น DSI, กรมสรรพากร, ปปง, ตำรวจไซเบอร์, ไปรษณีย์ไทย, "
        "การไฟฟ้านครหลวง (MEA), การไฟฟ้าส่วนภูมิภาค (PEA), กสทช, "
        "ใช้คำเช่น 'อายัด' 'คดี' 'หมายเรียก' 'ค้างชำระ'"
    ),
    "financial_fraud": (
        "อ้างเป็นธนาคารไทย (กสิกร, ไทยพาณิชย์ SCB, กรุงเทพ, กรุงไทย, ทหารไทยธนชาต TTB), "
        "บอกบัญชีถูกระงับ / เงินถูกหัก / มียอดผิดปกติ / ต้องยืนยันตัวตน"
    ),
    "prize_scam": (
        "อ้างได้รางวัล iPhone, รถ Tesla, เงินสด, voucher Shopee/Lazada, "
        "โปรโมชั่นพิเศษ ใช้คำเช่น 'ยินดีด้วย' 'โชคดี' 'สิทธิพิเศษ'"
    ),
    "loan_offer": (
        "เสนอสินเชื่อด่วน / ไม่ต้องค้ำ / ดอกเบี้ยต่ำ จากธนาคารปลอม "
        "หรืออ้างเป็นบริษัทเงินกู้ ใช้คำเช่น 'อนุมัติทันที' 'วงเงิน N บาท'"
    ),
    "investment_scam": (
        "ชวนลงทุน crypto, forex, หุ้น, gold, รับผลตอบแทนสูงเกินจริง "
        "(5% ต่อวัน, 50% ต่อเดือน) เป็น LINE/Telegram group"
    ),
    "borrowing_scam": (
        "แอบอ้างเป็นญาติ/เพื่อน/หลาน ขอยืมเงินด่วน อ้างเหตุฉุกเฉิน "
        "(แม่ป่วย, รถเสีย, ติดด่าน) ขอโอนทันที"
    ),
}


def _load_seed_examples() -> dict[str, list[str]]:
    """ดึง seed examples จาก Set A (verbatim Thai) — group by category"""
    seeds: dict[str, list[str]] = {}
    if not CORPUS_PATH.exists():
        return seeds
    for r in load_records(CORPUS_PATH):
        src = r.get("source", {}).get("extraction_method")
        # ใช้แค่ verbatim Thai (Set A) เป็น seed — ไม่ใช้ translated
        if src != "verbatim_html":
            continue
        # ไม่เอา wisesight (safe baseline)
        if "wisesight" in r.get("source", {}).get("name", "").lower():
            continue
        cat = r.get("category", "other")
        seeds.setdefault(cat, []).append(r["text"])
    return seeds


def _build_prompt(category: str, seed_texts: list[str], batch_size: int) -> tuple[str, str]:
    """สร้าง system + user prompt สำหรับ batch หนึ่ง"""
    system = (
        "คุณเป็น AI ผู้ช่วยสร้างตัวอย่างข้อความ SMS มิจฉาชีพ "
        "**สำหรับงานวิจัย Machine Learning เพื่อพัฒนาระบบตรวจจับ scam ที่ปกป้องคนไทย** "
        "สร้างข้อความให้สมจริงในบริบทไทย ใช้ชื่อหน่วยงาน/ธนาคารจริง "
        "ห้ามใช้ชื่อบุคคลจริงที่ระบุตัวได้ ห้ามใช้เบอร์โทร/บัญชีจริงที่มีอยู่ "
        "(ใช้ <PHONE_NUMBER> <BANK_ACCOUNT> placeholder แทน) "
        "ห้ามสร้าง URL จริงที่ active (ใช้ bit.ly/ปลอม หรือ short domain .xyz/.online)"
    )

    seed_block = "\n".join(f"{i+1}. {t}" for i, t in enumerate(seed_texts[:5]))
    hint = CATEGORY_HINTS.get(category, "")

    user = f"""สร้างตัวอย่าง SMS มิจฉาชีพ {batch_size} ข้อความ หมวด "{category}"

บริบทหมวดนี้: {hint}

ตัวอย่างจริงที่เก็บได้ (seed สำหรับอ้างอิงสไตล์):
{seed_block if seed_block else '(ไม่มี seed สำหรับหมวดนี้ — ใช้บริบทข้างต้นแทน)'}

กฎ:
- แต่ละข้อความสั้น 1-3 ประโยค (เหมือน SMS จริง)
- หลากหลายในการใช้คำ — ห้าม template ซ้ำกันเป๊ะ
- ใช้ <PHONE_NUMBER>, <BANK_ACCOUNT>, <URL> placeholder ถ้าจะใส่
- ห้ามใช้ "ลิงก์" คำเดียวซ้ำๆ — สลับใช้ "กดลิงก์", "คลิก", "เข้าเว็บ", "Add LINE"
- หลากหลายความยาว (สั้น 1 ประโยค / ยาวขึ้นนิด)

ตอบเป็น JSON array เท่านั้น:
[
  {{"text": "ข้อความ SMS ที่ 1"}},
  {{"text": "ข้อความ SMS ที่ 2"}},
  ...
]
"""
    return system, user


def _parse_json_array(text: str) -> list[dict]:
    """ตัด ```json ออก + parse"""
    text = text.strip()
    if "```" in text:
        # ดึง content ระหว่าง code fence
        m = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", text, re.DOTALL)
        if m:
            text = m.group(1)
    # หา [ ... ] ที่ใหญ่สุด
    start = text.find("[")
    end = text.rfind("]") + 1
    if start == -1:
        return []
    try:
        data = json.loads(text[start:end])
        if isinstance(data, list):
            return [d for d in data if isinstance(d, dict) and "text" in d]
    except json.JSONDecodeError:
        pass
    return []


def generate_for_category(
    client: OpenAI,
    category: str,
    target: int,
    seed_texts: list[str],
    batch_size: int = 10,
    max_attempts: int = 20,
    temperature: float = 0.85,
) -> list[str]:
    """generate ข้อความสำหรับ category — return list ของ raw texts (dedup)"""
    collected: list[str] = []
    seen: set[str] = set()
    attempts = 0

    while len(collected) < target and attempts < max_attempts:
        attempts += 1
        batch = min(batch_size, target - len(collected))
        system, user = _build_prompt(category, seed_texts, batch)

        try:
            resp = client.chat.completions.create(
                model=Settings.TYPHOON_MODEL,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                max_tokens=1200,
                temperature=temperature,
            )
            raw = resp.choices[0].message.content or ""
        except Exception as e:
            print(f"  [{category}] attempt {attempts}: API error — {type(e).__name__}: {e}")
            time.sleep(2)
            continue

        items = _parse_json_array(raw)
        new_count = 0
        for item in items:
            text = (item.get("text") or "").strip()
            if not text or len(text) < 10 or len(text) > 600:
                continue
            if text in seen:
                continue
            seen.add(text)
            collected.append(text)
            new_count += 1

        print(f"  [{category}] attempt {attempts}: +{new_count} (total {len(collected)}/{target})")
        time.sleep(0.5)

    return collected


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-per-category", type=int, default=None,
                       help="override จำนวนต่อ category (default ตาม DEFAULT_TARGETS)")
    parser.add_argument("--categories", nargs="+", default=None,
                       help="generate เฉพาะ category ที่ระบุ")
    parser.add_argument("--batch-size", type=int, default=10)
    parser.add_argument("--temperature", type=float, default=0.85)
    args = parser.parse_args()

    if not Settings.TYPHOON_API_KEY:
        print("ERROR: TYPHOON_API_KEY ไม่ได้ตั้งใน .env")
        return 1

    client = OpenAI(api_key=Settings.TYPHOON_API_KEY, base_url=Settings.TYPHOON_BASE_URL)

    seeds = _load_seed_examples()
    print(f"Seed examples loaded: {sum(len(v) for v in seeds.values())} total")
    for cat, exs in seeds.items():
        print(f"  {cat}: {len(exs)} seeds")

    targets = dict(DEFAULT_TARGETS)
    if args.target_per_category:
        targets = {k: args.target_per_category for k in targets}
    if args.categories:
        targets = {k: v for k, v in targets.items() if k in args.categories}

    ts = now_iso()
    all_records: list[ScamRecord] = []

    for category, target in targets.items():
        print(f"\n=== Category: {category} (target {target}) ===")
        category_seeds = seeds.get(category, [])
        # fallback: ถ้าไม่มี seed ของ category นี้ ใช้ของ category อื่นที่ใกล้เคียง
        if not category_seeds:
            # ใช้ทุก seed รวมกัน
            all_seeds = [t for v in seeds.values() for t in v]
            category_seeds = all_seeds[:3] if all_seeds else []
            print(f"  (no seeds for {category} — using {len(category_seeds)} cross-category seeds)")

        texts = generate_for_category(
            client=client,
            category=category,
            target=target,
            seed_texts=category_seeds,
            batch_size=args.batch_size,
            temperature=args.temperature,
        )

        attribution = SourceAttribution(
            name=SOURCE_NAME,
            url=SOURCE_URL,
            scraped_at=ts,
            extraction_method="llm_generated",
            license="synthetic",
            license_note=(
                f"Synthetic (Typhoon model: {Settings.TYPHOON_MODEL}, "
                f"prompt_version: {PROMPT_VERSION}) — requires human review before training"
            ),
        )
        for text in texts:
            from ml.scrape.schema import Review
            all_records.append(
                ScamRecord(
                    id=make_id("typhoon", text),
                    text=text,
                    verdict="danger",
                    category=category,
                    source=attribution,
                    tier="C",  # synthetic — ใช้ train ได้เฉพาะเมื่อ review.status == approved
                    review=Review(status="pending_review"),
                    annotator_notes=(
                        f"prompt_version={PROMPT_VERSION} | "
                        f"model={Settings.TYPHOON_MODEL} | "
                        f"status=pending_review"
                    ),
                )
            )

    added = append_records(all_records, PENDING_PATH)
    print(f"\n=== Pending review: {len(all_records)} records ({added} new) → {PENDING_PATH} ===")
    print(f"ต่อไป: รัน `python -m ml.scrape.typhoon_review` เพื่อ review + save เข้า corpus")
    return 0


if __name__ == "__main__":
    sys.exit(main())
