from app.database.connection import SessionLocal
from app.services.analysis_service import analyze_preliminary


def test_detection():
    samples = [
        ("text", "รีบโอนเงินตอนนี้เลย ของมีชิ้นเดียว", False),
        ("text", "สินค้าพร้อมส่ง สนใจสอบถามได้", False),
        ("phone", "0812345678", False),
        ("bank_account", "1234567890", True),
    ]

    db = SessionLocal()
    try:
        for input_type, value, blacklist_found in samples:
            result = analyze_preliminary(
                db=db,
                input_type=input_type,
                normalized_value=value,
                blacklist_found=blacklist_found,
            )
            print("=" * 50)
            print("INPUT TYPE:", input_type)
            print("VALUE:", value)
            print("RESULT:", result)
    finally:
        db.close()


if __name__ == "__main__":
    test_detection()