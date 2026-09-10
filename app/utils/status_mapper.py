def map_status_to_thai(status: str) -> str:
    mapping = {
        "suspicious": "เข้าข่ายน่าสงสัย",
        "unclear": "ยังสรุปไม่ได้",
        "non_suspicious": "ยังไม่พบข้อมูลชี้ชัด",
    }
    return mapping.get(status, status)