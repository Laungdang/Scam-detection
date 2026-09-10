"""
ML Detection Engine — orchestrator สำหรับ ML Mode

หลักการ (ดู CLAUDE.md Section 4.1):
- Single decision point: model.predict() ครั้งเดียว (ใน ml.inference.predict)
- Stateless ทุก request (ไม่มี chat history)
- ทุก signal เป็น feature ใน vector ที่ส่งให้ model — ไม่มี cascade gate
- PII masked ก่อนส่ง response/log (Section 2.8)

Engine ทำ:
1. Stage 1: normalize input (transcribe audio ถ้าจำเป็น, OCR ภาพถ้ามี)
2. Stage 4: เรียก ml.inference.predict()
3. Stage 6: บันทึก DB (mode='ml', masked text, input_hash)
"""

from __future__ import annotations

from dataclasses import asdict

from sqlalchemy.orm import Session

from app.database.models import CheckRequest, CheckResult
from app.services.pii_masker import hash_value, mask_pii
from app.services.prefill_cache import store_input
from app.utils.input_processor import process_user_input
from ml.inference import MLDetectResponse, predict


def run_ml_detection(
    db: Session,
    text: str,
    image_base64: str | None = None,
    image_media_type: str | None = None,
    audio_base64: str | None = None,
    audio_media_type: str | None = None,
) -> MLDetectResponse:
    """Pipeline เต็มของ ML mode — รับ raw input → คืน MLDetectResponse (PII masked, logged)"""

    # Stage 1: Input Normalization
    resolved_text = text or ""
    if audio_base64 and not resolved_text.strip():
        resolved_text = _transcribe(audio_base64, audio_media_type or "audio/webm")
    if image_base64 and not resolved_text.strip():
        resolved_text = _ocr_image(image_base64, image_media_type or "image/png")

    if not resolved_text.strip():
        return _empty_response()

    processed = process_user_input(resolved_text)
    normalized = processed["original_input"]
    input_type = processed["input_type"]

    # Stage 2-5: model inference (รวม feature extraction + decision + explanation)
    response = predict(normalized)

    # ถ้า suggest_qa → issue prefill_token (โอนแค่ raw input, ดู CLAUDE.md 4.7)
    if response.suggest_qa and response.qa_prefill_token is None:
        response.qa_prefill_token = store_input(normalized)

    # Stage 6: persistence — masked + hash เท่านั้น (ดู CLAUDE.md 2.8)
    masked = mask_pii(normalized, mode="strict")
    request_record = CheckRequest(
        user_id=None,
        mode="ml",
        input_type=input_type,
        input_text=masked.masked,
        input_hash=hash_value(normalized),
    )
    db.add(request_record)
    db.commit()
    db.refresh(request_record)

    result_record = CheckResult(
        request_id=request_record.request_id,
        result_status=response.verdict,
        matched_pattern=", ".join(f.name for f in response.top_features[:3]) or None,
        ai_summary=None,
    )
    db.add(result_record)
    db.commit()

    return response


def _empty_response() -> MLDetectResponse:
    return MLDetectResponse(
        verdict="uncertain",
        confidence=0.0,
        category=None,
        top_features=[],
        advice_text="ไม่มี input ที่จะวิเคราะห์ ส่งข้อความ/ภาพ/เสียงมาก่อน",
        masked_input="",
        suggest_qa=True,
        qa_prefill_token=None,
        model_version="n/a",
        latency_ms=0,
    )


def _transcribe(audio_base64: str, media_type: str) -> str:
    """transcribe audio → text (ใช้ shared service)"""
    try:
        from app.services.transcription_service import transcribe_audio
        return transcribe_audio(audio_base64, media_type) or ""
    except Exception:
        return ""


def _ocr_image(image_base64: str, media_type: str) -> str:
    """OCR image → text — ML mode ใช้ EasyOCR เท่านั้น ห้าม Claude Vision fallback

    ดู CLAUDE.md Section 6.4 — ML mode ต้องเป็น cost-deterministic
    ถ้า OCR fail/low quality → คืน "" → ml_engine จะตั้ง suggest_qa=True
    """
    try:
        from app.services.ocr_service import extract_text_from_image
        result = extract_text_from_image(
            image_base64,
            image_media_type=media_type,
            allow_llm_fallback=False,
        )
        if result.is_low_quality:
            return ""
        return result.text
    except Exception:
        return ""


def response_to_dict(response: MLDetectResponse) -> dict:
    """ทำให้ pydantic/FastAPI serialize ได้ (จัดการ dataclass nested)"""
    return asdict(response)
