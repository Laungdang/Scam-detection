"""
Pattern service — lexicon scan เป็น evidence ไม่ใช่ verdict (CLAUDE.md 2.1, 5.2)

เคสหลักที่ต้องผ่าน: "ด่วน" คำเดียวในข้อความปกติ ต้องรายงานแค่มิติ urgency
ไม่ใช่ "เร่งให้โอนเงิน" และต้องบอกชัดว่าไม่พบ money/link/credential
"""

from app.evidence.pattern_evidence import PatternEvidence, collect_patterns
from app.services.pattern_service import (
    extract_unique_pattern_names,
    find_matching_patterns,
    format_evidence,
    load_lexicon,
    scan_text,
)


def _found(text: str) -> dict[str, object]:
    return {m.dimension: m for m in scan_text(text) if m.has_hits}


# ─────────────────────────────────────────────────────────────
# Lexicon integrity
# ─────────────────────────────────────────────────────────────

def test_lexicon_loads_with_expected_dimensions():
    lex = load_lexicon()
    keys = lex.dimension_keys
    for required in ("urgency", "money_request", "credential_request", "link_action", "authority_claim", "threat"):
        assert required in keys
    assert all(d.terms or d.regexes for d in lex.dimensions), "ทุกมิติต้องมี term หรือ regex"


def test_lexicon_has_no_decision_fields():
    """ไฟล์ lexicon ห้ามมี verdict/weight/severity — ไม่งั้นกลายเป็น decision rule"""
    import yaml
    raw = yaml.safe_load(open("data/lexicon/scam_lexicon.yaml", encoding="utf-8"))
    for d in raw["dimensions"]:
        for forbidden in ("verdict", "weight", "severity", "status", "score"):
            assert forbidden not in d, f"dimension {d['key']} มี field ต้องห้าม: {forbidden}"


# ─────────────────────────────────────────────────────────────
# "ด่วน" ในบริบทปกติ
# ─────────────────────────────────────────────────────────────

def test_urgent_only_benign_messages_report_only_urgency():
    for text in [
        "ส่งงานด่วนนะครับ พรุ่งนี้เช้าอาจารย์จะตรวจ",
        "ด่วนมาก ขอเลื่อนประชุมเป็นบ่ายสองนะ",
    ]:
        found = _found(text)
        assert "urgency" in found, text
        assert "ด่วน" in found["urgency"].terms_found
        for dim in ("money_request", "credential_request", "link_action", "threat"):
            assert dim not in found, f"{text!r} ไม่ควรติด {dim}"


def test_flash_sale_is_urgency_plus_maybe_reward_but_no_request():
    found = _found("ด่วน! Flash Sale ลด 50% วันนี้วันเดียว ที่ Shopee")
    assert "urgency" in found
    assert "money_request" not in found
    assert "credential_request" not in found
    assert "link_action" not in found


def test_word_boundary_no_substring_false_positive():
    """ตัดคำแล้ว: 'รถด่วน' ไม่ใช่ 'ด่วน', 'ถูกมากกว่า' ไม่ใช่ 'ถูกมาก'"""
    assert "urgency" not in _found("รถด่วนขบวนนี้ออกกี่โมง")


def test_scan_never_reports_pattern_name_that_interprets():
    """ชื่อที่ส่งต่อไปต้องเป็น label ของมิติ ไม่ใช่การตีความแบบเดิม"""
    for m in scan_text("ด่วน โอนเลย"):
        assert m.label_th != "เร่งให้โอนเงิน"


# ─────────────────────────────────────────────────────────────
# Scam ที่มีหลายมิติ co-occur
# ─────────────────────────────────────────────────────────────

def test_phishing_message_hits_multiple_dimensions():
    text = "บัญชีของคุณถูกระงับ กรุณายืนยันตัวตนด่วนที่ลิงก์นี้ http://scb-verify.xyz"
    found = _found(text)
    assert "urgency" in found
    assert "threat" in found
    assert "credential_request" in found
    assert "link_action" in found
    assert "url" in found["link_action"].regex_hits
    assert "suspicious_tld" in found["link_action"].regex_hits


def test_investment_return_rate_regex():
    found = _found("ผลตอบแทน 30% ต่อเดือน รับประกัน")
    assert "financial_offer" in found
    assert "return_rate" in found["financial_offer"].regex_hits


# ─────────────────────────────────────────────────────────────
# PII ไม่หลุดผ่าน evidence
# ─────────────────────────────────────────────────────────────

def test_regex_hits_do_not_leak_matched_text():
    text = "โอนเข้าบัญชี 123-4-56789-0 จำนวน 5,000 บาท"
    matches = scan_text(text)
    evidence = format_evidence(matches)
    money = next(m for m in matches if m.dimension == "money_request")
    amount = next(m for m in matches if m.dimension == "amount_mention")
    assert "bank_account_format" in money.regex_hits
    assert "money_amount" in amount.regex_hits  # จำนวนเงินเป็นมิติแยก (ค่าจ้าง/ราคา ≠ การขอ)
    assert "123-4-56789-0" not in evidence
    assert "5,000" not in evidence


def test_wage_amount_is_not_money_request():
    """'ชั่วโมงละ 70 บาท' = ค่าจ้าง ไม่ใช่การขอเงิน — ห้ามเปิด RAG จากจำนวนเงินอย่างเดียว (kaggle_tu รอบ 2)"""
    from app.engines.qa_engine import should_use_rag
    from app.evidence.pattern_evidence import collect_patterns

    ev = collect_patterns(None, "text", "ร้านกาแฟแถวรังสิตรับพาร์ทไทม์ ชั่วโมงละ 70 บาท มีสัมภาษณ์หน้าร้าน")
    assert "money_request" not in ev.matched_pattern_names
    assert "amount_mention" in ev.matched_pattern_names
    assert not should_use_rag("text", ev, False)


def test_elongation_and_student_context_terms():
    found = _found("รุ่นพี่ฝากบอกให้โอนค่าชีทด่วนนน ไม่งั้นหมดสิทธิ์นะะะ")
    assert "urgency" in found and "ด่วน" in found["urgency"].terms_found
    # guideline v1.1 §3 / Q7: "หมดสิทธิ์" = scarcity (urgency) ไม่ใช่การขู่ (threat)
    assert "หมดสิทธิ์" in found["urgency"].terms_found
    assert "consequence_if_not" in found["urgency"].regex_hits
    assert "threat" not in found
    assert "borrowing_pretext" in found and "ฝากบอก" in found["borrowing_pretext"].terms_found
    assert "ค่าชีท" in found["money_request"].terms_found


def test_bracketed_channel_and_third_party_account():
    assert "inbox" in _found("ของดี (inbox ได้)")["channel_shift"].terms_found
    found = _found("บัญชีนี้ของแฟนเราเอง ปลอดภัยแน่นอน โอนมาเลย")
    assert "third_party_account" in found["money_request"].regex_hits


def test_inbound_payment_and_link_without_url_are_reported_as_facts():
    from app.engines.qa_engine import should_use_rag
    from app.evidence.pattern_evidence import collect_patterns

    ev = collect_patterns(None, "text", "ขอเลขบชพร้อมเพย์หน่อยคับ จะโอนค่าชีท")
    assert "inbound_payment_offer" in ev.matched_pattern_names
    # money_request ยังพบ ("โอน", "พร้อมเพย์") → RAG เปิดได้ — ทิศทางเงินเป็นข้อเท็จจริงให้ Claude ชั่ง
    ev2 = collect_patterns(None, "text", "มีลิงก์ให้กรอกข้อมูลเพื่อรับสิทธิ์ ลองเช็คก่อนนะ")
    assert "พูดถึงลิงก์แต่ไม่พบ URL" in ev2.to_evidence_text()
    ev3 = collect_patterns(None, "text", "กดลิงก์นี้ http://scb-verify.xyz")
    assert "พูดถึงลิงก์แต่ไม่พบ URL" not in ev3.to_evidence_text()
    assert should_use_rag("text", ev2, False)
    found2 = _found("แอดมินคณะแจ้ง ค่าจองสิทธิ์สอบ โอนมาที่ พร้อมเพย์ 0812345678 ภายในวันนี้")
    assert "authority_claim" in found2 and "แอดมินคณะ" in found2["authority_claim"].terms_found
    assert "promptpay_phone" in found2["money_request"].regex_hits


# ─────────────────────────────────────────────────────────────
# Evidence text
# ─────────────────────────────────────────────────────────────

def test_format_evidence_lists_found_and_missing():
    text = "ส่งงานด่วนนะครับ"
    out = format_evidence(scan_text(text))
    assert 'เร่งให้รีบตัดสินใจ: "ด่วน"' in out
    assert "ไม่พบ:" in out
    assert "ขอให้โอน/จ่ายเงิน" in out  # อยู่ในรายการ "ไม่พบ"
    for forbidden in ("น่าสงสัย", "suspicious", "ผลเบื้องต้น", "verdict", "caution", "danger"):
        assert forbidden not in out


def test_format_evidence_empty_text():
    out = format_evidence(scan_text(""))
    assert "ไม่พบคำสัญญาณ" in out


def test_pattern_evidence_dataclass():
    ev = collect_patterns(None, "text", "ส่งงานด่วนนะครับ")
    assert isinstance(ev, PatternEvidence)
    assert ev.has_matches
    assert ev.matched_pattern_names == ["urgency"]
    assert "ด่วน" in ev.terms_found
    assert "ด่วน" in ev.to_evidence_text()


def test_pattern_evidence_skips_non_text_input():
    ev = collect_patterns(None, "phone", "0812345678")
    assert not ev.has_matches
    assert "ไม่ได้สแกน" in ev.to_evidence_text()


# ─────────────────────────────────────────────────────────────
# Legacy API compat
# ─────────────────────────────────────────────────────────────

def test_legacy_find_matching_patterns_shape():
    matches = find_matching_patterns(None, "รีบโอนเลย ด่วน")
    assert matches, "ต้องพบอย่างน้อย 1 term"
    assert {"pattern_name", "keyword", "description"} <= set(matches[0].keys())
    names = extract_unique_pattern_names(matches)
    assert "เร่งให้รีบตัดสินใจ" in names
    assert "ขอให้โอน/จ่ายเงิน" in names


def test_legacy_find_matching_patterns_empty():
    assert find_matching_patterns(None, "") == []
