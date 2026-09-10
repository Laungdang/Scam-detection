from sqlalchemy.orm import Session

from app.database.models import (
    CheckRequest,
    CheckResult,
    BlacklistCheck,
    ResponseLog,
    ScamPattern,
    AdviceTemplate,
    PIIAccessLog,
)


def create_pii_access_log(
    db: Session,
    request_id: int | None,
    accessed_field_type: str,
    accessor_service: str,
    input_hash: str,
) -> PIIAccessLog:
    """บันทึก audit log ทุกครั้งที่เข้าถึง raw PII (PDPA มาตรา 39)
    เก็บแค่ input_hash ไม่เก็บ raw value
    """
    entry = PIIAccessLog(
        request_id=request_id,
        accessed_field_type=accessed_field_type,
        accessor_service=accessor_service,
        input_hash=input_hash,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def create_check_request(db: Session, user_id: int | None, input_type: str, input_text: str) -> CheckRequest:
    new_request = CheckRequest(
        user_id=user_id,
        input_type=input_type,
        input_text=input_text
    )
    db.add(new_request)
    db.commit()
    db.refresh(new_request)
    return new_request


def create_check_result(
    db: Session,
    request_id: int,
    result_status: str,
    matched_pattern: str | None = None,
    ai_summary: str | None = None
) -> CheckResult:
    new_result = CheckResult(
        request_id=request_id,
        result_status=result_status,
        matched_pattern=matched_pattern,
        ai_summary=ai_summary
    )
    db.add(new_result)
    db.commit()
    db.refresh(new_result)
    return new_result


def create_blacklist_check(
    db: Session,
    request_id: int,
    checked_value: str,
    checked_type: str,
    api_status: str | None = None,
    api_response: str | None = None
) -> BlacklistCheck:
    new_check = BlacklistCheck(
        request_id=request_id,
        checked_value=checked_value,
        checked_type=checked_type,
        api_status=api_status,
        api_response=api_response
    )
    db.add(new_check)
    db.commit()
    db.refresh(new_check)
    return new_check


def create_response_log(db: Session, result_id: int, response_text: str) -> ResponseLog:
    new_log = ResponseLog(
        result_id=result_id,
        response_text=response_text
    )
    db.add(new_log)
    db.commit()
    db.refresh(new_log)
    return new_log


def get_all_patterns(db: Session) -> list[ScamPattern]:
    return db.query(ScamPattern).all()


def get_advice_by_status(db: Session, status_type: str) -> AdviceTemplate | None:
    return db.query(AdviceTemplate).filter(AdviceTemplate.status_type == status_type).first()

def update_check_result_ai_summary(db: Session, result_id: int, ai_summary: str) -> CheckResult | None:
    result = db.query(CheckResult).filter(CheckResult.result_id == result_id).first()

    if not result:
        return None

    result.ai_summary = ai_summary
    db.commit()
    db.refresh(result)
    return result