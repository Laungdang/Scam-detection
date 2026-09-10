"""
Unit tests for pii_masker — PDPA compliance (CLAUDE.md Section 6.7)

Coverage requirements (Section 6.7 acceptance criteria):
- PII ฝังในประโยค
- PII หลายตัวในข้อความเดียว
- false positive (เลข 13 หลักที่ไม่ใช่บัตรประชาชน)
- checksum validation Mod 11 ของเลขบัตรประชาชน
"""

import os

import pytest

os.environ.setdefault("PII_SALT", "test_salt_for_unit_tests_only_do_not_use_in_prod")

from app.services.pii_masker import (
    MaskedResult,
    PIIMatch,
    _is_valid_thai_id,
    find_pii_in_text,
    hash_value,
    mask_field,
    mask_pii,
)


# valid Thai IDs (generated via Mod 11)
VALID_THAI_ID = "1234567890121"   # ตัวอย่างที่ผ่าน mod 11 check (จะ verify ใน test ด้านล่าง)
INVALID_THAI_ID = "1234567890123"  # checksum ไม่ผ่าน


def test_valid_thai_id_helper_passes_known_valid():
    # สร้าง Thai ID ที่ valid โดย compute checksum เอง
    base = "123456789012"
    total = sum(int(base[i]) * (13 - i) for i in range(12))
    check = (11 - total % 11) % 10
    valid = base + str(check)
    assert _is_valid_thai_id(valid) is True


def test_valid_thai_id_helper_rejects_invalid_checksum():
    assert _is_valid_thai_id(INVALID_THAI_ID) is False


def test_valid_thai_id_helper_rejects_non_13_digits():
    assert _is_valid_thai_id("12345") is False
    assert _is_valid_thai_id("12345678901234") is False


def test_valid_thai_id_helper_rejects_non_digits():
    assert _is_valid_thai_id("12345678abcde") is False


# ─────────────────────────────────────────────────────────────────
# mask_field — known field types
# ─────────────────────────────────────────────────────────────────

class TestMaskFieldThaiId:
    def test_keeps_first_and_last_digit(self):
        result = mask_field("1234567890121", "thai_id")
        assert result == "1-xxxx-xxxxx-xx-1"

    def test_handles_hyphenated_input(self):
        result = mask_field("1-2345-67890-12-1", "thai_id")
        assert result == "1-xxxx-xxxxx-xx-1"

    def test_falls_back_for_wrong_length(self):
        result = mask_field("12345", "thai_id")
        assert "*" in result
        assert "12345" not in result


class TestMaskFieldBankAccount:
    def test_keeps_last_4_digits(self):
        result = mask_field("1234567890", "bank_acct")
        assert result == "xxx-x-xx7890"

    def test_handles_hyphenated_input(self):
        result = mask_field("123-4-56789-0", "bank_acct")
        assert result == "xxx-x-xx7890"

    def test_falls_back_for_too_short(self):
        result = mask_field("12", "bank_acct")
        assert "12" not in result or "*" in result


class TestMaskFieldPhone:
    def test_strict_mode_hides_all_but_last4(self):
        result = mask_field("0812345678", "phone", "strict")
        assert result == "xxx-xxx-5678"

    def test_display_mode_keeps_first3_and_last4(self):
        result = mask_field("0812345678", "phone", "display")
        assert result == "081-xxx-5678"

    def test_handles_hyphenated(self):
        result = mask_field("081-234-5678", "phone", "display")
        assert result == "081-xxx-5678"

    def test_falls_back_for_too_short(self):
        result = mask_field("123", "phone")
        assert "123" not in result


class TestMaskFieldPerson:
    def test_thai_name(self):
        result = mask_field("สมชาย ใจดี", "person")
        assert result == "ส*** ใ***"

    def test_english_name(self):
        result = mask_field("John Smith", "person")
        assert result == "J*** S***"

    def test_single_word(self):
        result = mask_field("Madonna", "person")
        assert result == "M***"

    def test_empty(self):
        assert mask_field("", "person") == ""


class TestMaskFieldUrl:
    def test_strips_path_and_query(self):
        result = mask_field("https://scb-fake.xyz/login?token=abc", "url")
        assert result == "https://scb-fake.xyz/..."

    def test_http_scheme(self):
        result = mask_field("http://example.com/path", "url")
        assert result == "http://example.com/..."

    def test_falls_back_for_invalid_url(self):
        result = mask_field("not-a-url", "url")
        assert "not-a-url" not in result or "*" in result


# ─────────────────────────────────────────────────────────────────
# find_pii_in_text — detection ใน free text
# ─────────────────────────────────────────────────────────────────

class TestFindPiiInText:
    def test_returns_empty_when_no_pii(self):
        assert find_pii_in_text("ข้อความปกติไม่มีข้อมูลส่วนตัว") == []

    def test_returns_empty_for_empty_string(self):
        assert find_pii_in_text("") == []

    def test_detects_phone_in_sentence(self):
        matches = find_pii_in_text("โทรหาผมที่ 0812345678 นะ")
        assert len(matches) == 1
        assert matches[0].pii_type == "phone"
        assert matches[0].original == "0812345678"

    def test_detects_thai_id_with_valid_checksum_only(self):
        valid = _generate_valid_thai_id()
        text = f"เลขบัตรของฉันคือ {valid}"
        matches = find_pii_in_text(text)
        assert any(m.pii_type == "thai_id" for m in matches)

    def test_rejects_random_13_digits_as_thai_id(self):
        # เลข 13 หลักสุ่ม (false positive)
        text = "รหัส 1234567890123 ไม่ใช่บัตร"
        matches = find_pii_in_text(text)
        # ไม่ควรถูก mark เป็น thai_id (เพราะ checksum fail)
        assert not any(m.pii_type == "thai_id" for m in matches)
        # แต่อาจถูก match เป็น bank account (เลข 13 หลักก็เป็นบัญชีได้)
        assert any(m.pii_type == "bank_acct" for m in matches)

    def test_detects_url(self):
        matches = find_pii_in_text("ไปดูที่ https://example.com/page นะ")
        assert any(m.pii_type == "url" for m in matches)

    def test_detects_bank_account(self):
        matches = find_pii_in_text("โอนมาที่ 1234567890")
        assert any(m.pii_type == "bank_acct" for m in matches)

    def test_detects_multiple_pii_in_one_text(self):
        text = "โทร 0812345678 หรือโอนเงิน 1234567890 ก็ได้"
        matches = find_pii_in_text(text)
        types = {m.pii_type for m in matches}
        assert "phone" in types
        assert "bank_acct" in types

    def test_no_overlap_between_phone_and_bank(self):
        # 0812345678 เป็น phone (10 หลัก, start with 0) ไม่ใช่ bank
        matches = find_pii_in_text("0812345678")
        # ควรเป็น phone อย่างเดียว ไม่ซ้ำกับ bank
        phone_matches = [m for m in matches if m.pii_type == "phone"]
        bank_matches = [m for m in matches if m.pii_type == "bank_acct"]
        assert len(phone_matches) == 1
        assert len(bank_matches) == 0

    def test_matches_sorted_by_position(self):
        text = "0812345678 then 1234567890123"
        matches = find_pii_in_text(text)
        for i in range(len(matches) - 1):
            assert matches[i].start < matches[i + 1].start


# ─────────────────────────────────────────────────────────────────
# mask_pii — end-to-end
# ─────────────────────────────────────────────────────────────────

class TestMaskPii:
    def test_empty_text(self):
        result = mask_pii("")
        assert isinstance(result, MaskedResult)
        assert result.masked == ""
        assert result.pii_found == []
        assert result.pii_hash != ""

    def test_clean_text_unchanged(self):
        text = "สวัสดีครับ ผมขอถามเรื่อง scam"
        result = mask_pii(text)
        assert result.masked == text
        assert result.pii_found == []

    def test_masks_phone_in_sentence(self):
        result = mask_pii("โทรหาผมที่ 0812345678 นะ")
        assert "0812345678" not in result.masked
        assert "xxx-xxx-5678" in result.masked

    def test_display_mode_uses_friendly_phone(self):
        result = mask_pii("โทร 0812345678", mode="display")
        assert "081-xxx-5678" in result.masked

    def test_masks_multiple_pii(self):
        text = "โทร 0812345678 โอน 1234567890"
        result = mask_pii(text)
        assert "0812345678" not in result.masked
        assert "1234567890" not in result.masked
        assert len(result.pii_found) == 2

    def test_masks_url(self):
        result = mask_pii("เข้า https://scam-site.xyz/login?a=1")
        assert "scam-site.xyz" in result.masked
        # path ถูกตัด แต่ scheme + host ยังอยู่
        assert "/login" not in result.masked
        assert "a=1" not in result.masked

    def test_no_pii_leakage_in_output(self):
        text = "บัญชี 9876543210 โทร 0998765432"
        result = mask_pii(text)
        assert "9876543210" not in result.masked
        assert "0998765432" not in result.masked

    def test_preserves_text_structure_around_pii(self):
        result = mask_pii("โทร 0812345678 ครับ")
        assert result.masked.startswith("โทร ")
        assert result.masked.endswith(" ครับ")


# ─────────────────────────────────────────────────────────────────
# hash_value — determinism + salt
# ─────────────────────────────────────────────────────────────────

class TestHashValue:
    def test_deterministic(self):
        assert hash_value("test") == hash_value("test")

    def test_different_inputs_different_hash(self):
        assert hash_value("a") != hash_value("b")

    def test_hash_format_is_sha256_hex(self):
        h = hash_value("anything")
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)

    def test_empty_string_still_hashable(self):
        h = hash_value("")
        assert len(h) == 64

    def test_raises_when_salt_missing(self, monkeypatch):
        from app.config import settings as settings_module
        monkeypatch.setattr(settings_module.Settings, "PII_SALT", "")
        with pytest.raises(RuntimeError, match="PII_SALT"):
            hash_value("anything")


# ─────────────────────────────────────────────────────────────────
# Integration — full pipeline scenarios
# ─────────────────────────────────────────────────────────────────

class TestPdpaScenarios:
    def test_scam_message_with_pii(self):
        """scenario: user ส่ง SMS ที่มีเบอร์/บัญชีของมิจฉาชีพ"""
        sms = (
            "ยินดีด้วย! คุณได้รางวัล โอนค่าธรรมเนียม 500 บาท "
            "ไปที่ 1234567890 หรือโทร 0812345678 ภายในวันนี้"
        )
        result = mask_pii(sms)
        # PII ถูกมาส์ก
        assert "1234567890" not in result.masked
        assert "0812345678" not in result.masked
        # เนื้อความที่ไม่ใช่ PII ยังอยู่
        assert "ยินดีด้วย" in result.masked
        assert "500" in result.masked
        # ทุก PII ถูก track ไว้
        assert len(result.pii_found) == 2

    def test_hash_enables_dedup_without_storing_raw(self):
        text1 = "โทร 0812345678"
        text2 = "โทร 0812345678"
        text3 = "โทร 0999999999"
        r1, r2, r3 = mask_pii(text1), mask_pii(text2), mask_pii(text3)
        assert r1.pii_hash == r2.pii_hash
        assert r1.pii_hash != r3.pii_hash


# ─────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────

def _generate_valid_thai_id() -> str:
    base = "123456789012"
    total = sum(int(base[i]) * (13 - i) for i in range(12))
    check = (11 - total % 11) % 10
    return base + str(check)
