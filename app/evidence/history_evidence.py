"""
History Evidence — chat history ของ session ปัจจุบัน + severity สะสม
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.database.models import ChatMessage


_SEVERITY_ORDER = {"safe": 0, "caution": 1, "danger": 2}


@dataclass
class HistoryEvidence:
    messages: list[dict] = field(default_factory=list)  # [{"role": ..., "content": ...}]
    prev_max_severity: str = "safe"

    @property
    def turn_count(self) -> int:
        return len(self.messages)

    def to_evidence_text(self) -> str:
        if not self.messages:
            return "ประวัติการสนทนา: ไม่มี (เป็น turn แรก)"
        prev_max = self.prev_max_severity
        # ข้อเท็จจริง: verdict สูงสุดที่ Claude เองให้ไว้ใน turn ก่อน — ไม่ใช่ floor
        # Claude ตัดสินเองว่าหลักฐานใหม่ทำให้ควรคง/ลด/เพิ่ม (CLAUDE.md 2.3)
        return (
            f"ประวัติการสนทนา: {self.turn_count} ข้อความก่อนหน้า, "
            f"verdict สูงสุดที่คุณเคยให้ในเรื่องนี้ = {prev_max} "
            f"(ทบทวนใหม่ได้ถ้าข้อมูลใหม่เปลี่ยนภาพรวม เช่น ผู้ใช้ยืนยันว่าเป็นคนรู้จักจริง)"
        )


def collect_history(db: Session, session_id: int | None, max_messages: int = 10) -> HistoryEvidence:
    """โหลด chat history ของ session — คำนวณ severity สะสม"""
    if not session_id:
        return HistoryEvidence()

    msgs = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at)
        .all()
    )

    history: list[dict] = []
    prev_max = "safe"
    for m in msgs[-max_messages:]:
        history.append({"role": m.role, "content": m.content})
        if m.role == "bot" and m.result_data:
            try:
                data = json.loads(m.result_data)
                ui_type = data.get("type", "safe")
                if _SEVERITY_ORDER.get(ui_type, 0) > _SEVERITY_ORDER.get(prev_max, 0):
                    prev_max = ui_type
            except Exception:
                continue

    return HistoryEvidence(messages=history, prev_max_severity=prev_max)
