"""
Seed corpus — verbatim Thai scam SMS text extracted from public sources

ทุก record มี source URL ที่ verify ได้ และ extraction_method ระบุชัด
รัน script นี้แล้วจะ append เข้า data/raw/scam_corpus.jsonl

หลักการ:
- ใส่เฉพาะข้อความที่ verify ได้ว่า quote ตรงจาก source จริง
- ถ้า source ถูกลบ → record ยังอยู่ แต่ scrape ใหม่จะ fail (audit-trail ตามได้)
- ใช้ deterministic ID (sha1 of text) — re-run ได้ไม่ซ้ำ
"""

from pathlib import Path

from ml.scrape.schema import (
    ScamRecord,
    SourceAttribution,
    append_records,
    make_id,
    now_iso,
)


OUTPUT_PATH = Path("data/raw/scam_corpus.jsonl")


# ─────────────────────────────────────────────────────────────────
# Source 1: Police Region 9 — ระวังภัย SMS มิจฉาชีพ กับกลโกงรูปแบบใหม่
# ─────────────────────────────────────────────────────────────────
POLICE9_URL = "https://www.police9.go.th/ระวังภัย-sms-มิจฉาชีพ-กับกล/"
POLICE9_SOURCE_NAME = "Police Region 9 (Thai Royal Police)"

POLICE9_EXAMPLES: list[tuple[str, str]] = [
    # (text, category)
    (
        "บัญชีของคุณถูกระงับการใช้งาน กรุณาคลิกลิงก์เพื่อยืนยันตัวตน",
        "phishing_link",
    ),
    (
        "คุณมีคดีความ กรุณาคลิกลิงก์เพื่อตรวจสอบรายละเอียด",
        "impersonation_authority",
    ),
    (
        "รับเงินคืน ค่าไฟฟ้า กรุณาคลิกลิงก์เพื่อตรวจสอบรายละเอียด",
        "impersonation_authority",
    ),
    (
        "คุณได้รับรางวัล iPhone 14 กรุณาคลิกลิงก์เพื่อรับรางวัล",
        "prize_scam",
    ),
]


# ─────────────────────────────────────────────────────────────────
# Source 2: Ngern Tid Lor — รู้ทันเหลี่ยมโจรตัวร้าย
# ─────────────────────────────────────────────────────────────────
TIDLOR_URL = "https://www.tidlor.com/th/article/lifestyle/general/how-to-avoid-phishing-scams"
TIDLOR_SOURCE_NAME = "Ngern Tid Lor (financial education content)"

TIDLOR_EXAMPLES: list[tuple[str, str]] = [
    (
        "คุณเป็นผู้โชคดีได้รับวงเงินกู้จากธนาคารแห่งประเทศไทย (ธปท.) 200,000 บาท",
        "loan_offer",
    ),
    (
        "เงินของคุณถูกถอนออกไปจากบัญชี 50,000 บาท",
        "financial_fraud",
    ),
    (
        "คุณมียอดใช้ผ่านบัตรเครดิต 100,000 บาท",
        "financial_fraud",
    ),
    (
        "ยินดีด้วย! คุณคือผู้โชคดีได้รับเงินกู้สินเชื่อโควิดแบบฟรี ๆ 40,000 บาท คลิกลิงก์เพื่อกรอกข้อมูลเลย",
        "loan_offer",
    ),
    (
        "บัตรเครดิตของคุณกำลังจะถูกโจรกรรม รีบกรอกข้อมูลยืนยันตัวตนผ่านลิงก์เพื่ออายัด",
        "phishing_link",
    ),
]


# ─────────────────────────────────────────────────────────────────
# Source 3: Anti Fake News Center — รวมข้อความ SMS ที่มิจฉาชีพมักแนบลิงก์
# ─────────────────────────────────────────────────────────────────
AFNC_URL = "https://www.antifakenewscenter.com/คลังความรู้/รวมข้อความ-sms-ที่มิจฉาชีพมักแนบลิงก์หลอกเหยื่อ/"
AFNC_SOURCE_NAME = "Anti Fake News Center Thailand (DES Ministry)"

AFNC_EXAMPLES: list[tuple[str, str]] = [
    (
        "ธนาคารปรับปรุงระบบ โปรดอัปเดตข้อมูลตามลิงก์",
        "phishing_link",
    ),
    (
        "ยังไม่ชำระค่าบริการ",
        "financial_fraud",
    ),
    (
        "บัญชีเงินฝากโดนแฮก",
        "phishing_link",
    ),
]


# ─────────────────────────────────────────────────────────────────
# Source 4: Bangkok Biznews — 8 มุกยอดฮิตมิจฉาชีพ
# ─────────────────────────────────────────────────────────────────
BBN_URL = "https://www.bangkokbiznews.com/business/962824"
BBN_SOURCE_NAME = "Bangkok Biznews — 8 มุกยอดฮิตมิจฉาชีพ"

BBN_EXAMPLES: list[tuple[str, str]] = [
    (
        "เงินเดือน 2,000 บาท โอนเข้าบัญชีเรียบร้อย",
        "financial_fraud",
    ),
    (
        "ยินดีด้วยคุณได้รับเงินรางวัล 20,000 บาท",
        "prize_scam",
    ),
    (
        "โครงการเราชนะ ลงทะเบียนเพิ่มข้อมูลที่ลิงก์",
        "impersonation_authority",
    ),
]


# ─────────────────────────────────────────────────────────────────
# Build records + save
# ─────────────────────────────────────────────────────────────────

def build_seed_records() -> list[ScamRecord]:
    """รวม seed records จากทุก source"""
    records: list[ScamRecord] = []
    ts = now_iso()

    source_groups = [
        ("police9", POLICE9_URL, POLICE9_SOURCE_NAME, POLICE9_EXAMPLES),
        ("tidlor", TIDLOR_URL, TIDLOR_SOURCE_NAME, TIDLOR_EXAMPLES),
        ("afnc", AFNC_URL, AFNC_SOURCE_NAME, AFNC_EXAMPLES),
        ("bbn", BBN_URL, BBN_SOURCE_NAME, BBN_EXAMPLES),
    ]

    for slug, url, name, examples in source_groups:
        attribution = SourceAttribution(
            name=name,
            url=url,
            scraped_at=ts,
            extraction_method="verbatim_html",
            license="fair_use_academic",
            license_note="fair use - academic research, source URL preserved for verification",
        )
        for text, category in examples:
            records.append(
                ScamRecord(
                    id=make_id(slug, text),
                    text=text,
                    verdict="danger",
                    category=category,
                    source=attribution,
                    tier="A",  # Thai verbatim จากเว็บหน่วยงาน/สื่อ — มี URL ตรวจได้ (CLAUDE.md 10.2)
                )
            )
    return records


def main() -> None:
    records = build_seed_records()
    added = append_records(records, OUTPUT_PATH)
    print(f"Seed corpus: {len(records)} records prepared, {added} new appended to {OUTPUT_PATH}")
    print(f"Total now: {sum(1 for _ in OUTPUT_PATH.open(encoding='utf-8'))} records")


if __name__ == "__main__":
    main()
