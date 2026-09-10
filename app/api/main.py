import secrets
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

from app.api.qa_routes import router as qa_router
from app.api.shared_routes import router as shared_router
from app.config.settings import Settings
from app.services.rate_limiter import SlidingWindowRateLimiter
from app.utils.logger import get_logger

logger = get_logger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Pre-warm Sentence Transformer + ChromaDB ตอน startup
    # ป้องกัน request แรกช้าเพราะโหลด model
    try:
        from app.services.rag_service import get_collection
        get_collection()
        logger.info("RAG collection pre-warmed successfully")
    except Exception as e:
        logger.warning(f"RAG pre-warm failed (non-critical): {e}")
    yield


app = FastAPI(title="Scam Detection API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(qa_router)
app.include_router(shared_router)

# ML mode ปิดด้วย flag (scope 2026-09-10): pilot = Q&A เท่านั้น — import เฉพาะเมื่อเปิด
# เพื่อไม่โหลด model artifact โดยไม่จำเป็น (Mode Isolation 2.4: ถอดได้โดย Q&A ไม่กระทบ)
if Settings.ENABLE_ML_MODE:
    from app.api.ml_routes import router as ml_router

    app.include_router(ml_router)
else:
    logger.info("ML mode disabled (ENABLE_ML_MODE=false) — Q&A-only deployment")

app.mount("/static", StaticFiles(directory="app/ui/static"), name="static")

# Rate limit เฉพาะ endpoint ที่มี Claude API cost — access control เป็นเรื่องของ I/O layer
# ไม่ใช่ decision logic (Section 2.7) — limiter เป็น shared service ไม่รู้จัก verdict
qa_chat_limiter = SlidingWindowRateLimiter(
    per_minute=Settings.QA_RATE_LIMIT_PER_MINUTE,
    per_day=Settings.QA_RATE_LIMIT_PER_DAY,
)

# path ที่เปิดโดยไม่ต้องมีรหัส: หน้าเว็บ, static, config (UI ต้องอ่านก่อนถามรหัส), health
PUBLIC_API_PATHS = {"/api/config", "/api/health", "/health"}


def _client_key(request: Request) -> str:
    # หลัง Cloudflare tunnel ip จริงอยู่ใน header; ต่อตรง = client.host
    return (
        request.headers.get("cf-connecting-ip")
        or (request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
        or (request.client.host if request.client else "unknown")
    )


@app.middleware("http")
async def pilot_gate(request: Request, call_next):
    path = request.url.path

    if (
        Settings.APP_ACCESS_CODE
        and request.method != "OPTIONS"
        and path.startswith("/api/")
        and path not in PUBLIC_API_PATHS
    ):
        supplied = request.headers.get("x-access-code", "")
        if not secrets.compare_digest(supplied, Settings.APP_ACCESS_CODE):
            return JSONResponse(
                status_code=401,
                content={"detail": "ต้องใส่รหัสเข้าใช้งานให้ถูกต้อง (closed pilot)"},
            )

    if path == "/api/qa/chat" and request.method == "POST":
        decision = qa_chat_limiter.check_and_record(_client_key(request))
        if not decision.allowed:
            msg = (
                "ส่งคำถามถี่เกินไป กรุณารอสักครู่"
                if decision.reason == "per_minute"
                else "ใช้ครบโควต้าของวันนี้แล้ว พรุ่งนี้ใช้ต่อได้"
            )
            return JSONResponse(
                status_code=429,
                content={"detail": msg},
                headers={"Retry-After": str(decision.retry_after_seconds)},
            )

    return await call_next(request)


@app.get("/api/config")
def app_config():
    """ค่าที่ UI ต้องรู้ตอนโหลดหน้า — ไม่มีความลับใดๆ ในนี้"""
    return {
        "ml_enabled": Settings.ENABLE_ML_MODE,
        "access_code_required": bool(Settings.APP_ACCESS_CODE),
    }


@app.get("/")
def index():
    return FileResponse("app/ui/index.html")
