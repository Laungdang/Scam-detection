"""
Q&A Assistant Engine — orchestrator สำหรับ Q&A Mode

หลักการ (ดู CLAUDE.md Section 5 — Q&A Pipeline):
- Stage 1: Input normalization (audio/image)
- Stage 2: Evidence collection (blacklist, pattern, RAG, history) — raw facts
- Stage 3: PII Masking + Prompt construction — Claude ไม่เห็น raw PII
- Stage 4: LLM inference (Claude เป็น SOLE decider)
- Stage 5: Parse + validate (ไม่ override verdict)
- Stage 6: Persist (masked + hash)

ไม่มี preliminary verdict / status override — ดู Section 2.1, 2.3, 5.2
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.database.models import ChatMessage, ChatSession, CheckRequest, CheckResult
from app.evidence.blacklist_evidence import (
    EntitiesBlacklistEvidence,
    collect_entity_blacklists,
    collect_main_blacklist,
)
from app.evidence.history_evidence import HistoryEvidence, collect_history
from app.evidence.pattern_evidence import PatternEvidence, collect_patterns
from app.evidence.rag_evidence import RagEvidence, collect_rag
from app.services.ai_service import analyze_with_ai
from app.services.pii_masker import hash_value, mask_pii
from app.utils.input_processor import process_user_input


_OFF_TOPIC_MSG = (
    "ขอโทษครับ ผมช่วยได้เฉพาะเรื่องตรวจสอบมิจฉาชีพเท่านั้น "
    "ถ้ามีเบอร์โทร เลขบัญชี ลิงก์ หรือข้อความน่าสงสัย ลองส่งมาให้ผมดูได้เลยครับ"
)


class QAAnalysisError(Exception):
    """Claude ไม่สามารถให้ verdict ได้ (API ล่ม / parse JSON ไม่ได้ / verdict ผิด format)

    ห้าม fallback เป็น verdict ใดๆ — ต้อง fail fast ให้ route คืน error ชัดเจน
    (CLAUDE.md ข้อ 8: ห้าม `except: pass` แล้วใช้ default status)
    """


@dataclass
class QAResponse:
    type: str  # "danger" | "caution" | "safe" | "chat"
    ai_summary: str
    ai_structured: dict | None
    signals: list[str]
    blacklist: dict
    session_id: int

    def to_dict(self) -> dict:
        return {
            "type": self.type,
            "ai_summary": self.ai_summary,
            "ai_structured": self.ai_structured,
            "signals": self.signals,
            "blacklist": self.blacklist,
            "session_id": self.session_id,
        }


def run_qa(
    db: Session,
    text: str,
    session_id: int | None = None,
    image_base64: str | None = None,
    image_media_type: str | None = None,
) -> QAResponse:
    """Pipeline เต็มของ Q&A mode

    ดู CLAUDE.md Section 5.1 Stage 1-6
    """

    # ─────────────────────────────────────────────────────
    # STAGE 1: Input normalization
    # ─────────────────────────────────────────────────────
    processed = process_user_input(text)
    original_input = processed["original_input"]
    input_type = processed["input_type"]
    normalized_value = processed["normalized_value"]
    extracted_entities = processed.get("extracted_entities", [])

    # ─────────────────────────────────────────────────────
    # STAGE 2: Evidence collection (raw facts only, no verdict)
    # ─────────────────────────────────────────────────────
    masked = mask_pii(original_input, mode="strict")
    request_record = CheckRequest(
        user_id=None,
        mode="qa",
        input_type=input_type,
        input_text=masked.masked,
        input_hash=hash_value(original_input),
    )
    db.add(request_record)
    db.commit()
    db.refresh(request_record)

    blacklist_ev = collect_main_blacklist(db, request_record.request_id, input_type, normalized_value)
    entities_ev = collect_entity_blacklists(db, request_record.request_id, extracted_entities)
    pattern_ev = collect_patterns(db, input_type, normalized_value)
    rag_ev = collect_rag(original_input)
    history_ev = collect_history(db, session_id)

    blacklist_found = blacklist_ev.found or entities_ev.any_found
    blacklist_checked = blacklist_ev.checked or entities_ev.any_checked
    # รวม hit count ทุกแหล่ง (main + entities) ส่งให้ Claude ใช้ Hard Constraints
    total_blacklist_hits = (blacklist_ev.count or 0) if blacklist_ev.found else 0
    for ev in entities_ev.entities:
        if ev.found and ev.count:
            total_blacklist_hits += ev.count
    blacklist_hit_count: int | None = total_blacklist_hits if blacklist_found else None

    # ─────────────────────────────────────────────────────
    # STAGE 3-5: PII mask + prompt + Claude (Claude is sole decider)
    # ─────────────────────────────────────────────────────
    masked_input_for_prompt = mask_pii(original_input, mode="strict").masked
    masked_history = [
        {"role": m["role"], "content": mask_pii(m["content"], mode="strict").masked}
        for m in history_ev.messages
    ]

    ai_result = analyze_with_ai(
        original_input=masked_input_for_prompt,
        input_type=input_type,
        matched_pattern_names=pattern_ev.matched_pattern_names,
        blacklist_found=blacklist_found,
        blacklist_hit_count=blacklist_hit_count,
        chat_history=masked_history,
        image_base64=image_base64,
        image_media_type=image_media_type,
        pattern_evidence_text=pattern_ev.to_evidence_text(),
        history_evidence_text=history_ev.to_evidence_text(),
        skip_rag=not should_use_rag(input_type, pattern_ev, bool(image_base64)),
    )

    # Fail fast — ไม่มี default verdict (CLAUDE.md ข้อ 8)
    if not ai_result.get("success"):
        raise QAAnalysisError(ai_result.get("message") or "Claude analysis failed")
    structured = ai_result.get("structured")
    if not isinstance(structured, dict):
        raise QAAnalysisError("Claude ตอบไม่ใช่ JSON ตามรูปแบบ — ไม่สามารถสรุปผลได้")

    # ─────────────────────────────────────────────────────
    # STAGE 6: Persist (NO preliminary override — Claude verdict wins)
    # ─────────────────────────────────────────────────────
    session_id = _ensure_session(db, session_id, text, ai_result)

    response_type = structured.get("response_type", "analysis")

    if response_type in ("chat", "off_topic"):
        return _build_chat_response(db, session_id, text, structured, response_type)

    return _build_analysis_response(
        db=db,
        request_id=request_record.request_id,
        session_id=session_id,
        text=text,
        ai_result=ai_result,
        blacklist_ev=blacklist_ev,
        entities_ev=entities_ev,
        pattern_ev=pattern_ev,
        history_ev=history_ev,
    )


def _ensure_session(
    db: Session, session_id: int | None, user_text: str, ai_result: dict
) -> int:
    if session_id:
        return session_id
    title = (ai_result.get("structured") or {}).get("title", "").strip()
    if not title:
        title = user_text[:40] + ("..." if len(user_text) > 40 else "")
    session = ChatSession(title=title)
    db.add(session)
    db.commit()
    db.refresh(session)
    return session.session_id


def _build_chat_response(
    db: Session,
    session_id: int,
    user_text: str,
    structured: dict,
    response_type: str,
) -> QAResponse:
    if response_type == "off_topic":
        message = _OFF_TOPIC_MSG
    else:
        message = structured.get("message", "")
    response_data = {
        "type": "chat",
        "ai_summary": message,
        "ai_structured": None,
        "signals": [],
        "blacklist": {"checked": False, "found": False, "hits": []},
    }
    masked_user = mask_pii(user_text, mode="strict").masked
    masked_bot = mask_pii(message, mode="strict").masked
    db.add(ChatMessage(session_id=session_id, role="user", content=masked_user))
    db.add(
        ChatMessage(
            session_id=session_id,
            role="bot",
            content=masked_bot,
            result_data=json.dumps(response_data, ensure_ascii=False),
        )
    )
    db.commit()
    return QAResponse(
        type="chat",
        ai_summary=message,
        ai_structured=None,
        signals=[],
        blacklist={"checked": False, "found": False, "hits": []},
        session_id=session_id,
    )


def _build_analysis_response(
    db: Session,
    request_id: int,
    session_id: int,
    text: str,
    ai_result: dict,
    blacklist_ev,
    entities_ev: EntitiesBlacklistEvidence,
    pattern_ev: PatternEvidence,
    history_ev: HistoryEvidence,
) -> QAResponse:
    structured = ai_result.get("structured") or {}
    # Claude เป็น single decision point — ไม่มี floor/override จาก history หรือ code อื่น
    # (CLAUDE.md 2.3) severity สะสมของ turn ก่อนถูกส่งให้ Claude เป็น evidence แล้ว
    # (history_ev.to_evidence_text) — Claude เป็นคนตัดสินว่าจะคงหรือลด
    ui_type = resolve_claude_verdict(structured)

    blacklist_hits = _extract_blacklist_hits(blacklist_ev, entities_ev)
    signals = _build_signals(blacklist_hits, pattern_ev)
    bl_limit_exceeded = (
        blacklist_ev.status == "limit_exceeded"
        or any(ev.status == "limit_exceeded" for ev in entities_ev.entities)
    )

    response_data = {
        "type": ui_type,
        "reason": "—".join(s for s in signals[:3]) or "พิจารณาจากบริบทสนทนา",
        "advice": structured.get("follow_up", ""),
        "ai_summary": ai_result.get("summary_text") or "",
        "ai_structured": structured,
        "signals": signals,
        "blacklist": {
            "checked": blacklist_ev.checked or entities_ev.any_checked,
            "found": blacklist_ev.found or entities_ev.any_found,
            "hits": blacklist_hits,
            "limit_exceeded": bl_limit_exceeded,
        },
    }

    # save CheckResult (verdict จาก Claude — ไม่มี preliminary)
    db.add(
        CheckResult(
            request_id=request_id,
            result_status=ui_type,
            matched_pattern=", ".join(pattern_ev.matched_pattern_names) or None,
            ai_summary=ai_result.get("summary_text"),
        )
    )

    masked_user = mask_pii(text, mode="strict").masked
    masked_bot = mask_pii(ai_result.get("summary_text") or "", mode="strict").masked
    db.add(ChatMessage(session_id=session_id, role="user", content=masked_user))
    db.add(
        ChatMessage(
            session_id=session_id,
            role="bot",
            content=masked_bot,
            result_data=json.dumps(response_data, ensure_ascii=False),
        )
    )
    db.commit()

    return QAResponse(
        type=ui_type,
        ai_summary=ai_result.get("summary_text") or "",
        ai_structured=structured,
        signals=signals,
        blacklist=response_data["blacklist"],
        session_id=session_id,
    )


def _extract_blacklist_hits(blacklist_ev, entities_ev: EntitiesBlacklistEvidence) -> list[dict]:
    hits = []
    if blacklist_ev.found and blacklist_ev.checked:
        masked_value = mask_pii(blacklist_ev.checked_value or "", mode="display").masked
        hits.append({
            "value": masked_value,
            "type": blacklist_ev.checked_type,
            "count": blacklist_ev.count,
        })
    for ev in entities_ev.entities:
        if ev.found:
            masked_value = mask_pii(ev.checked_value or "", mode="display").masked
            hits.append({
                "value": masked_value,
                "type": ev.checked_type,
                "count": ev.count,
            })
    return hits


VALID_VERDICTS = ("danger", "caution", "safe")

# มิติที่ "ไม่พอ" ให้ดึง RAG ด้วยตัวเอง — "ด่วน" หรือชื่อแบรนด์อย่างเดียวพบในข้อความปกติตลอด
# (ml/rag_eval.py: "ส่งงานด่วน" ดึง SMS ปลอม SCB มาที่ 0.61 ถ้าปล่อยผ่านด้วย urgency)
RAG_WEAK_DIMENSIONS = frozenset({"urgency", "authority_claim", "amount_mention", "reward", "inbound_payment_offer"})


def should_use_rag(input_type: str, pattern_ev: PatternEvidence, has_image: bool) -> bool:
    """RAG gate — ดึงเคสคล้ายเฉพาะเมื่อมีอะไรให้เทียบ "โครงเรื่อง"

    - เบอร์/บัญชี/URL/ภาพ → ดึงเสมอ (ไม่มี text ให้ scan)
    - text → ต้องมีคำสัญญาณอย่างน้อย 1 มิติที่ไม่ใช่ urgency/authority_claim
    embedding จับผิวคำ: ข้อความปกติที่มีแค่ "ด่วน" จะได้ scam คล้ายผิวมาประกอบ = anchoring
    """
    if input_type != "text" or has_image:
        return True
    strong = {d.dimension for d in pattern_ev.found if d.dimension not in RAG_WEAK_DIMENSIONS}
    found = {d.dimension for d in pattern_ev.found}
    # ทิศทางเงินกลับด้าน (ผู้ส่งจะโอน "ให้" ผู้ใช้) และการขอที่พบมีแค่คำว่า โอน/บัญชี → เคสคล้าย
    # "ถูกขอข้อมูลบัญชี" จะ anchor ผิดเรื่อง (guideline v1.1 Q3) — ไม่ดึง RAG
    if "inbound_payment_offer" in found and strong <= {"money_request"}:
        return False
    return bool(strong)


def resolve_claude_verdict(structured: dict) -> str:
    """ดึง verdict จาก structured response ของ Claude — ไม่มี default

    verdict ผิด format = ระบบตอบไม่ได้ ต้อง raise ไม่ใช่เดา "safe" (ทิศทางอันตราย:
    scam จริงแต่ parse พัง → บอก user ว่าปลอดภัย)
    """
    verdict = (structured or {}).get("verdict", "")
    if verdict not in VALID_VERDICTS:
        raise QAAnalysisError(f"Claude ส่ง verdict ที่ไม่รู้จัก: {verdict!r}")
    return verdict


def _build_signals(blacklist_hits: list[dict], pattern_ev: PatternEvidence) -> list[str]:
    """สัญญาณที่โชว์ user — ข้อเท็จจริง (คำที่พบ) ไม่ใช่การตีความ"""
    signals = []
    for hit in blacklist_hits:
        count_str = f" ({hit['count']} ครั้ง)" if hit.get("count") else ""
        signals.append(f"พบใน blacklist: {hit['value']}{count_str}")
    for dim in pattern_ev.found:
        parts = [f'"{t}"' for t in dim.terms_found] + [f"[{r}]" for r in dim.regex_hits]
        signals.append(f"{dim.label_th}: {', '.join(parts)}")
    if not signals:
        signals.append("ไม่พบคำสัญญาณหรือ blacklist")
    return signals
