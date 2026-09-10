from app.services.ai_service import analyze_with_ai


def process_ai_analysis(
    original_input: str,
    input_type: str,
    matched_pattern_names: list[str],
    blacklist_found: bool,
    chat_history: list[dict] | None = None,
    image_base64: str | None = None,
    image_media_type: str | None = None,
) -> dict:
    """ส่งหลักฐาน raw ให้ Claude — ไม่ส่ง preliminary_status (ดู CLAUDE.md 2.1, 5.2)"""
    result = analyze_with_ai(
        original_input=original_input,
        input_type=input_type,
        matched_pattern_names=matched_pattern_names,
        blacklist_found=blacklist_found,
        chat_history=chat_history,
        image_base64=image_base64,
        image_media_type=image_media_type,
    )

    return {
        "checked": True,
        **result,
    }
