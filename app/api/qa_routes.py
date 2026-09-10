"""
Q&A Assistant routes — prefix `/api/qa`

ดู CLAUDE.md Section 5 (Q&A pipeline) + Section 4.7 (handoff)
- POST /api/qa/chat — main chat endpoint
- POST /api/qa/chat?prefill=<token> — รับ raw input จาก ML mode handoff
- GET/POST/DELETE /api/qa/sessions/* — session management

Logic ทั้งหมดอยู่ใน app/engines/qa_engine.py (Claude เป็น sole decider)
"""

import json
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.database.connection import SessionLocal
from app.database.models import ChatMessage, ChatSession
from app.engines.qa_engine import QAAnalysisError, run_qa
from app.services.prefill_cache import consume_input


router = APIRouter(prefix="/api/qa", tags=["qa"])


class ChatRequest(BaseModel):
    text: str = ""
    session_id: int | None = None
    image_base64: str | None = None
    image_media_type: str | None = None
    prefill_token: str | None = None  # โอนมาจาก ML mode (ดู CLAUDE.md 4.7)


class NewSessionRequest(BaseModel):
    title: str = "New Chat"


@router.post("/sessions")
def create_session(req: NewSessionRequest):
    db = SessionLocal()
    try:
        session = ChatSession(title=req.title)
        db.add(session)
        db.commit()
        db.refresh(session)
        return {"session_id": session.session_id, "title": session.title}
    finally:
        db.close()


@router.get("/sessions")
def list_sessions(include_deleted: bool = False):
    """รายการ session — default exclude soft-deleted (Heuristic Eval H3 fix)"""
    db = SessionLocal()
    try:
        q = db.query(ChatSession)
        if not include_deleted:
            q = q.filter(ChatSession.deleted_at.is_(None))
        sessions = q.order_by(ChatSession.created_at.desc()).limit(20).all()
        return [
            {
                "session_id": s.session_id,
                "title": s.title,
                "created_at": str(s.created_at),
                "deleted_at": str(s.deleted_at) if s.deleted_at else None,
            }
            for s in sessions
        ]
    finally:
        db.close()


@router.get("/sessions/trash")
def list_trash():
    """รายการ session ที่ถูก soft-delete (ยังกู้ได้ ภายใน 30 วัน)"""
    db = SessionLocal()
    try:
        sessions = (
            db.query(ChatSession)
            .filter(ChatSession.deleted_at.is_not(None))
            .order_by(ChatSession.deleted_at.desc())
            .limit(50)
            .all()
        )
        return [
            {
                "session_id": s.session_id,
                "title": s.title,
                "deleted_at": str(s.deleted_at),
            }
            for s in sessions
        ]
    finally:
        db.close()


@router.post("/sessions/{session_id}/restore")
def restore_session(session_id: int):
    """กู้ session ที่ถูก soft-delete (Heuristic Eval H3 fix)"""
    db = SessionLocal()
    try:
        s = db.query(ChatSession).filter(ChatSession.session_id == session_id).first()
        if s is None:
            raise HTTPException(status_code=404, detail="session ไม่พบ")
        s.deleted_at = None
        db.commit()
        return {"ok": True, "session_id": session_id}
    finally:
        db.close()


@router.get("/sessions/{session_id}/messages")
def get_messages(session_id: int):
    db = SessionLocal()
    try:
        messages = (
            db.query(ChatMessage)
            .filter(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at)
            .all()
        )

        def safe_load(s):
            try:
                return json.loads(s) if s else None
            except Exception:
                return None

        return [
            {
                "role": m.role,
                "content": m.content,
                "result_data": safe_load(m.result_data),
            }
            for m in messages
        ]
    finally:
        db.close()


@router.delete("/sessions/{session_id}")
def delete_session(session_id: int, hard: bool = False):
    """Soft delete by default (Heuristic Eval H3 fix) — restorable for 30 days
    Use ?hard=true to permanently delete (skips trash, cannot undo)
    """
    db = SessionLocal()
    try:
        session = db.query(ChatSession).filter(ChatSession.session_id == session_id).first()
        if not session:
            return {"ok": True}
        if hard:
            db.delete(session)
        else:
            session.deleted_at = datetime.now(timezone.utc)
        db.commit()
        return {"ok": True, "soft": not hard}
    finally:
        db.close()


@router.post("/chat")
def chat(req: ChatRequest):
    """Q&A chat endpoint — Claude วิเคราะห์ + ตอบกลับ

    ดู CLAUDE.md Section 5 — Claude เป็นผู้ตัดสิน verdict เดียว
    ไม่มี preliminary_status anchoring (Section 5.2)
    PII masked ก่อนส่งให้ Claude (Section 2.8)

    Prefill flow (Section 4.7):
    - ถ้ามี prefill_token → resolve เป็น raw text, ใช้แทน req.text
    - prefill_token เป็น one-shot (consume แล้วหายไป)
    """
    text = req.text or ""

    if req.prefill_token:
        prefilled = consume_input(req.prefill_token)
        if prefilled is None:
            raise HTTPException(status_code=410, detail="prefill_token หมดอายุหรือไม่พบ")
        text = prefilled

    if not text.strip() and not req.image_base64:
        raise HTTPException(status_code=400, detail="ต้องมี text หรือ image_base64")

    db = SessionLocal()
    try:
        response = run_qa(
            db=db,
            text=text,
            session_id=req.session_id,
            image_base64=req.image_base64,
            image_media_type=req.image_media_type,
        )
        return response.to_dict()
    except QAAnalysisError as e:
        # ไม่มี default verdict — บอก user ตรงๆ ว่าวิเคราะห์ไม่ได้ (UI แสดง retry)
        raise HTTPException(status_code=502, detail=f"วิเคราะห์ไม่สำเร็จ: {e}") from e
    finally:
        db.close()
