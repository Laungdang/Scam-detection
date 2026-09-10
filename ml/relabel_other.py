"""
Week 4: Auto-relabel "other" category — rules + LLM verification

ปัญหา (จาก ml.error_analysis): "other" รวม records 3 ประเภท
1. Scam ที่ label ผิด (เช่น phishing ที่ถูก dump เป็น "other")
2. Noise/promotional ที่ไม่ใช่ scam จริง
3. Scam ประเภทอื่นจริง ๆ ที่ไม่อยู่ใน 8 categories

วิธี:
1. Rules — เร็ว, deterministic, จัดการ case ชัด ๆ
2. Typhoon LLM — verify case ที่ rules ไม่ตัดสิน
3. Output diff report (audit trail) → apply เข้า corpus

วิธีใช้:
    python -m ml.relabel_other --apply
    # หรือ dry-run ก่อน:
    python -m ml.relabel_other
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from openai import OpenAI

from app.config.settings import Settings


CORPUS_PATH = Path("data/raw/scam_corpus.jsonl")
PROPOSAL_PATH = Path("data/raw/sources/relabel_proposals.jsonl")
BACKUP_PATH = Path("data/raw/scam_corpus.before_relabel.jsonl")

RelabelAction = Literal[
    "keep_other",          # ยังเป็น other (real misc)
    "relabel",             # เปลี่ยน category
    "remove",              # ไม่ใช่ scam จริง — ลบจาก training
    "keep_safe",           # จริง ๆ ควรเป็น safe
]

VALID_CATEGORIES = {
    "borrowing_scam", "financial_fraud", "impersonation_authority",
    "investment_scam", "loan_offer", "phishing_link", "prize_scam",
    "romance_scam", "other",
}


# ─────────────────────────────────────────────────────────────────
# Rules — deterministic
# ─────────────────────────────────────────────────────────────────

URL_RE = re.compile(r"<URL>|https?://|bit\.ly|line\.me", re.IGNORECASE)
CLICK_RE = re.compile(r"คลิก|กดลิงก์|Add LINE|click|join", re.IGNORECASE)


def _has_any(text: str, keywords: list[str]) -> bool:
    return any(k.lower() in text.lower() for k in keywords)


def rule_classify(text: str) -> tuple[str, str]:
    """returns (action, new_category_or_reason)"""
    t = text.strip()
    if not t:
        return "remove", "empty_text"

    # very short + no URL/clickable → likely noise/greeting/fragment
    if len(t) < 15 and not URL_RE.search(t):
        return "remove", "too_short_no_link"

    has_url = bool(URL_RE.search(t))
    has_click = bool(CLICK_RE.search(t))
    has_action_link = has_url or has_click

    # === Strong category signals ===
    if _has_any(t, ["DSI", "ตำรวจ", "สรรพากร", "ปปง", "อายัด", "คดี", "หมายเรียก", "การไฟฟ้า", "ไปรษณีย์ไทย", "กสทช"]):
        return "relabel", "impersonation_authority"

    if _has_any(t, ["ลงทุน", "forex", "crypto", "ทองคำดิจิทัล", "กำไรวันละ", "ผลตอบแทน", "trader"]):
        return "relabel", "investment_scam"

    if _has_any(t, ["สินเชื่อ", "เงินกู้", "อนุมัติ", "ไม่ต้องค้ำ", "วงเงิน"]) and not _has_any(t, ["ผิดปกติ", "ระงับ"]):
        return "relabel", "loan_offer"

    if _has_any(t, ["ยินดีด้วย", "ขอแสดงความยินดี", "โชคดี", "ได้รับรางวัล", "voucher", "iPhone", "Tesla", "ลุ้น"]):
        return "relabel", "prize_scam"

    if _has_any(t, ["ขอยืม", "รบกวนพี่", "ขอความช่วยเหลือ", "แม่ป่วย", "ติดด่าน", "รถเสีย"]):
        return "relabel", "borrowing_scam"

    if _has_any(t, ["บัญชี", "บัตรเครดิต", "ถูกแฮก", "ถูกล็อค", "ถูกระงับ", "ถูกอายัด", "ค้างชำระ", "ยอดผิดปกติ"]) and has_action_link:
        return "relabel", "financial_fraud"

    if has_action_link and _has_any(t, ["ยืนยันตัวตน", "verify", "ความปลอดภัย", "Security"]):
        return "relabel", "phishing_link"

    if has_action_link:
        # มี link แต่ไม่มี signal ชัด — น่าจะ phishing แบบทั่วไป
        return "relabel", "phishing_link"

    # romance pattern: short greeting + no link
    if _has_any(t, ["สวัสดี", "hello", "hi", "เป็นอย่างไร", "ทำอะไรอยู่"]) and len(t) < 80 and not has_action_link:
        return "relabel", "romance_scam"

    # ไม่มี rule fire → ส่งต่อ LLM
    return "unknown", "no_rule_fired"


# ─────────────────────────────────────────────────────────────────
# Typhoon LLM verification
# ─────────────────────────────────────────────────────────────────

LLM_SYSTEM = (
    "คุณเป็น AI ผู้เชี่ยวชาญการจัดประเภท SMS มิจฉาชีพไทย "
    "วิเคราะห์ข้อความที่ user ส่งมา แล้วตอบ JSON เท่านั้น "
    "ไม่อธิบายเพิ่ม"
)

LLM_USER_TEMPLATE = """\
ข้อความ: "{text}"

ตัดสินใจว่า:
1. เป็น SMS scam จริงหรือไม่
2. ถ้าเป็น scam อยู่หมวดไหน

ตอบเป็น JSON:
{{"action": "relabel" | "keep_other" | "remove" | "keep_safe",
  "category": "phishing_link" | "financial_fraud" | "impersonation_authority" | "prize_scam" | "loan_offer" | "investment_scam" | "borrowing_scam" | "romance_scam" | "other" | null,
  "reason": "เหตุผลสั้น ๆ"}}

แนวทาง:
- relabel = scam จริง แต่หมวดผิด (ระบุหมวดที่ถูกใน category)
- keep_other = scam จริง แต่ไม่อยู่ใน 8 หมวด (category="other")
- remove = ไม่ใช่ scam (เช่น โปรโมชั่น, ทักทาย, fragment) — ลบจาก training set
- keep_safe = เป็นข้อความปกติ ควรเป็น safe verdict (ไม่ใช่ scam)"""


def llm_classify(client: OpenAI, text: str, retries: int = 2) -> dict | None:
    for attempt in range(retries):
        try:
            resp = client.chat.completions.create(
                model=Settings.TYPHOON_MODEL,
                messages=[
                    {"role": "system", "content": LLM_SYSTEM},
                    {"role": "user", "content": LLM_USER_TEMPLATE.format(text=text)},
                ],
                max_tokens=200,
                temperature=0.2,
            )
            raw = resp.choices[0].message.content or ""
            # extract JSON
            start = raw.find("{")
            end = raw.rfind("}") + 1
            if start == -1:
                continue
            data = json.loads(raw[start:end])
            action = data.get("action")
            category = data.get("category")
            if action not in ("relabel", "keep_other", "remove", "keep_safe"):
                continue
            if action == "relabel" and category not in VALID_CATEGORIES:
                continue
            return {"action": action, "category": category, "reason": data.get("reason", "")}
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(1.5)
                continue
            print(f"  LLM error: {type(e).__name__}: {e}")
    return None


# ─────────────────────────────────────────────────────────────────
# Main flow
# ─────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true",
                       help="apply proposals กลับเข้า corpus (default = dry-run)")
    parser.add_argument("--llm-max", type=int, default=100,
                       help="จำกัด LLM calls เพื่อคุม cost (default 100)")
    args = parser.parse_args()

    print(f"Loading corpus ...")
    all_records = []
    with CORPUS_PATH.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                all_records.append(json.loads(line))

    other_records = [r for r in all_records if r.get("category") == "other" and r["verdict"] == "danger"]
    print(f"Total records: {len(all_records)}")
    print(f"'other' (danger) records: {len(other_records)}")

    # Step 1: rules
    print(f"\n=== Step 1: rule-based classification ===")
    proposals = []
    unknown_indices = []
    for i, r in enumerate(other_records):
        action, info = rule_classify(r["text"])
        if action == "unknown":
            unknown_indices.append(i)
        else:
            proposals.append({
                "id": r["id"],
                "text": r["text"],
                "original_category": "other",
                "method": "rule",
                "action": action,
                "new_category": info if action == "relabel" else None,
                "reason": info,
            })

    print(f"  rule-based decisions: {len(proposals)}")
    print(f"  unknown (need LLM): {len(unknown_indices)}")

    # Step 2: LLM for unknowns
    if unknown_indices and Settings.TYPHOON_API_KEY:
        print(f"\n=== Step 2: LLM verification (Typhoon) — up to {args.llm_max} calls ===")
        client = OpenAI(api_key=Settings.TYPHOON_API_KEY, base_url=Settings.TYPHOON_BASE_URL)
        llm_processed = 0
        for i in unknown_indices:
            if llm_processed >= args.llm_max:
                # ใส่ keep_other ที่เหลือ
                r = other_records[i]
                proposals.append({
                    "id": r["id"], "text": r["text"], "original_category": "other",
                    "method": "fallback_keep", "action": "keep_other",
                    "new_category": "other", "reason": "llm_budget_exhausted",
                })
                continue
            r = other_records[i]
            result = llm_classify(client, r["text"])
            llm_processed += 1
            if result is None:
                proposals.append({
                    "id": r["id"], "text": r["text"], "original_category": "other",
                    "method": "llm_failed", "action": "keep_other",
                    "new_category": "other", "reason": "llm_call_failed",
                })
                continue
            proposals.append({
                "id": r["id"], "text": r["text"], "original_category": "other",
                "method": "llm",
                "action": result["action"],
                "new_category": result.get("category") if result["action"] == "relabel" else (
                    "other" if result["action"] == "keep_other" else None
                ),
                "reason": result.get("reason", ""),
            })
            if llm_processed % 10 == 0:
                print(f"  LLM processed {llm_processed}/{min(len(unknown_indices), args.llm_max)}")
            time.sleep(0.3)
        print(f"  LLM done: {llm_processed} calls")

    # Step 3: summary
    print(f"\n=== Proposal summary ===")
    by_action = Counter(p["action"] for p in proposals)
    for a, c in by_action.most_common():
        print(f"  {a}: {c}")

    by_new_cat = Counter(p["new_category"] for p in proposals if p["action"] == "relabel")
    if by_new_cat:
        print(f"\n  Relabels by new category:")
        for cat, c in by_new_cat.most_common():
            print(f"    → {cat}: {c}")

    by_method = Counter(p["method"] for p in proposals)
    print(f"\n  By method: {dict(by_method)}")

    # Save proposals
    PROPOSAL_PATH.parent.mkdir(parents=True, exist_ok=True)
    with PROPOSAL_PATH.open("w", encoding="utf-8") as f:
        for p in proposals:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")
    print(f"\nProposals saved to {PROPOSAL_PATH}")

    # Sample 10 random
    print(f"\n=== Sample proposals (10 random) ===")
    import random
    random.seed(42)
    for p in random.sample(proposals, min(10, len(proposals))):
        action = p["action"]
        new_cat = p.get("new_category") or "-"
        text = p["text"][:90]
        print(f"  [{action}/{new_cat}] {text}")

    # Step 4: apply if requested
    if args.apply:
        print(f"\n=== Step 4: APPLYING to corpus ===")
        # backup
        if not BACKUP_PATH.exists():
            with CORPUS_PATH.open("rb") as src, BACKUP_PATH.open("wb") as dst:
                dst.write(src.read())
            print(f"  Backup saved to {BACKUP_PATH}")

        prop_by_id = {p["id"]: p for p in proposals}
        new_records = []
        n_relabeled = n_removed = n_kept = 0
        for r in all_records:
            p = prop_by_id.get(r["id"])
            if p is None:
                new_records.append(r)
                continue
            if p["action"] == "remove":
                n_removed += 1
                continue
            if p["action"] == "keep_safe":
                r["verdict"] = "safe"
                r["category"] = None
                r["annotator_notes"] = (r.get("annotator_notes") or "") + " | relabeled_to_safe"
                new_records.append(r)
                n_relabeled += 1
                continue
            if p["action"] == "relabel":
                old = r["category"]
                r["category"] = p["new_category"]
                r["annotator_notes"] = (r.get("annotator_notes") or "") + f" | relabeled_from_other_to_{p['new_category']}"
                n_relabeled += 1
            elif p["action"] == "keep_other":
                n_kept += 1
            new_records.append(r)

        with CORPUS_PATH.open("w", encoding="utf-8") as f:
            for r in new_records:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        print(f"  Relabeled: {n_relabeled}")
        print(f"  Removed:   {n_removed}")
        print(f"  Kept as other: {n_kept}")
        print(f"  New corpus size: {len(new_records)} (was {len(all_records)})")
    else:
        print(f"\n--apply not set — corpus unchanged. Re-run with --apply to commit.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
