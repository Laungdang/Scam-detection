"""
Blacklist Evidence — เก็บข้อมูล blacklist API เป็น raw facts (ไม่ตัดสิน)

ดู CLAUDE.md Section 5.2 (Anti-Bias) — Q&A mode ห้ามใส่ verdict ใน evidence
คืนแค่ found/not_found + count + raw response เพื่อให้ Claude ตัดสินเอง
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.services.blacklist_flow_service import process_blacklist_check


@dataclass
class BlacklistEvidence:
    checked: bool
    found: bool
    count: int | None
    status: str
    raw_response: dict | None
    checked_value: str | None
    checked_type: str | None
    error: str | None = None

    def to_evidence_text(self) -> str:
        """แปลงเป็นข้อความบรรยาย — ส่งเข้า prompt ของ Claude"""
        if not self.checked:
            return f"Blacklist API: ไม่ได้ตรวจ (รองรับเฉพาะเลขบัญชี/บัตรประชาชน/ชื่อ)"
        if self.error:
            return f"Blacklist API: error ({self.error})"
        if self.found:
            count_str = f" ถูกรายงาน {self.count} ครั้ง" if self.count else ""
            return f"Blacklist API: ✅ พบ{count_str}"
        return f"Blacklist API: ❌ ไม่พบ (ตรวจแล้ว)"


def _extract_count(raw_response: dict | None) -> int | None:
    if not raw_response:
        return None
    result = raw_response.get("result", {})
    for key in ("count", "total", "report_count", "complaint_count", "total_count", "times"):
        if key in result:
            try:
                return int(result[key])
            except (TypeError, ValueError):
                continue
    return None


def collect_main_blacklist(
    db: Session,
    request_id: int,
    input_type: str,
    normalized_value: str,
) -> BlacklistEvidence:
    """ตรวจ blacklist สำหรับ main input (ถ้า type รองรับ)"""
    result = process_blacklist_check(
        db=db,
        request_id=request_id,
        input_type=input_type,
        normalized_value=normalized_value,
    )
    raw = result.get("raw_response")
    return BlacklistEvidence(
        checked=result.get("checked", False),
        found=result.get("found", False),
        count=_extract_count(raw),
        status=result.get("status", "unknown"),
        raw_response=raw,
        checked_value=normalized_value if result.get("checked") else None,
        checked_type=input_type if result.get("checked") else None,
        error=result.get("message") if result.get("status") in ("error", "limit_exceeded") else None,
    )


@dataclass
class EntitiesBlacklistEvidence:
    """ผลรวม blacklist ของ entity ที่ extract จากข้อความ"""
    entities: list[BlacklistEvidence] = field(default_factory=list)
    any_found: bool = False
    any_checked: bool = False

    def to_evidence_text(self) -> str:
        if not self.entities:
            return ""
        lines = []
        for ev in self.entities:
            if ev.found:
                count_str = f" ({ev.count} ครั้ง)" if ev.count else ""
                lines.append(f"  - entity {ev.checked_value} ({ev.checked_type}): พบใน blacklist{count_str}")
        if not lines:
            return ""
        return "Entity blacklist hits:\n" + "\n".join(lines)


def collect_entity_blacklists(
    db: Session,
    request_id: int,
    extracted_entities: list[dict],
) -> EntitiesBlacklistEvidence:
    """ตรวจ blacklist สำหรับ entity ที่ฝังในข้อความ (เช่น เลขบัญชีในข้อความ chat)"""
    results = []
    any_found = False
    any_checked = False
    for entity in extracted_entities:
        result = process_blacklist_check(
            db=db,
            request_id=request_id,
            input_type=entity["type"],
            normalized_value=entity["value"],
        )
        raw = result.get("raw_response")
        ev = BlacklistEvidence(
            checked=result.get("checked", False),
            found=result.get("found", False),
            count=_extract_count(raw),
            status=result.get("status", "unknown"),
            raw_response=raw,
            checked_value=entity["value"],
            checked_type=entity["type"],
            error=result.get("message") if result.get("status") in ("error", "limit_exceeded") else None,
        )
        results.append(ev)
        if ev.found:
            any_found = True
        if ev.checked:
            any_checked = True
    return EntitiesBlacklistEvidence(
        entities=results,
        any_found=any_found,
        any_checked=any_checked,
    )
