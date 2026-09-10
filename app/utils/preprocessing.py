import re
from typing import Optional


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def clean_text(text: str) -> str:
    """
    ทำความสะอาดข้อความเบื้องต้น:
    - ตัดช่องว่างหัวท้าย
    - ลดช่องว่างหลายอันเหลืออันเดียว
    - แปลงเป็น lowercase เฉพาะอักษรอังกฤษ
    """
    if not text:
        return ""

    text = text.strip()
    text = normalize_whitespace(text)
    text = text.lower()
    return text


def remove_special_characters(text: str, keep_basic_punctuation: bool = True) -> str:
    """
    ลบอักขระพิเศษที่ไม่จำเป็น
    """
    if not text:
        return ""

    if keep_basic_punctuation:
        pattern = r"[^a-zA-Z0-9ก-๙\s\-\_\.\,\:\;\/\?\@\#\(\)]"
    else:
        pattern = r"[^a-zA-Z0-9ก-๙\s]"

    cleaned = re.sub(pattern, "", text)
    return normalize_whitespace(cleaned)


def normalize_phone_number(text: str) -> str:
    """
    เก็บเฉพาะตัวเลขจากเบอร์โทร
    เช่น 081-234-5678 -> 0812345678
    """
    return re.sub(r"\D", "", text)


def normalize_bank_account(text: str) -> str:
    """
    เก็บเฉพาะตัวเลขจากเลขบัญชี
    เช่น 123-4-56789-0 -> 1234567890
    """
    return re.sub(r"\D", "", text)


def normalize_url(text: str) -> str:
    """
    normalize URL แบบง่าย
    """
    text = text.strip()
    return text


def truncate_text(text: str, max_length: int = 500) -> str:
    """
    ตัดข้อความให้ยาวไม่เกินที่กำหนด
    """
    if len(text) <= max_length:
        return text
    return text[:max_length].strip()


def prepare_text_for_analysis(text: str, max_length: int = 1000) -> str:
    """
    pipeline รวมสำหรับเตรียมข้อความก่อนวิเคราะห์
    """
    text = clean_text(text)
    text = remove_special_characters(text, keep_basic_punctuation=True)
    text = truncate_text(text, max_length=max_length)
    return text


def safe_text(text: Optional[str]) -> str:
    return text.strip() if text else ""