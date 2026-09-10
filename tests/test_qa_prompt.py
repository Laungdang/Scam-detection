"""
Q&A prompt / decision-point tests (CLAUDE.md 2.3, 5.2, 8)

- prompt ที่ส่ง Claude ต้องไม่มีคำตัดสินล่วงหน้า
- RAG context ต้องไม่มี status ของเคสเก่า
- verdict ของ Claude ห้ามถูก override/fallback ใน code
"""

import pytest

from app.engines.qa_engine import QAAnalysisError, resolve_claude_verdict
from app.services.ai_service import SYSTEM_PROMPT, build_user_message
from app.services.pattern_service import format_evidence, scan_text
from app.services.rag_service import build_rag_context


FORBIDDEN_IN_EVIDENCE = ("ผลเบื้องต้น", "ระบบประเมิน", "preliminary", "suspicious", "น่าสงสัย")


def test_user_message_contains_dimension_evidence_not_labels():
    text = "ส่งงานด่วนนะครับ พรุ่งนี้เช้าอาจารย์จะตรวจ"
    ev_text = format_evidence(scan_text(text))
    msg = build_user_message(
        original_input=text,
        input_type="text",
        matched_pattern_names=["urgency"],
        blacklist_found=False,
        pattern_evidence_text=ev_text,
        history_evidence_text="ประวัติการสนทนา: ไม่มี (เป็น turn แรก)",
    )
    assert '"ด่วน"' in msg
    assert "ไม่พบ:" in msg
    assert "เร่งให้โอนเงิน" not in msg
    assert "ระบบไม่ได้ประเมินอะไรไว้ล่วงหน้า" in msg
    for w in FORBIDDEN_IN_EVIDENCE:
        assert w not in msg, f"prompt มีคำต้องห้าม: {w}"


def test_user_message_legacy_fallback_when_no_evidence_text():
    msg = build_user_message(
        original_input="x",
        input_type="text",
        matched_pattern_names=["urgency"],
        blacklist_found=False,
    )
    assert "คำสัญญาณที่พบ: urgency" in msg


def test_system_prompt_no_pattern_implies_not_safe_rule():
    """บรรทัดเดิม 'ถ้าไม่มี pattern ... → safe ได้' = อ่านกลับด้านว่า มี pattern ห้าม safe"""
    assert "ถ้าไม่มีหลักฐาน blacklist หรือ pattern matching ใดๆ" not in SYSTEM_PROMPT
    assert "ไม่ใช่คำตัดสิน" in SYSTEM_PROMPT
    assert "ไม่ต้องกลัวการตอบ safe" in SYSTEM_PROMPT


def test_system_prompt_restricts_facts_not_judgment():
    assert "ห้ามใช้ความรู้ของตัวเองหรือข้อมูลนอกเหนือจากที่ได้รับมา" not in SYSTEM_PROMPT
    assert "ใช้วิจารณญาณของคุณเอง" in SYSTEM_PROMPT
    # กฎกัน hallucinate เบอร์/เว็บ ยังต้องอยู่
    assert "ห้ามสร้าง แต่งเติม หรือเดาหมายเลขโทรศัพท์" in SYSTEM_PROMPT


def test_rag_context_has_no_legacy_status():
    ctx = build_rag_context([
        {
            "input_text": "ตัวอย่างเคส",
            "scam_category": "phishing_link",
            "result_status": "suspicious",
            "matched_pattern": "เร่งให้โอนเงิน",
            "data_source": "x",
            "similarity": 0.8,
        }
    ])
    assert "suspicious" not in ctx
    assert "สถานะ" not in ctx
    assert "เร่งให้โอนเงิน" not in ctx
    assert "phishing_link" in ctx


def test_rag_gate_requires_non_weak_dimension():
    from app.engines.qa_engine import should_use_rag
    from app.evidence.pattern_evidence import collect_patterns

    ev = lambda t: collect_patterns(None, "text", t)  # noqa: E731
    assert not should_use_rag("text", ev("ส่งงานด่วนนะครับ พรุ่งนี้เช้าอาจารย์จะตรวจ"), False)   # urgency only
    assert not should_use_rag("text", ev("ด่วน! Flash Sale ลด 50% ที่ Shopee"), False)          # urgency + brand
    assert should_use_rag("text", ev("แม่โอนเงินค่าเทอมให้ด่วนหน่อย"), False)                   # money_request
    assert should_use_rag("text", ev("บัญชีถูกระงับ ยืนยันตัวตนที่ลิงก์นี้"), False)
    assert should_use_rag("phone", ev(""), False)     # เบอร์ → ดึงเสมอ
    assert should_use_rag("text", ev("สวัสดี"), True)  # มีภาพ → ดึงเสมอ
    # ทิศทางเงินกลับด้าน (Q3): ผู้ซื้อขอเลขบัญชีผู้ขายเพื่อจ่ายให้ → ไม่ดึงเคส "ถูกขอข้อมูลบัญชี" มา anchor
    assert not should_use_rag("text", ev("ขอเลขบชพร้อมเพย์หน่อยคับ จะโอนค่าชีท"), False)
    assert should_use_rag("text", ev("ขอเลขบชพร้อมเพย์หน่อยคับ จะโอนค่าชีท line: @fakeid"), False)  # + ID ภายนอก → ดึง


@pytest.mark.parametrize("verdict", ["danger", "caution", "safe"])
def test_resolve_verdict_passthrough(verdict):
    assert resolve_claude_verdict({"verdict": verdict}) == verdict


@pytest.mark.parametrize("bad", [{}, {"verdict": ""}, {"verdict": "suspicious"}, {"verdict": None}])
def test_resolve_verdict_raises_instead_of_defaulting(bad):
    with pytest.raises(QAAnalysisError):
        resolve_claude_verdict(bad)
