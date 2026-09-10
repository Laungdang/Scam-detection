"""
OCR Service — EasyOCR primary, Claude Vision fallback (Q&A only)

ดู CLAUDE.md Section 6.4 (OCR Strategy):
- ML mode → EasyOCR only (allow_llm_fallback=False), ถ้า fail → suggest_qa
- Q&A mode → EasyOCR + Claude Vision fallback (allow_llm_fallback=True)
- Rate limit Claude Vision: 50 calls/วัน (per env)
- Service ไม่รู้ว่ามาจาก mode ไหน — caller บอกผ่าน allow_llm_fallback

Input: base64-encoded image (from API request)
Output: OcrResult { text, avg_confidence, char_count, engine_used }
"""

from __future__ import annotations

import base64
import io
import threading
from dataclasses import dataclass
from datetime import date
from typing import Literal

from PIL import Image

from app.config.settings import Settings
from app.utils.logger import get_logger


logger = get_logger("ocr_service")

EngineUsed = Literal["easyocr", "claude_vision", "none"]
DEFAULT_CONFIDENCE_THRESHOLD = 0.5
DEFAULT_MIN_CHARS = 10
DEFAULT_CLAUDE_VISION_DAILY_LIMIT = 50


@dataclass
class OcrResult:
    text: str
    avg_confidence: float
    char_count: int
    engine_used: EngineUsed
    fallback_reason: str | None = None

    @property
    def is_low_quality(self) -> bool:
        """text ว่าง / สั้นเกินไป / confidence ต่ำ → low quality"""
        return (
            not self.text
            or self.char_count < DEFAULT_MIN_CHARS
            or self.avg_confidence < DEFAULT_CONFIDENCE_THRESHOLD
        )


# ─────────────────────────────────────────────────────────────────
# EasyOCR — lazy load (model ~500MB downloaded on first use)
# ─────────────────────────────────────────────────────────────────

_reader = None
_reader_lock = threading.Lock()


def _get_reader():
    """lazy-load EasyOCR reader — ใช้ Thai + English"""
    global _reader
    if _reader is not None:
        return _reader
    with _reader_lock:
        if _reader is None:
            try:
                import easyocr
                logger.info("Loading EasyOCR (th+en) — first run may download ~500MB ...")
                _reader = easyocr.Reader(["th", "en"], gpu=False, verbose=False)
                logger.info("EasyOCR loaded")
            except Exception as e:
                logger.warning(f"EasyOCR load failed: {e!r}")
                _reader = None
        return _reader


def _decode_image(image_base64: str) -> bytes | None:
    """decode base64 → bytes (verify เป็น valid image)"""
    try:
        raw = base64.b64decode(image_base64)
        Image.open(io.BytesIO(raw)).verify()
        return raw
    except Exception as e:
        logger.warning(f"image decode failed: {e!r}")
        return None


def _ocr_easyocr(image_bytes: bytes) -> OcrResult:
    """รัน EasyOCR — return OcrResult (text + avg_confidence)"""
    reader = _get_reader()
    if reader is None:
        return OcrResult(text="", avg_confidence=0.0, char_count=0,
                         engine_used="none", fallback_reason="easyocr_unavailable")
    try:
        results = reader.readtext(image_bytes, detail=1, paragraph=False)
    except Exception as e:
        logger.warning(f"EasyOCR readtext failed: {e!r}")
        return OcrResult(text="", avg_confidence=0.0, char_count=0,
                         engine_used="none", fallback_reason=f"easyocr_error: {e!r}")

    if not results:
        return OcrResult(text="", avg_confidence=0.0, char_count=0,
                         engine_used="easyocr", fallback_reason="no_text_detected")

    texts: list[str] = []
    confidences: list[float] = []
    for r in results:
        if len(r) >= 3:
            _, text, conf = r[0], r[1], r[2]
            if text and text.strip():
                texts.append(text.strip())
                try:
                    confidences.append(float(conf))
                except (TypeError, ValueError):
                    continue

    combined_text = " ".join(texts).strip()
    avg_conf = sum(confidences) / len(confidences) if confidences else 0.0
    return OcrResult(
        text=combined_text,
        avg_confidence=round(avg_conf, 3),
        char_count=len(combined_text),
        engine_used="easyocr",
    )


# ─────────────────────────────────────────────────────────────────
# Claude Vision fallback — Q&A only, rate-limited
# ─────────────────────────────────────────────────────────────────

class _ClaudeVisionRateLimiter:
    """daily counter — reset เที่ยงคืน (UTC ก่อน) thread-safe"""

    def __init__(self, daily_limit: int):
        self.daily_limit = daily_limit
        self._lock = threading.Lock()
        self._date = date.today()
        self._count = 0

    def acquire(self) -> bool:
        with self._lock:
            today = date.today()
            if today != self._date:
                self._date = today
                self._count = 0
            if self._count >= self.daily_limit:
                return False
            self._count += 1
            return True

    @property
    def used_today(self) -> int:
        with self._lock:
            if date.today() != self._date:
                return 0
            return self._count


_claude_vision_limiter = _ClaudeVisionRateLimiter(
    daily_limit=getattr(Settings, "CLAUDE_VISION_DAILY_LIMIT", DEFAULT_CLAUDE_VISION_DAILY_LIMIT)
)


def _ocr_claude_vision(image_base64: str, image_media_type: str) -> OcrResult:
    """fallback OCR ด้วย Claude Vision — Q&A only"""
    if not _claude_vision_limiter.acquire():
        logger.warning(
            f"Claude Vision daily limit reached "
            f"({_claude_vision_limiter.daily_limit}/day) — skipping fallback"
        )
        return OcrResult(text="", avg_confidence=0.0, char_count=0,
                         engine_used="none", fallback_reason="claude_vision_rate_limited")

    if not Settings.CLAUDE_API_KEY:
        return OcrResult(text="", avg_confidence=0.0, char_count=0,
                         engine_used="none", fallback_reason="claude_api_key_missing")

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=Settings.CLAUDE_API_KEY)
        msg = client.messages.create(
            model=Settings.CLAUDE_MODEL,
            max_tokens=512,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": image_media_type,
                            "data": image_base64,
                        },
                    },
                    {
                        "type": "text",
                        "text": (
                            "อ่านและคัดลอกข้อความทั้งหมดที่อยู่ในภาพนี้ออกมาให้ครบถ้วน "
                            "ไม่ต้องวิเคราะห์ ไม่ต้องอธิบาย ให้แค่ข้อความในภาพเท่านั้น"
                        ),
                    },
                ],
            }],
        )
        text = msg.content[0].text.strip() if msg.content else ""
        logger.info(f"Claude Vision OCR: {len(text)} chars (used today: {_claude_vision_limiter.used_today})")
        return OcrResult(
            text=text,
            avg_confidence=0.95,  # Claude ไม่ให้ confidence score, สมมติ high
            char_count=len(text),
            engine_used="claude_vision",
        )
    except Exception as e:
        logger.warning(f"Claude Vision OCR failed: {e!r}")
        return OcrResult(text="", avg_confidence=0.0, char_count=0,
                         engine_used="none", fallback_reason=f"claude_vision_error: {e!r}")


# ─────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────

def extract_text_from_image(
    image_base64: str,
    image_media_type: str = "image/png",
    allow_llm_fallback: bool = False,
) -> OcrResult:
    """รัน OCR — caller ระบุนโยบาย LLM fallback

    Args:
        image_base64: base64-encoded image
        image_media_type: เช่น "image/jpeg", "image/png"
        allow_llm_fallback: ถ้า True + EasyOCR low quality → ใช้ Claude Vision
                            ถ้า False → คืน EasyOCR result ตามจริง (ML mode behavior)

    Returns: OcrResult — caller เช็ค .is_low_quality + .engine_used เพื่อตัดสิน
    """
    image_bytes = _decode_image(image_base64)
    if image_bytes is None:
        return OcrResult(text="", avg_confidence=0.0, char_count=0,
                         engine_used="none", fallback_reason="decode_failed")

    primary = _ocr_easyocr(image_bytes)

    if not primary.is_low_quality:
        return primary

    if not allow_llm_fallback:
        primary.fallback_reason = (
            primary.fallback_reason or "low_quality_no_fallback_allowed"
        )
        return primary

    logger.info(f"EasyOCR low quality (conf={primary.avg_confidence}, chars={primary.char_count}) — fallback Claude Vision")
    fallback = _ocr_claude_vision(image_base64, image_media_type)
    if fallback.text:
        return fallback
    return primary  # คืน EasyOCR result เดิม ถ้า fallback fail


def used_today() -> int:
    """expose สำหรับ monitoring + test"""
    return _claude_vision_limiter.used_today
