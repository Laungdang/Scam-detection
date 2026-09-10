"""
Pattern Evidence — คำสัญญาณที่พบในข้อความ แยกตามมิติ (raw facts, ไม่ตัดสิน)

ดู CLAUDE.md Section 5.2: ส่งให้ Claude ว่า "พบคำว่า X, Y" — ไม่ใช่ label ที่ตีความแล้ว
เช่น "ด่วน" → รายงานว่า พบคำ "ด่วน" ในมิติ "เร่งให้รีบตัดสินใจ" — ไม่ใช่ "เร่งให้โอนเงิน"
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.services.pattern_service import DimensionMatch, format_evidence, scan_text


@dataclass
class PatternEvidence:
    dimensions: list[DimensionMatch] = field(default_factory=list)  # ทุกมิติ (รวมที่ไม่พบ)

    @property
    def found(self) -> list[DimensionMatch]:
        return [d for d in self.dimensions if d.has_hits]

    @property
    def has_matches(self) -> bool:
        return bool(self.found)

    @property
    def matched_pattern_names(self) -> list[str]:
        """dimension keys ที่พบ — ใช้เก็บ DB column `matched_pattern` และ signals"""
        return [d.dimension for d in self.found]

    @property
    def terms_found(self) -> list[str]:
        out: list[str] = []
        for d in self.found:
            out.extend(d.terms_found)
            out.extend(f"[{r}]" for r in d.regex_hits)
        return out

    def to_evidence_text(self) -> str:
        if not self.dimensions:
            return "คำสัญญาณที่พบ: ไม่ได้สแกน (input ไม่ใช่ข้อความ)"
        return format_evidence(self.dimensions)


def collect_patterns(
    db: Session,  # noqa: ARG001 — คง signature เดิม; lexicon อยู่ใน YAML ไม่ใช่ DB แล้ว
    input_type: str,
    normalized_value: str,
) -> PatternEvidence:
    """สแกนข้อความหาคำสัญญาณทุกมิติ — เก็บเป็น facts, ไม่ตัดสิน"""
    if input_type != "text":
        return PatternEvidence()
    return PatternEvidence(dimensions=scan_text(normalized_value))
