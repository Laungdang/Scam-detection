from sqlalchemy.orm import Session

from app.services.pattern_service import (
    find_matching_patterns,
    extract_unique_pattern_names,
)
from app.services.advice_service import get_advice_text


def determine_preliminary_status(
    input_type: str,
    matched_patterns: list[dict],
    blacklist_found: bool = False,
) -> str:
    """
    สถานะที่รองรับ:
    - suspicious
    - unclear
    - non_suspicious
    """
    if blacklist_found:
        return "suspicious"

    if matched_patterns:
        return "suspicious"

    if input_type == "text":
        return "unclear"

    return "non_suspicious"


def build_reason_text(
    input_type: str,
    matched_patterns: list[dict],
    blacklist_found: bool = False,
) -> str:
    pattern_names = extract_unique_pattern_names(matched_patterns)

    if blacklist_found and pattern_names:
        return f"พบข้อมูลใน blacklist และพบ pattern ที่น่าสงสัย ได้แก่: {', '.join(pattern_names)}"

    if blacklist_found:
        return "พบข้อมูลที่เกี่ยวข้องใน blacklist"

    if pattern_names:
        return f"พบ pattern ที่น่าสงสัย ได้แก่: {', '.join(pattern_names)}"

    if input_type == "text":
        return "ยังไม่พบ pattern ที่ชัดเจน แต่ข้อความลักษณะนี้ยังต้องใช้ข้อมูลเพิ่มเติม"

    return "ยังไม่พบข้อมูลชี้ชัดจากข้อมูลที่ให้มา"


def analyze_preliminary(
    db: Session,
    input_type: str,
    normalized_value: str,
    blacklist_found: bool = False,
) -> dict:
    if input_type == "text":
        matched_patterns = find_matching_patterns(db, normalized_value)
    else:
        matched_patterns = []

    status = determine_preliminary_status(
        input_type=input_type,
        matched_patterns=matched_patterns,
        blacklist_found=blacklist_found,
    )

    reason_text = build_reason_text(
        input_type=input_type,
        matched_patterns=matched_patterns,
        blacklist_found=blacklist_found,
    )

    advice_text = get_advice_text(db, status)

    return {
        "status": status,
        "matched_patterns": matched_patterns,
        "matched_pattern_names": extract_unique_pattern_names(matched_patterns),
        "reason_text": reason_text,
        "advice_text": advice_text,
    }