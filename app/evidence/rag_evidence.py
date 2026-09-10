"""
RAG Evidence — เคสคล้ายจากฐานข้อมูล (similar past cases)

ดู CLAUDE.md Section 5.2: เคสคล้ายเป็นบริบทเสริม Claude ใช้พิจารณา
ไม่ใช่ verdict — Claude ตัดสินเองว่าน่าเชื่อแค่ไหน
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.services.rag_service import build_rag_context, retrieve_similar_cases


@dataclass
class RagEvidence:
    similar_cases: list[dict] = field(default_factory=list)
    rag_context_text: str = ""

    @property
    def case_count(self) -> int:
        return len(self.similar_cases)

    def to_evidence_text(self) -> str:
        if not self.similar_cases:
            return "RAG: ไม่เจอเคสคล้ายในฐานข้อมูล"
        return self.rag_context_text


def collect_rag(query: str, top_k: int = 3) -> RagEvidence:
    """ดึง top-k similar cases ผ่าน RAG service"""
    cases = retrieve_similar_cases(query, top_k=top_k)
    context = build_rag_context(cases)
    return RagEvidence(
        similar_cases=cases,
        rag_context_text=context,
    )
