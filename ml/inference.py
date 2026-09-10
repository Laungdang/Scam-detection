"""
ML Inference — โหลด trained model + ตอบเป็น MLDetectResponse

หลักการ (ดู CLAUDE.md Section 4.1 + 4.5):
- จุดตัดสินเดียวคือ model.predict_proba() — ไม่มี override
- มาส์ก PII ใน input/output ก่อนส่งกลับ
- ตั้ง suggest_qa=True ถ้า confidence < threshold (default 0.7)
- โหลด model ครั้งเดียวที่ module level (lazy) — ไม่ reload ทุก request

ใช้จาก app/engines/ml_engine.py (Phase 2)
"""

from __future__ import annotations

import json
import pickle
import time
from dataclasses import asdict, dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Literal

import numpy as np
from sklearn.pipeline import Pipeline

from app.config.settings import Settings
from app.services.pii_masker import mask_pii


Verdict = Literal["danger", "caution", "safe", "uncertain"]
MODELS_DIR = Path("models")


# Multi-class category → display label (Thai-friendly)
CATEGORY_LABELS_TH = {
    "borrowing_scam": "หลอกขอยืมเงิน",
    "financial_fraud": "หลอกหักเงิน / โอนเงินผิดปกติ",
    "impersonation_authority": "อ้างเป็นหน่วยงานรัฐ",
    "investment_scam": "หลอกชวนลงทุน",
    "loan_offer": "เสนอเงินกู้ปลอม",
    "phishing_link": "ลิงก์ฟิชชิ่ง",
    "prize_scam": "หลอกว่าได้รางวัล",
    "romance_scam": "หลอกความรัก (Romance scam)",
    "other": "มิจฉาชีพประเภทอื่น",
    "safe": "ปลอดภัย",
}


def _is_safe_class(class_name: str) -> bool:
    return class_name == "safe"


def _is_binary_classes(classes: list[str]) -> bool:
    """True ถ้าเป็น binary model (สอง class คือ danger/safe)"""
    return set(classes) == {"danger", "safe"}


@dataclass
class FeatureContribution:
    name: str
    weight: float


@dataclass
class MLDetectResponse:
    verdict: Verdict
    confidence: float
    category: str | None
    top_features: list[FeatureContribution]
    advice_text: str
    masked_input: str
    suggest_qa: bool
    qa_prefill_token: str | None
    model_version: str
    latency_ms: int

    def to_dict(self) -> dict:
        d = asdict(self)
        return d


@dataclass
class LoadedModel:
    """unified wrapper รองรับทั้ง bare Pipeline (LogReg) และ {pipeline, label_encoder} (XGBoost)"""
    pipeline: Pipeline
    classes: list[str]
    label_encoder: object | None  # sklearn LabelEncoder or None

    def predict_proba(self, texts: list[str]) -> np.ndarray:
        return self.pipeline.predict_proba(texts)


@lru_cache(maxsize=1)
def _load_model(version: str) -> tuple[LoadedModel, dict]:
    """โหลด model จาก disk ครั้งเดียว (cache ไว้)

    รองรับ 2 format:
    - bare sklearn Pipeline (LogReg) → ใช้ pipeline.classes_
    - dict {pipeline, label_encoder} (XGBoost) → ใช้ encoder.classes_
    """
    model_dir = MODELS_DIR / version
    with (model_dir / "model.pkl").open("rb") as f:
        obj = pickle.load(f)

    if isinstance(obj, dict) and "pipeline" in obj:
        pipeline = obj["pipeline"]
        encoder = obj.get("label_encoder")
        raw_classes = list(encoder.classes_) if encoder is not None else list(pipeline.classes_)
        loaded = LoadedModel(pipeline=pipeline, classes=[str(c) for c in raw_classes], label_encoder=encoder)
    else:
        loaded = LoadedModel(pipeline=obj, classes=[str(c) for c in obj.classes_], label_encoder=None)

    metadata = json.loads((model_dir / "metadata.json").read_text(encoding="utf-8"))
    return loaded, metadata


def _get_feature_names(feature_pipeline) -> list[str]:
    """รวม feature names จาก FeatureUnion sub-transformers manually

    เพราะ MetadataFeatures ไม่ implement get_feature_names_out — เลย concat เอง
    """
    from ml.features import MetadataFeatures

    names: list[str] = []
    for trans_name, trans in feature_pipeline.transformer_list:
        if hasattr(trans, "get_feature_names_out"):
            try:
                sub = trans.get_feature_names_out()
                names.extend(f"{trans_name}::{n}" for n in sub)
                continue
            except Exception:
                pass
        # fallback สำหรับ metadata pipeline
        names.extend(f"{trans_name}::{n}" for n in MetadataFeatures.feature_names)
    return names


def _top_features(model: LoadedModel, text: str, k: int = 5) -> list[FeatureContribution]:
    """ดึง top-k feature ที่ดัน prediction — รองรับทั้ง LogReg (coef) และ XGBoost (importance)

    ดู CLAUDE.md Section 2.5 (Explainability)
    """
    try:
        pipeline = model.pipeline
        feature_pipeline = pipeline.named_steps["features"]
        classifier = pipeline.named_steps["classifier"]
        feature_vec = feature_pipeline.transform([text])
        feature_names = _get_feature_names(feature_pipeline)

        if hasattr(classifier, "coef_"):
            # LogReg-style: coef * feature_value → signed contribution
            coefs = classifier.coef_[0]
            contribs = np.asarray(feature_vec.multiply(coefs).todense()).flatten()
        elif hasattr(classifier, "feature_importances_"):
            # XGBoost-style: importance * feature_value (unsigned, แต่บอกว่า feature ไหนสำคัญต่อ prediction นี้)
            importances = classifier.feature_importances_
            contribs = np.asarray(feature_vec.multiply(importances).todense()).flatten()
        else:
            return []

        top_idx = np.argsort(np.abs(contribs))[-k:][::-1]
        return [
            FeatureContribution(
                name=str(feature_names[i]) if i < len(feature_names) else f"feature_{i}",
                weight=float(contribs[i]),
            )
            for i in top_idx
            if abs(contribs[i]) > 1e-6
        ]
    except Exception as e:
        import logging
        logging.getLogger("ml.inference").warning(f"top_features extraction failed: {e!r}")
        return []


def _verdict_from_proba(
    classes: list[str],
    probs: np.ndarray,
    threshold: float,
) -> tuple[Verdict, str | None, float]:
    """แปลง class probability → (verdict, category, confidence)

    Binary model (classes = {danger, safe}):
        - predicted = danger → verdict=danger, category=None
        - predicted = safe → verdict=safe, category=None
    Multi-class model (classes = {safe, borrowing_scam, ..., other}):
        - predicted = safe → verdict=safe, category=None
        - predicted != safe → verdict=danger, category=predicted
    ถ้า max(probs) < threshold → verdict=uncertain (แต่ keep category=top-1 เป็น hint)
    """
    max_idx = int(np.argmax(probs))
    confidence = float(probs[max_idx])
    predicted = classes[max_idx]

    is_binary = _is_binary_classes(classes)
    is_safe = _is_safe_class(predicted) or (is_binary and predicted == "safe")

    if confidence < threshold:
        # uncertain — แต่ยัง expose category top-1 เป็น hint (ถ้า multi-class)
        category = None if (is_binary or is_safe) else predicted
        return "uncertain", category, confidence

    if is_safe:
        return "safe", None, confidence

    # danger (binary) หรือ scam category (multi)
    category = None if is_binary else predicted
    return "danger", category, confidence


def predict(
    text: str,
    version: str | None = None,
    threshold: float | None = None,
) -> MLDetectResponse:
    """รัน inference + คืน MLDetectResponse (PII masked, ready for API)"""
    version = version or Settings.MODEL_VERSION
    threshold = threshold if threshold is not None else Settings.ML_CONFIDENCE_THRESHOLD

    start = time.time()
    loaded, metadata = _load_model(version)

    probs = loaded.predict_proba([text])[0]
    verdict, category, confidence = _verdict_from_proba(loaded.classes, probs, threshold)

    features = _top_features(loaded, text, k=5)

    masked = mask_pii(text, mode="display")

    suggest_qa = (
        verdict == "uncertain"
        or confidence < threshold
    )

    advice_text = _advice_for(verdict, category)

    return MLDetectResponse(
        verdict=verdict,
        confidence=round(confidence, 4),
        category=category,
        top_features=features,
        advice_text=advice_text,
        masked_input=masked.masked,
        suggest_qa=suggest_qa,
        qa_prefill_token=None,  # Phase 3 (ML→QA handoff) จะ implement
        model_version=version,
        latency_ms=int((time.time() - start) * 1000),
    )


_CATEGORY_ADVICE = {
    "borrowing_scam": "ระวัง! คนแอบอ้างเป็นญาติ/เพื่อน ขอยืมเงินด่วน — โทรกลับเช็คจากเบอร์ที่คุณรู้จักก่อนเสมอ",
    "financial_fraud": "ระวัง! อ้างว่าบัญชีมีปัญหา ขอให้กดลิงก์ — ติดต่อธนาคารผ่านแอป/สาขาตรง อย่ากดลิงก์",
    "impersonation_authority": "ระวัง! อ้างเป็นเจ้าหน้าที่ DSI/สรรพากร/ตำรวจ — หน่วยงานจริงไม่ส่ง SMS แนบลิงก์ โทร 1441",
    "investment_scam": "ระวัง! ลงทุนได้ผลตอบแทนสูงเกินจริง — ตรวจสอบ license ผ่าน ก.ล.ต.",
    "loan_offer": "ระวัง! เสนอเงินกู้ไม่ต้องค้ำ อนุมัติทันที — เงินกู้ถูกกฎหมายไม่ติดต่อทาง SMS",
    "phishing_link": "ระวัง! ลิงก์ปลอม — อย่ากดลิงก์ ตรวจสอบ URL ผ่านเว็บทางการของหน่วยงานเอง",
    "prize_scam": "ระวัง! อ้างว่าได้รางวัล — รางวัลจริงไม่ต้องโอนค่าธรรมเนียม / ไม่ต้องกดลิงก์",
    "romance_scam": "ระวัง! รู้จักผ่านออนไลน์แล้วขอเงิน — โดยเฉพาะถ้ายังไม่เคยพบเจอตัวจริง",
    "other": "ระวัง! ข้อความนี้มีลักษณะเป็นมิจฉาชีพ — โทร 1441 (ตำรวจไซเบอร์) ถ้าสงสัย",
}


def _advice_for(verdict: Verdict, category: str | None = None) -> str:
    """advice ตาม verdict + category — Phase 6 จะย้ายเป็น YAML template"""
    if verdict == "danger":
        if category and category in _CATEGORY_ADVICE:
            return _CATEGORY_ADVICE[category]
        return (
            "ระวัง! ข้อความนี้มีลักษณะเป็นมิจฉาชีพ "
            "อย่ากดลิงก์ อย่าให้ข้อมูลส่วนตัว "
            "ถ้าสงสัยให้โทร 1441 (ตำรวจไซเบอร์)"
        )
    if verdict == "uncertain":
        hint = ""
        if category and category in CATEGORY_LABELS_TH:
            hint = f" (เดาว่าเป็น: {CATEGORY_LABELS_TH[category]})"
        return (
            f"ระบบไม่มั่นใจ 100%{hint} — แนะนำให้ปรึกษา AI ผู้ช่วยต่อ "
            f"เพื่อวิเคราะห์เคสเฉพาะอย่างละเอียด"
        )
    return "ไม่พบสัญญาณมิจฉาชีพชัดเจน — แต่ระวังไว้เสมอ"
