---
title: HI-Scammer
emoji: 🛡️
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
---

# HI-Scammer — ระบบตรวจสอบและให้คำปรึกษามิจฉาชีพออนไลน์ (closed pilot)

Q&A mode เท่านั้น (Claude + RAG จากเคสจริงที่มี URL ตรวจย้อนได้) — senior thesis project

การเข้าใช้ต้องมีรหัส (closed pilot) — ขอได้จากผู้ทำวิจัย

## Secrets ที่ Space ต้องมี (Settings → Variables and secrets)

| Secret | คืออะไร |
|---|---|
| `CLAUDE_API_KEY` | Anthropic API key |
| `DATABASE_URL` | Postgres connection string จาก Neon (มี `?sslmode=require`) |
| `PII_SALT` | salt สำหรับ hash PII (สุ่มยาวๆ ครั้งเดียว ห้ามเปลี่ยน) |
| `APP_ACCESS_CODE` | รหัสเข้าใช้งานที่แจกผู้ทดลอง |

ตัวเลือก: `QA_RATE_LIMIT_PER_MINUTE` (default 6), `QA_RATE_LIMIT_PER_DAY` (default 200)

หมายเหตุ: ห้ามตั้ง `ENABLE_ML_MODE=true` บน Space นี้ — image ไม่ได้ลง xgboost/model artifact (ML mode ถูกตัดออกจาก deploy scope 2026-09-10)
