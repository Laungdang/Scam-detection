"""
PII Access Audit — PDPA มาตรา 39

Decorator สำหรับ wrap function ที่เข้าถึง raw PII โดยอัตโนมัติ
บันทึกลง pii_access_log โดยเก็บแค่ input_hash ไม่เก็บค่าจริง

ดู CLAUDE.md Section 2.8 (Audit Log) + Section 6.5

Design constraint:
- ห้ามบันทึกค่า PII ดิบลง log/exception/print
- การบันทึก audit ต้อง best-effort — ถ้า DB ล่ม ต้องไม่ block main flow
- รองรับทั้ง sync function

Usage:
    @audit_pii_access(field_type="bank_acct")
    def check_blacklist(value: str, value_type: str) -> dict:
        ...

    # หรือ wrap แบบ context-aware:
    with PIIAccessContext(field_type="phone", input_value=phone):
        result = external_api_call(phone)
"""

from __future__ import annotations

import functools
import logging
from contextlib import contextmanager
from typing import Callable, Iterator

from app.database.connection import SessionLocal
from app.database.repository import create_pii_access_log
from app.services.pii_masker import hash_value

logger = logging.getLogger("audit")


def _record(
    field_type: str,
    accessor_service: str,
    input_value: str,
    request_id: int | None = None,
) -> None:
    """internal — write audit log, swallow any error"""
    try:
        db = SessionLocal()
        try:
            create_pii_access_log(
                db=db,
                request_id=request_id,
                accessed_field_type=field_type,
                accessor_service=accessor_service,
                input_hash=hash_value(input_value),
            )
        finally:
            db.close()
    except Exception as exc:
        # ห้าม block main flow — audit fail = log warning only
        logger.warning(f"PII audit log failed: {exc!r}")


def audit_pii_access(field_type: str, value_arg: str = "value") -> Callable:
    """Decorator: บันทึก audit log ก่อนเรียก function ที่เข้าถึง PII

    Args:
        field_type: ประเภท PII ("phone", "bank_acct", "thai_id", ...)
        value_arg: ชื่อ kwarg ที่เก็บค่า PII (default "value")
    """
    def decorator(func: Callable) -> Callable:
        service_name = f"{func.__module__}.{func.__name__}"

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            value = kwargs.get(value_arg)
            if value is None and args:
                # หา positional arg ตามชื่อใน signature
                import inspect
                sig = inspect.signature(func)
                params = list(sig.parameters)
                if value_arg in params:
                    idx = params.index(value_arg)
                    if idx < len(args):
                        value = args[idx]

            if value:
                _record(
                    field_type=field_type,
                    accessor_service=service_name,
                    input_value=str(value),
                )
            return func(*args, **kwargs)
        return wrapper
    return decorator


@contextmanager
def pii_access_context(
    field_type: str,
    input_value: str,
    accessor_service: str,
    request_id: int | None = None,
) -> Iterator[None]:
    """Context manager สำหรับเคสที่ decorator ไม่สะดวก (เช่น loop, dynamic field_type)

    with pii_access_context("bank_acct", account_number, "ml_engine.detect"):
        result = blacklist_service.check(account_number)
    """
    _record(
        field_type=field_type,
        accessor_service=accessor_service,
        input_value=input_value,
        request_id=request_id,
    )
    yield
