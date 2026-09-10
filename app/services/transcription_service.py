import base64
import io
import requests

from app.config.settings import Settings
from app.utils.logger import get_logger

logger = get_logger("transcription_service")

GROQ_URL = "https://api.groq.com/openai/v1/audio/transcriptions"

_EXT_MAP = {
    "audio/webm": ("audio.webm", "audio/webm"),
    "audio/mp4": ("audio.mp4", "audio/mp4"),
    "audio/mpeg": ("audio.mp3", "audio/mpeg"),
    "audio/mp3": ("audio.mp3", "audio/mpeg"),
    "audio/wav": ("audio.wav", "audio/wav"),
    "audio/ogg": ("audio.ogg", "audio/ogg"),
    "audio/flac": ("audio.flac", "audio/flac"),
}


def transcribe_audio(audio_base64: str, media_type: str) -> str:
    if not Settings.GROQ_API_KEY:
        raise ValueError("GROQ_API_KEY is not configured")

    audio_bytes = base64.b64decode(audio_base64) # แปลงจาก base64(string) เป็น binary data
    filename, mime = _EXT_MAP.get(media_type, ("audio.webm", "audio/webm")) # กำหนดค่า default เผื่อ media_type ไม่ตรงกับที่รองรับ

    response = requests.post(
        GROQ_URL,
        headers={"Authorization": f"Bearer {Settings.GROQ_API_KEY}"},
        files={"file": (filename, io.BytesIO(audio_bytes), mime)}, # ส่งไฟล์เสียง ส่งไฟล์เป็น binary data ผ่าน multipart/form-data
        data={"model": "whisper-large-v3", "language": "th", "response_format": "text"}, #ระบุโมเดล whisper, ภาษาที่ใช้ในเสียง, และรูปแบบการตอบกลับเป็นข้อความธรรมดา
        timeout=30,
    )
    response.raise_for_status()
    text = response.text.strip()
    logger.info(f"Transcribed {len(audio_bytes)} bytes → {len(text)} chars")
    return text
