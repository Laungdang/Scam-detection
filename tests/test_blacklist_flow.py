from app.database.connection import SessionLocal
from app.database.repository import create_check_request
from app.services.blacklist_flow_service import process_blacklist_check


def test_blacklist_flow():
    db = SessionLocal()

    try:
        request = create_check_request(
            db=db,
            user_id=None,
            input_type="phone",
            input_text="0812345678",
        )

        result = process_blacklist_check(
            db=db,
            request_id=request.request_id,
            input_type="phone",
            normalized_value="0812345678",
        )

        print("REQUEST ID:", request.request_id)
        print("BLACKLIST RESULT:", result)

    finally:
        db.close()


if __name__ == "__main__":
    test_blacklist_flow()