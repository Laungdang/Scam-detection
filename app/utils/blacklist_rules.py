def should_check_blacklist(input_type: str) -> bool:
    """
    กำหนดว่าประเภทข้อมูลใดควรถูกส่งไปตรวจ Blacklist API
    """
    return input_type in {"bank_account", "national_id", "fullname"}