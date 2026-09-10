from sqlalchemy.orm import Session
from app.database.repository import get_advice_by_status


def get_advice_text(db: Session, status_type: str) -> str:
    advice = get_advice_by_status(db, status_type)

    if advice:
        return advice.advice_text

    fallback_map = {
        "suspicious": "ควรหลีกเลี่ยงการทำธุรกรรมทันที และตรวจสอบข้อมูลจากหลายแหล่งก่อนตัดสินใจ",
        "unclear": "ข้อมูลยังไม่เพียงพอ ควรขอข้อมูลเพิ่มเติมก่อนทำธุรกรรม",
        "non_suspicious": "ยังไม่พบข้อมูลชี้ชัด แต่ควรตรวจสอบเพิ่มเติมก่อนตัดสินใจ",
    }

    return fallback_map.get(status_type, "ไม่พบคำแนะนำสำหรับสถานะนี้")