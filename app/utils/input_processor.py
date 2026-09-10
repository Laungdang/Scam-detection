import re

from app.utils.preprocessing import (
    prepare_text_for_analysis,
    normalize_phone_number,
    normalize_bank_account,
    normalize_url,
)
from app.utils.validators import detect_input_type


def extract_entities_from_text(text: str) -> list[dict]:
    """
    ดึง bank_account และ phone ที่ฝังอยู่ในข้อความออกมา
    คืนค่า list ของ {"value": ..., "type": ...}
    """
    entities = []
    seen = set()

    # หาตัวเลขติดกัน 9-15 หลัก (เลขบัญชี) — ใช้ lookahead/lookbehind แทน \b เพราะไทยเป็น word char
    bank_pattern = re.findall(r"(?<!\d)\d{9,15}(?!\d)", text)
    for num in bank_pattern:
        if num not in seen:
            seen.add(num)
            entities.append({"value": num, "type": "bank_account"})

    return entities


def process_user_input(user_input: str) -> dict:
    input_type = detect_input_type(user_input)

    if input_type == "phone":
        normalized_value = normalize_phone_number(user_input)
    elif input_type == "bank_account":
        normalized_value = normalize_bank_account(user_input)
    elif input_type == "url":
        normalized_value = normalize_url(user_input)
    else:
        normalized_value = prepare_text_for_analysis(user_input)

    extracted_entities = (
        extract_entities_from_text(user_input) if input_type == "text" else []
    )

    return {
        "original_input": user_input,
        "input_type": input_type,
        "normalized_value": normalized_value,
        "extracted_entities": extracted_entities,
    }