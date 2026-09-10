from pydantic import BaseModel


class AnalysisResponseSchema(BaseModel):
    status: str
    input_type: str
    matched_patterns: list[str]
    blacklist_found: bool
    reason_text: str | None = None
    ai_summary: str | None = None
    advice_text: str | None = None