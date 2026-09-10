from pydantic import BaseModel, Field


class CheckRequestSchema(BaseModel):
    user_id: int | None = None
    input_text: str = Field(..., min_length=1, description="ข้อความหรือข้อมูลที่ผู้ใช้ส่งมาตรวจสอบ")