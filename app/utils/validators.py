import re
from urllib.parse import urlparse

from app.utils.preprocessing import normalize_bank_account, normalize_phone_number


THAI_PHONE_PATTERNS = [
    r"^0[689]\d{8}$",     # 0812345678, 0912345678, 0612345678
    r"^66[689]\d{8}$",    # 66812345678
]

BANK_ACCOUNT_PATTERN = r"^\d{9,15}$"


def is_empty_input(text: str) -> bool:
    return not text or not text.strip()


def is_url(text: str) -> bool:
    text = text.strip()
    if not text:
        return False

    if text.startswith("http://") or text.startswith("https://"):
        parsed = urlparse(text)
        return bool(parsed.netloc)

    # รองรับโดเมนแบบไม่มี scheme
    domain_like = re.match(
        r"^(www\.)?([a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}([\/\w\-\.\?\=\&\%]*)?$",
        text
    )
    return bool(domain_like)


def _is_numeric_input(text: str) -> bool:
    """ตรวจว่า input เป็นตัวเลข/เครื่องหมายโทรศัพท์เท่านั้น ไม่ใช่ข้อความยาว"""
    return bool(re.match(r"^[\d\s\-\+\(\)]+$", text.strip()))


def is_phone_number(text: str) -> bool:
    if not _is_numeric_input(text):
        return False
    normalized = normalize_phone_number(text)

    for pattern in THAI_PHONE_PATTERNS:
        if re.match(pattern, normalized):
            return True
    return False


def is_bank_account(text: str) -> bool:
    if not _is_numeric_input(text):
        return False
    normalized = normalize_bank_account(text)
    return bool(re.match(BANK_ACCOUNT_PATTERN, normalized))


def is_numeric_like(text: str) -> bool:
    normalized = re.sub(r"\D", "", text)
    return normalized.isdigit() and len(normalized) > 0


def detect_input_type(text: str) -> str:
    """
    คืนค่า:
    - url
    - phone
    - bank_account
    - text
    """
    if is_empty_input(text):
        return "empty"

    if is_url(text):
        return "url"

    if is_phone_number(text):
        return "phone"

    if is_bank_account(text):
        return "bank_account"

    return "text"