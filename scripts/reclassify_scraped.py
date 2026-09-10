"""
Reclassify scraped rows ใน Excel ด้วย Claude Haiku
รัน: python -m scripts.reclassify_scraped
"""
import json
import os
import sys
import time

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = open(sys.stdout.fileno(), mode="w", encoding="utf-8", buffering=1)

import anthropic
import pandas as pd

from app.config.settings import Settings

XLSX_PATH = os.getenv("RAG_XLSX_PATH", "C:/Users/laung/Downloads/scam_dataset_v3_fixed.xlsx")

SCAM_CATEGORIES = {
    "investment_fraud": [
        "Deepfake / ปลอมบุคคลมีชื่อเสียง / AI Trading ปลอม",
        "Pump-and-Dump crypto / ชักชวนผ่าน Telegram",
        "ปลอมใบอนุญาต ก.ล.ต. / ชื่อบัญชีเป็นบุคคลธรรมดา",
        "เพจ Social Media ปลอม / ผลตอบแทนสูงผิดปกติ",
        "รับประกันผลตอบแทนสูงผิดปกติ / Forex ปลอม",
    ],
    "romance_pig_butcher": [
        "Pig Butchering / Romance+Investment combo",
        "Romance Scam / ตัวตนปลอม / ขอเงินฉุกเฉิน",
        "Fake Trading Platform / Pig Butchering",
        "Pig Butchering Scam / Romance+Investment",
    ],
    "employment_scam": [
        "งาน Part-time ปลอม / ต้องจ่ายเงินก่อน",
        "งานต่างประเทศปลอม / Scam Center เมียนมา",
        "บริษัทจัดหางานปลอม / ภารกิจออนไลน์ / โอนก่อน",
        "ประกาศงานปลอม / ขอข้อมูลส่วนตัว / ขอ PIN",
    ],
    "loan_scam": [
        "สินเชื่อด่วนปลอม / ค่าธรรมเนียมก่อนได้เงิน",
        "LINE OA ปลอมธนาคาร / ค่าธรรมเนียมก่อนได้เงิน",
    ],
    "shopping_scam": [
        "ขายบัตรคอนเสิร์ตปลอม / โอนมัดจำแล้วหนี",
        "สินค้าแบรนด์เนมปลอม / โอนก่อนแล้วหนี",
        "รีวิวปลอม / สินค้าไม่ตรงปก / ร้านใหม่",
        "ร้านออนไลน์ใหม่ / ราคาถูกผิดปกติ / โอนก่อน",
        "เพจปลอมเลียนแบบแบรนด์ / โอนก่อนได้ของ",
    ],
    "call_center": [
        "อ้างเป็น INTERPOL / ขอเงินประกันตัว",
        "อ้างเป็น DSI / ขู่จับ / บัญชีม้า",
        "อ้างเป็น กสทช. / เร่งรัดด้วยการขู่ระงับเบอร์",
        "อ้างเป็นกรมสรรพากร / เร่งรัดชำระภาษีปลอม",
        "อ้างเป็นตำรวจไซเบอร์ / ส่งลิงก์ติดตั้งแอปดูดเงิน",
        "อ้างเป็นตำรวจ / ขู่ให้โอนเงินหลบคดี",
        "อ้างเป็นพนักงานธนาคาร / ขอ OTP",
        "ปลอมนโยบายรัฐ Digital Wallet / แอปดูดเงิน",
        "ปลอมหน่วยงานรัฐ / Phishing ขอข้อมูลบัญชี",
    ],
    "sms_phishing": [
        "SMS Spoofing / ลิงก์ปลอมเลียนแบบธนาคาร",
        "SMS Spoofing เข้ากล่อง SMS จริง / Phishing",
        "SMS ปลอมจากบริษัทขนส่ง / Smishing",
        "SMS ปลอมจากบริษัทขนส่ง / แอปดูดเงิน",
        "URL ปลอมธนาคารออมสิน / Phishing",
        "แอปปลอม / ขอข้อมูล Internet Banking",
        "Domain ปลอมเลียนแบบธนาคาร / Phishing",
    ],
}

SYSTEM_PROMPT = (
    'จำแนกข่าวมิจฉาชีพ ตอบเฉพาะ JSON: {"scam_category": "...", "matched_pattern": "..."}\n'
    + "scam_category: " + ", ".join(SCAM_CATEGORIES.keys()) + "\n"
    + "matched_pattern ตาม category:\n"
    + "\n".join(f"{c}: " + " | ".join(pats) for c, pats in SCAM_CATEGORIES.items())
)


def parse_claude_json(raw: str) -> dict:
    text = raw.strip()
    if "```" in text:
        parts = text.split("```")
        text = parts[1] if len(parts) > 1 else text
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    start = text.find("{")
    end = text.rfind("}") + 1
    if start == -1:
        return {}
    return json.loads(text[start:end])


def main():
    df = pd.read_excel(XLSX_PATH)
    mask = df["sample_id"].astype(str).str.startswith("scraped_")
    scraped_idx = df[mask].index.tolist()
    print(f"Reclassify {len(scraped_idx)} scraped rows ด้วย Claude Haiku...")
    print(f"ประมาณ {len(scraped_idx) * 0.05 / 60:.1f} นาที\n")

    client = anthropic.Anthropic(api_key=Settings.CLAUDE_API_KEY)
    updated = 0
    errors = 0

    for i, idx in enumerate(scraped_idx):
        text = str(df.at[idx, "input_text"])[:400]
        try:
            msg = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=100,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": text}],
            )
            data = parse_claude_json(msg.content[0].text)
            cat = data.get("scam_category", "sms_phishing")
            pat = data.get("matched_pattern", "")

            if cat not in SCAM_CATEGORIES:
                cat = "sms_phishing"
            if pat not in SCAM_CATEGORIES.get(cat, []):
                pat = SCAM_CATEGORIES[cat][0]

            df.at[idx, "scam_category"] = cat
            df.at[idx, "matched_pattern"] = pat
            updated += 1
        except Exception as ex:
            errors += 1
            print(f"  ERROR idx={idx}: {ex}")

        if (i + 1) % 50 == 0:
            # save checkpoint ทุก 50 rows
            df.to_excel(XLSX_PATH, index=False)
            print(f"  checkpoint {i + 1}/{len(scraped_idx)} (errors: {errors})")
            time.sleep(1)

    # save final
    df.to_excel(XLSX_PATH, index=False)
    print(f"\nเสร็จสิ้น! updated={updated}, errors={errors}")

    from collections import Counter
    cats = Counter(df[mask]["scam_category"].tolist())
    print("\nDistribution หลัง reclassify:")
    for k, v in cats.most_common():
        print(f"  {v:3d}  {k}")

    print("\nขั้นตอนต่อไป:")
    print("  python -m scripts.setup_rag")


if __name__ == "__main__":
    main()
