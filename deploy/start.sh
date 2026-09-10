#!/usr/bin/env bash
# Boot: migrate DB (Neon ผ่าน DATABASE_URL secret) แล้วค่อยเปิด API
set -u

echo "[start] running alembic migrations..."
if python -m alembic upgrade head; then
    echo "[start] migrations OK"
else
    # ไม่ block การ start — /api/config ยังต้องขึ้นเพื่อให้เห็น error ชัดใน log
    echo "[start] WARN: migration failed — ตรวจ DATABASE_URL secret (ต้องมี ?sslmode=require)"
fi

exec uvicorn app.api.main:app --host 0.0.0.0 --port "${PORT:-7860}"
