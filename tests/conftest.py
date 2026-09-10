"""
Pytest fixtures + global setup.

ตั้งค่า env vars ที่ต้องมีก่อน `app.config.settings` ถูก import ที่ไหนก็ตาม
(Settings เป็น class-level attributes อ่าน env ที่ import time ครั้งเดียว)
"""

import os

os.environ.setdefault("PII_SALT", "pytest_salt_do_not_use_in_production")
