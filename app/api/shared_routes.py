"""
Shared routes — endpoints ที่ใช้ร่วมระหว่าง mode (transcribe, health)
prefix `/api`
"""

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/api", tags=["shared"])


class TranscribeRequest(BaseModel):
    audio_base64: str
    audio_media_type: str = "audio/webm"


@router.get("/health")
def health():
    return {"status": "ok"}


@router.post("/transcribe")
def transcribe(req: TranscribeRequest):
    """แปลงเสียงเป็นข้อความ — ใช้ได้ทั้ง ML mode และ Q&A mode"""
    from app.services.transcription_service import transcribe_audio

    try:
        text = transcribe_audio(req.audio_base64, req.audio_media_type)
        return {"text": text}
    except Exception as e:
        return {"error": str(e), "text": ""}
