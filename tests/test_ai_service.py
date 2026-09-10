from app.services.ai_service import analyze_with_huggingface


def test_ai():
    """smoke test — analyze_with_ai (alias analyze_with_huggingface) ไม่รับ preliminary_status แล้ว"""
    result = analyze_with_huggingface(
        original_input="รีบโอนเงินตอนนี้เลย ของมีชิ้นเดียว",
        input_type="text",
        matched_pattern_names=["เร่งให้โอนเงิน"],
        blacklist_found=False,
    )

    print(result)


if __name__ == "__main__":
    test_ai()
