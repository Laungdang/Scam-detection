import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    APP_ENV = os.getenv("APP_ENV", "development")
    APP_NAME = os.getenv("APP_NAME", "Scam Detection Chatbot")

    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = os.getenv("DB_PORT", "5432")
    DB_NAME = os.getenv("DB_NAME", "scam_chatbot")
    DB_USER = os.getenv("DB_USER", "postgres")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "")

    HUGGINGFACE_API_TOKEN = os.getenv("HUGGINGFACE_API_TOKEN", "")
    HUGGINGFACE_MODEL = os.getenv("HUGGINGFACE_MODEL", "mistralai/Mistral-7B-Instruct-v0.2")
    HUGGINGFACE_MAX_NEW_TOKENS = int(os.getenv("HUGGINGFACE_MAX_NEW_TOKENS", "300"))
    HUGGINGFACE_TEMPERATURE = float(os.getenv("HUGGINGFACE_TEMPERATURE", "0.2"))

    CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY", "")
    CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-haiku-4-5-20251001")
    CLAUDE_MAX_TOKENS = int(os.getenv("CLAUDE_MAX_TOKENS", "2048"))

    GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

    BLACKLIST_API_URL = os.getenv("BLACKLIST_API_URL", "")
    BLACKLIST_API_KEY = os.getenv("BLACKLIST_API_KEY", "")
    BLACKLIST_API_TIMEOUT = int(os.getenv("BLACKLIST_API_TIMEOUT", "10"))

    # PDPA / PII compliance — ห้ามใช้ default ใน production
    PII_SALT = os.getenv("PII_SALT", "")

    # ML Mode
    # Scope decision 2026-09-10: pilot deploy = Q&A (RAG+LLM) เท่านั้น — model v0.4.x
    # train บน data v1 ที่ archive แล้ว และ tier A (80) ยังไม่พอ train v2
    # ปิดด้วย flag ไม่ลบโค้ด: เปิดกลับเมื่อ tier A ≥ 300 + retrain (ดู CLAUDE.md changelog)
    ENABLE_ML_MODE = os.getenv("ENABLE_ML_MODE", "false").strip().lower() in ("1", "true", "yes")
    ML_CONFIDENCE_THRESHOLD = float(os.getenv("ML_CONFIDENCE_THRESHOLD", "0.7"))
    # Default = XGBoost multi-class (Week 2 winner):
    #   binary: macro-F1 0.965 | multi (10 classes): macro-F1 0.912 | latency 3ms, memory 5MB
    # BERT (v0.4.0-bert-multi) F1 0.865 — แย่กว่า; LR (v0.4.0-lr-multi) F1 0.882
    MODEL_VERSION = os.getenv("MODEL_VERSION", "v0.4.0-xgb-multi")

    # OCR / Claude Vision (CLAUDE.md Section 6.4)
    CLAUDE_VISION_DAILY_LIMIT = int(os.getenv("CLAUDE_VISION_DAILY_LIMIT", "50"))

    # Q&A RAG (Data v2) — ต้องใช้ model เดียวกันตอน setup_rag และตอน retrieve
    # bge-m3 แทน MiniLM: วัดด้วย ml/rag_eval.py (2026-08-29) MiniLM hit@3 8/11 + leak 3/3
    RAG_EMBED_MODEL = os.getenv("RAG_EMBED_MODEL", "BAAI/bge-m3")
    # 0.60 calibrated กับ bge-m3 (ml/rag_eval.py 2026-08-29): relevant top-hit 0.62-0.82, benign max 0.61
    RAG_SIMILARITY_THRESHOLD = float(os.getenv("RAG_SIMILARITY_THRESHOLD", "0.6"))

    # Pilot access gate (closed pilot — กัน Claude API cost จากคนนอก)
    # ว่าง = ไม่ต้องใช้รหัส (local dev); ตั้งค่าเมื่อเปิดผ่าน tunnel/host จริงเสมอ
    APP_ACCESS_CODE = os.getenv("APP_ACCESS_CODE", "")
    # Rate limit ต่อ client IP เฉพาะ POST /api/qa/chat (endpoint เดียวที่มี API cost)
    QA_RATE_LIMIT_PER_MINUTE = int(os.getenv("QA_RATE_LIMIT_PER_MINUTE", "6"))
    QA_RATE_LIMIT_PER_DAY = int(os.getenv("QA_RATE_LIMIT_PER_DAY", "200"))

    # Typhoon (SCB 10X) — synthetic data generation (Phase 4 Set C)
    TYPHOON_API_KEY = os.getenv("TYPHOON_API_KEY", "")
    TYPHOON_MODEL = os.getenv("TYPHOON_MODEL", "typhoon-v2.5-30b-a3b-instruct")
    TYPHOON_BASE_URL = os.getenv("TYPHOON_BASE_URL", "https://api.opentyphoon.ai/v1")

    @classmethod
    def database_url(cls) -> str:
        # Hosted DB (Neon/Supabase) ให้ตั้ง DATABASE_URL ตรงๆ ทั้งเส้น (มี ?sslmode=require ติดมา)
        # — override การประกอบจาก DB_HOST/DB_USER ที่ใช้กับ local postgres
        override = os.getenv("DATABASE_URL", "").strip()
        if override:
            if override.startswith("postgres://"):  # scheme เก่าที่ SQLAlchemy 2.x ไม่รับ
                override = override.replace("postgres://", "postgresql://", 1)
            return override
        return (
            f"postgresql+psycopg2://{cls.DB_USER}:{cls.DB_PASSWORD}"
            f"@{cls.DB_HOST}:{cls.DB_PORT}/{cls.DB_NAME}"
        )