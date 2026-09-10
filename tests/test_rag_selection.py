"""
RAG selection rules (Data v2 — CLAUDE.md 10.2 / 10.7)

- เฉพาะ tier ที่ is_usable_for(rag) และไม่ใช่ narrative ค่าต่ำ (digest รายชื่อเพจ / ข่าวต่างประเทศ)
- context ที่ส่ง Claude มีแหล่ง+วันที่ ไม่มี status เก่า
"""

from ml.scrape.schema import is_usable_for
from ml.scrape.wp_news import is_low_value_narrative
from scripts.setup_rag import select_rag_records


def _rec(tier, text, name="Anti Fake News Center", review=None):
    return {
        "id": f"{tier}-{abs(hash(text))}",
        "text": text,
        "verdict": "danger",
        "category": "phishing_link",
        "tier": tier,
        "source": {"name": name, "url": "https://x", "published_date": "2026-01-01"},
        "review": review,
    }


def test_low_value_digest_and_foreign_news_flagged():
    assert is_low_value_narrative(_rec("N", "ตัดวงจร #อาชญากรรมออนไลน์ 22 กรกฎาคม 2568\nเพจปลอม..."))
    assert is_low_value_narrative(_rec("N", "FBI เตือนการโจมตี Salesforce\n..."))
    assert is_low_value_narrative(_rec("N", "พบการโจมตีผ่าน Wi-Fi โรงแรม ขโมยบัญชี Microsoft 365\n..."))
    assert not is_low_value_narrative(_rec("N", "กรมการขนส่งทางบก ส่ง SMS แจ้งชำระใบสั่ง\n..."))
    assert not is_low_value_narrative(_rec("A", "ตัดวงจร"))  # ใช้กับ tier N เท่านั้น


def test_tier_rules_for_rag():
    assert is_usable_for(_rec("A", "x"), "rag")
    assert is_usable_for(_rec("N", "x"), "rag")
    assert not is_usable_for(_rec("B", "x"), "rag")
    assert not is_usable_for(_rec("C", "x", review={"status": "approved"}), "rag")


def test_select_rag_records_filters():
    records = [
        _rec("A", "scam จริง"),
        _rec("N", "บทความเคสเฉพาะ\nเนื้อหา"),
        _rec("N", "ตัดวงจร #อาชญากรรมออนไลน์ 1 มกราคม\nรายชื่อเพจ"),
        _rec("B", "translated"),
        _rec("C", "synthetic", review={"status": "pending_review"}),
        _rec("S", "wisesight text", name="PyThaiNLP Wisesight Sentiment (CC0)"),
    ]
    selected, skipped = select_rag_records(records)
    assert [r["text"][:6] for r in selected] == ["scam จ", "บทความ"]
    assert skipped == {"tier_rule": 2, "wisesight": 1, "low_value_narrative": 1}


def test_rag_context_has_source_and_date():
    from app.services.rag_service import build_rag_context

    ctx = build_rag_context([{
        "input_text": "กรมการขนส่งทางบก ส่ง SMS แจ้งชำระใบสั่ง",
        "scam_category": "phishing_link",
        "source_name": "Anti Fake News Center Thailand",
        "published_date": "2026-08-25",
        "similarity": 0.8,
    }])
    assert "แหล่ง: Anti Fake News Center Thailand (2026-08-25)" in ctx
    assert "สถานะ" not in ctx
