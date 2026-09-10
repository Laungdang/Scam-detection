import requests

from app.config.settings import Settings
from app.services.audit import pii_access_context
from app.utils.logger import get_logger

logger = get_logger("blacklist_service")

# endpoint และ field ที่ต้องส่งแต่ละ type
TYPE_CONFIG = {
    "bank_account": {"endpoint": "bank-summary/", "field": "bank_number"},
    "national_id": {"endpoint": "idcard-summary/", "field": "idcard"},
    "fullname": {"endpoint": "fullname-summary/", "field": None},  # ใช้ first_name/last_name
}

# map domain type → PII field_type สำหรับ audit (PDPA มาตรา 39)
_AUDIT_FIELD_TYPE = {
    "bank_account": "bank_acct",
    "national_id": "thai_id",
    "fullname": "person",
}


def check_blacklist(value: str, value_type: str) -> dict:
    """
    เรียก Blacklist API และคืนผลลัพธ์มาตรฐาน
    Return dict: { success, found, status, raw_response }
    """
    base_url = Settings.BLACKLIST_API_URL
    api_key = Settings.BLACKLIST_API_KEY
    timeout = Settings.BLACKLIST_API_TIMEOUT

    if not base_url:
        return {
            "success": False,
            "found": False,
            "status": "error",
            "raw_response": None,
            "message": "ไม่ได้ตั้งค่า BLACKLIST_API_URL",
        }

    config = TYPE_CONFIG.get(value_type)
    if not config:
        return {
            "success": False,
            "found": False,
            "status": "skipped",
            "raw_response": None,
            "message": f"ไม่มี endpoint สำหรับ type={value_type}",
        }

    url = base_url.rstrip("/") + "/" + config["endpoint"]

    if value_type == "fullname":
        parts = value.strip().split(" ", 1)
        body = {
            "first_name": parts[0],
            "last_name": parts[1] if len(parts) > 1 else "",
        }
    else:
        body = {config["field"]: value}

    headers = {
        "Content-Type": "application/json",
        "X-API-Key": api_key,
    }

    audit_field = _AUDIT_FIELD_TYPE.get(value_type, value_type)
    accessor = f"{__name__}.check_blacklist"

    try:
        # PDPA audit — บันทึก access ก่อนส่ง raw value ออก external API
        with pii_access_context(
            field_type=audit_field,
            input_value=value,
            accessor_service=accessor,
        ):
            response = requests.post(url, headers=headers, json=body, timeout=timeout)

        logger.info(f"Blacklist API response: HTTP {response.status_code} for type={value_type!r}")
        if response.status_code in (429, 402, 403):
            logger.warning(f"Blacklist API quota หมดแล้ว (HTTP {response.status_code}) — type={value_type!r}")
            return {
                "success": False,
                "found": False,
                "status": "limit_exceeded",
                "raw_response": None,
                "message": "Blacklist API: ใช้ quota วันนี้ครบแล้ว",
            }

        response.raise_for_status()
        data = response.json()

        found = data.get("result", {}).get("found", False)
        return {
            "success": True,
            "found": found,
            "status": "found" if found else "not_found",
            "raw_response": data,
        }

    except requests.exceptions.Timeout:
        return {
            "success": False,
            "found": False,
            "status": "error",
            "raw_response": None,
            "message": "Blacklist API timeout",
        }
    except requests.exceptions.RequestException as e:
        return {
            "success": False,
            "found": False,
            "status": "error",
            "raw_response": None,
            "message": str(e),
        }
