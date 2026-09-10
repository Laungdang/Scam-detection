import json
from sqlalchemy.orm import Session

from app.services.blacklist_service import check_blacklist
from app.database.repository import create_blacklist_check
from app.utils.blacklist_rules import should_check_blacklist


def process_blacklist_check(
    db: Session,
    request_id: int,
    input_type: str,
    normalized_value: str,
) -> dict:
    """
    จัดการ flow Blacklist ทั้งหมด:
    - เช็กว่าควรเรียก API ไหม
    - เรียก API
    - บันทึกผลลง DB
    - คืนผลลัพธ์มาตรฐาน
    """
    if not should_check_blacklist(input_type):
        return {
            "checked": False,
            "success": False,
            "found": False,
            "status": "skipped",
            "message": f"ไม่ต้องตรวจ Blacklist สำหรับ input_type={input_type}",
            "raw_response": None,
        }

    result = check_blacklist(
        value=normalized_value,
        value_type=input_type,
    )

    create_blacklist_check(
        db=db,
        request_id=request_id,
        checked_value=normalized_value,
        checked_type=input_type,
        api_status=result["status"],
        api_response=json.dumps(result["raw_response"], ensure_ascii=False) if result["raw_response"] else None,
    )

    return {
        "checked": True,
        **result,
    }