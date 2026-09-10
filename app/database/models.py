from sqlalchemy import Column, Integer, String, Text, TIMESTAMP, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.database.connection import Base


class User(Base):
    __tablename__ = "users"

    user_id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100))
    email = Column(String(150), unique=True)
    created_at = Column(TIMESTAMP, server_default=func.now())

    check_requests = relationship("CheckRequest", back_populates="user")


class ScamPattern(Base):
    __tablename__ = "scam_patterns"

    pattern_id = Column(Integer, primary_key=True, index=True)
    pattern_name = Column(String(150), nullable=False)
    keyword = Column(Text, nullable=False)
    description = Column(Text)
    created_at = Column(TIMESTAMP, server_default=func.now())


class AdviceTemplate(Base):
    __tablename__ = "advice_templates"

    advice_id = Column(Integer, primary_key=True, index=True)
    advice_title = Column(String(150), nullable=False)
    advice_text = Column(Text, nullable=False)
    status_type = Column(String(50), nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now())


class CheckRequest(Base):
    __tablename__ = "check_requests"

    request_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True)
    mode = Column(String(10), nullable=False, server_default="qa")  # "ml" | "qa"
    input_type = Column(String(50), nullable=False)
    input_text = Column(Text, nullable=False)  # masked เท่านั้น (PDPA — ดู CLAUDE.md 2.8)
    input_hash = Column(String(64), nullable=True, index=True)  # SHA256(raw + salt) สำหรับ dedup
    created_at = Column(TIMESTAMP, server_default=func.now())

    user = relationship("User", back_populates="check_requests")
    result = relationship("CheckResult", back_populates="request", uselist=False, cascade="all, delete")
    blacklist_checks = relationship("BlacklistCheck", back_populates="request", cascade="all, delete")


class CheckResult(Base):
    __tablename__ = "check_results"

    result_id = Column(Integer, primary_key=True, index=True)
    request_id = Column(Integer, ForeignKey("check_requests.request_id", ondelete="CASCADE"), nullable=False)
    result_status = Column(String(50), nullable=False)
    matched_pattern = Column(Text)
    ai_summary = Column(Text)
    created_at = Column(TIMESTAMP, server_default=func.now())

    request = relationship("CheckRequest", back_populates="result")
    response_logs = relationship("ResponseLog", back_populates="result", cascade="all, delete")


class BlacklistCheck(Base):
    __tablename__ = "blacklist_checks"

    blacklist_check_id = Column(Integer, primary_key=True, index=True)
    request_id = Column(Integer, ForeignKey("check_requests.request_id", ondelete="CASCADE"), nullable=False)
    checked_value = Column(Text, nullable=False)
    checked_type = Column(String(50), nullable=False)
    api_status = Column(String(50))
    api_response = Column(Text)
    checked_at = Column(TIMESTAMP, server_default=func.now())

    request = relationship("CheckRequest", back_populates="blacklist_checks")


class ResponseLog(Base):
    __tablename__ = "response_logs"

    response_id = Column(Integer, primary_key=True, index=True)
    result_id = Column(Integer, ForeignKey("check_results.result_id", ondelete="CASCADE"), nullable=False)
    response_text = Column(Text, nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now())

    result = relationship("CheckResult", back_populates="response_logs")


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    session_id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now())
    # Soft delete (Heuristic Eval H3 fix) — set deleted_at instead of DELETE row
    # Cron job purges rows where deleted_at < now - 30 days
    deleted_at = Column(TIMESTAMP, nullable=True, index=True)

    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete", order_by="ChatMessage.created_at")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    message_id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("chat_sessions.session_id", ondelete="CASCADE"), nullable=False)
    role = Column(String(10), nullable=False)  # "user" or "bot"
    content = Column(Text, nullable=False)
    result_data = Column(Text, nullable=True)  # JSON ผลการวิเคราะห์
    created_at = Column(TIMESTAMP, server_default=func.now())

    session = relationship("ChatSession", back_populates="messages")


class UserConsent(Base):
    """PDPA มาตรา 19 — เก็บ consent record สำหรับ data processing
    ดู CLAUDE.md Section 2.8 (Consent Mechanism)
    """
    __tablename__ = "user_consents"

    consent_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=True)
    session_token = Column(String(128), nullable=True, index=True)  # สำหรับ anonymous user
    consent_version = Column(String(20), nullable=False)  # "v1.0", "v1.1" ของ Privacy Notice
    accepted_at = Column(TIMESTAMP, server_default=func.now())
    ip_hash = Column(String(64), nullable=True)  # SHA256 ของ IP สำหรับ audit (ไม่เก็บ IP ดิบ)
    withdrawn_at = Column(TIMESTAMP, nullable=True)


class PIIAccessLog(Base):
    """PDPA มาตรา 39 — audit log ทุกครั้งที่เข้าถึง raw PII
    ดู CLAUDE.md Section 2.8 (Audit Log)
    """
    __tablename__ = "pii_access_log"

    log_id = Column(Integer, primary_key=True, index=True)
    request_id = Column(Integer, ForeignKey("check_requests.request_id", ondelete="SET NULL"), nullable=True)
    accessed_field_type = Column(String(50), nullable=False)  # "phone" | "bank_acct" | "thai_id" | ...
    accessor_service = Column(String(100), nullable=False)  # "blacklist_service.check_blacklist"
    input_hash = Column(String(64), nullable=False, index=True)  # ไม่เก็บ raw PII, เก็บ hash
    timestamp = Column(TIMESTAMP, server_default=func.now())