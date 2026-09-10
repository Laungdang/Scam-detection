"""
ML Detection routes — prefix `/api/ml`

ดู CLAUDE.md Section 4 (ML Pipeline) + Section 7 (file structure)
- POST /api/ml/detect — single-shot scam detection (stateless)
- ไม่มี chat session ใน mode นี้ (เป็น stateless tool, ไม่ใช่ conversational)
"""

from fastapi import APIRouter
from pydantic import BaseModel

from app.database.connection import SessionLocal
from app.engines.ml_engine import response_to_dict, run_ml_detection


router = APIRouter(prefix="/api/ml", tags=["ml"])


class DetectRequest(BaseModel):
    text: str = ""
    image_base64: str | None = None
    image_media_type: str | None = None
    audio_base64: str | None = None
    audio_media_type: str | None = None


@router.post("/detect")
def detect(req: DetectRequest) -> dict:
    """รัน ML classifier บน input — ตอบ verdict + confidence + features (PII masked)

    Stateless: ไม่เก็บ chat history, ไม่ต้องส่ง session_id
    Output: MLDetectResponse schema (ดู CLAUDE.md Section 4.5)
    """
    db = SessionLocal()
    try:
        response = run_ml_detection(
            db=db,
            text=req.text,
            image_base64=req.image_base64,
            image_media_type=req.image_media_type,
            audio_base64=req.audio_base64,
            audio_media_type=req.audio_media_type,
        )
        return response_to_dict(response)
    finally:
        db.close()
