from app.services.ai_flow_service import process_ai_analysis


def test_ai_flow():
    """smoke test — Claude flow ไม่รับ preliminary_status แล้ว (ดู CLAUDE.md 2.1)"""
    result = process_ai_analysis(
        original_input="รีบโอนเงินตอนนี้เลย ของมีชิ้นเดียว",
        input_type="text",
        matched_pattern_names=["เร่งให้โอนเงิน"],
        blacklist_found=False,
    )

    print(result)


if __name__ == "__main__":
    test_ai_flow()
