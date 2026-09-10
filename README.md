# HI-Scammer — ระบบตรวจสอบและให้คำปรึกษามิจฉาชีพออนไลน์

> **EN:** Thai scam detection & advisory system (senior thesis, in progress 2026).
> A Claude-powered conversational advisor grounded in a provenance-verified case corpus (RAG),
> built on a strict evidence-not-verdict architecture with PDPA-compliant PII masking,
> and a research-grade data pipeline: tiered provenance, versioned annotation guideline
> validated through 4 blind inter-annotator rounds (Cohen's κ 0.24 → 0.61/0.88).

ผู้ใช้ส่งข้อความ/เบอร์/เลขบัญชี/ลิงก์/ภาพที่สงสัยมาถาม ระบบวิเคราะห์จากหลักฐานจริง
(blacklist ตำรวจ, คำสัญญาณ 15 มิติ, เคสจริงที่คล้ายกัน) แล้วตอบเป็นภาษาคน:
**ทำได้ / เช็ค X ก่อน / อย่าทำ + แจ้ง 1441** — พร้อมบอกเสมอว่าตัดสินจากอะไร

> ⚠️ โปรเจควิจัย (thesis) — ไม่ใช่บริการของหน่วยงานรัฐ ผลวิเคราะห์ไม่ใช่คำวินิจฉัยทางกฎหมาย
> หากเสียหายแล้วให้ติดต่อ **1441** (AOC) หรือแจ้งความที่ [thaipoliceonline.go.th](https://thaipoliceonline.go.th)

---

## สถาปัตยกรรม

```
ผู้ใช้ (ข้อความ/ภาพ/เสียง)
        │
        ▼
┌─────────────────────────── Q&A Engine ───────────────────────────┐
│                                                                  │
│  1. Normalize + OCR (EasyOCR → Claude Vision fallback)           │
│  2. เก็บหลักฐาน (ข้อเท็จจริงล้วน ไม่มีคำตัดสินล่วงหน้า):          │
│       • Blacklist API (ฐานตำรวจ) — จำนวนครั้งที่ถูกรายงาน        │
│       • Scam Lexicon 15 มิติ — คำที่พบจริง + มิติที่ "ไม่พบ"      │
│       • RAG — เคสจริงที่คล้าย (bge-m3, มี gate กันข้อความปกติ)    │
│       • ประวัติแชท (เป็นหลักฐาน ไม่ใช่เพดานบังคับ)               │
│  3. Mask PII ทุก field (PDPA) → สร้าง prompt                     │
│  4. Claude ตัดสิน — จุดตัดสินใจจุดเดียวของระบบ                   │
│  5. ตอบ + needs_info ถามกลับเมื่อข้อมูลไม่พอ                     │
└──────────────────────────────────────────────────────────────────┘
```

หลักออกแบบสำคัญ (รายละเอียดเต็มใน [CLAUDE.md](CLAUDE.md)):

| หลักการ | ความหมาย |
|---|---|
| **Evidence, not verdict** | ทุก signal เป็นข้อเท็จจริงดิบ — ห้าม layer ไหนตัดสินก่อนถึงผู้ตัดสิน (กัน LLM anchoring) |
| **Single decision point** | Claude ตัดสินครั้งเดียว ไม่มี code override/severity floor ทับคำตอบ |
| **Fail fast** | LLM ตอบเพี้ยน → HTTP 502 ให้ retry — ไม่มีทาง default เป็น "ปลอดภัย" เงียบๆ |
| **PDPA by design** | เลขบัตร/บัญชี/เบอร์ ถูก mask ก่อนออกจาก memory ทุกทาง (Claude, DB, log, UI) + consent + right-to-forget |
| **ข้อมูลไม่พอ ≠ ปลอดภัย** | verdict `caution` ต้องระบุว่าให้เช็คอะไร (`needs_info`) แล้วระบบถามกลับ |

> โหมด ML classifier (TF-IDF/XGBoost/WangchanBERTa) มีในโค้ดแต่**ปิดไว้** (`ENABLE_ML_MODE=false`)
> — จะเปิดเมื่อ corpus จริงถึงเป้า (ดู "ข้อมูล" ด้านล่าง) ระหว่างนี้เก็บเป็น baseline ของ thesis

## ข้อมูล (จุดที่งานนี้ต่างจากระบบทั่วไป)

ทุก record ใน corpus ต้อง **ตรวจย้อนแหล่งที่มาได้** — แบ่ง tier ชัดเจน:

| Tier | คือ | ใช้ทำอะไร |
|---|---|---|
| A `real_thai` | ข้อความ scam ไทยจริง มี URL/consent ตรวจได้ | train / **test (tier เดียวที่ได้)** / RAG |
| S `safe_real` | ข้อความปกติจริง | train / test |
| B `real_foreign` | scam จริงภาษาอื่นแปลไทย (IMC25) | train เท่านั้น |
| C `synthetic` | LLM สร้าง (ผ่าน human review เท่านั้น) | train เท่านั้น |
| N `narrative` | เคสเล่าเรื่องจากข่าว/หน่วยงาน (มี URL + snapshot hash) | RAG เท่านั้น |

- เกณฑ์ตัดสิน = [ANNOTATION_GUIDELINE](data/ANNOTATION_GUIDELINE.md) v2.2 — ผ่าน blind test 4 รอบ
  กับผู้ตัดสิน 3 คน (κ A1/A3 = 0.61, ผู้เขียน-vs-เกณฑ์ = 0.88) ปรับกฎด้วยเสียงข้างมาก ไม่ใช่อำนาจผู้เขียน
- System prompt ถูก regression test กับเกณฑ์ทุกเวอร์ชัน (`ml/guideline_eval.py` — 38/39)
- ที่มา/license รายแหล่ง + ข้อจำกัด: [data/DATACARD.md](data/DATACARD.md)
  (IMC25 CC-BY-4.0, Wisesight CC0, Kaggle TU CC BY-NC-SA 4.0, AFNC/ThaiCERT fair-use academic)

## Tech Stack

FastAPI · PostgreSQL + SQLAlchemy + Alembic · Claude API (Haiku) · ChromaDB + **BAAI/bge-m3** ·
PyThaiNLP (ตัดคำ lexicon) · EasyOCR (+Claude Vision fallback เฉพาะ Q&A) · Vanilla JS SPA

## Setup

```bash
pip install -r requirements.txt          # dev เต็ม (มี torch/easyocr)
cp .env.example .env                     # แล้วเติมค่า: CLAUDE_API_KEY, DB, PII_SALT
python -m alembic upgrade head           # สร้าง/อัพเดตตาราง
python scripts/setup_rag.py              # สร้าง vector DB จาก corpus (โหลด bge-m3 ~2.2GB ครั้งแรก)
python -m uvicorn app.api.main:app --port 8000
# เปิด http://localhost:8000
```

ตัวแปรสำคัญใน `.env` (ดู [.env.example](.env.example) ทั้งหมด):

| ตัวแปร | ทำอะไร |
|---|---|
| `APP_ACCESS_CODE` | รหัสเข้าใช้ (closed pilot) — **ต้องตั้งเสมอถ้าเปิดออกเน็ต** |
| `QA_RATE_LIMIT_PER_MINUTE/DAY` | จำกัดการเรียก Claude ต่อ IP (default 6/นาที, 200/วัน) |
| `DATABASE_URL` | ใช้ hosted Postgres (Neon ฯลฯ) แทน DB local |
| `ENABLE_ML_MODE` | เปิดโหมด ML (default ปิด) |

## Deploy

- **ทดลอง/pilot:** `powershell -File scripts\run_pilot.ps1` — รัน API + Cloudflare quick tunnel ได้ URL สาธารณะทันที
- **Hugging Face Space (Docker):** `python scripts/deploy_hf.py --space <user>/<name>` — ประกอบเฉพาะไฟล์ runtime, ตั้ง secrets จาก `.env` ให้อัตโนมัติ (ดู [deploy/](deploy/))

## API หลัก

| Endpoint | ทำอะไร |
|---|---|
| `POST /api/qa/chat` | วิเคราะห์/คุยต่อ — `{text, session_id?, image_base64?}` (ต้องมี header `X-Access-Code` ถ้าตั้งรหัส) |
| `GET/POST/DELETE /api/qa/sessions*` | จัดการประวัติแชท (soft-delete + กู้คืนได้) |
| `GET /api/config` | ค่าที่ UI ต้องรู้ (โหมดที่เปิด, ต้องใส่รหัสไหม) |
| `POST /api/ml/detect` | (เฉพาะเมื่อ `ENABLE_ML_MODE=true`) |

## ทดสอบ

```bash
python -m pytest                          # unit + prompt-contract tests
python -m ml.guideline_eval --workers 4   # regression: ระบบ vs เกณฑ์ annotation 39 ข้อ (เรียก Claude จริง)
python -m ml.rag_eval                     # คุณภาพ retrieval (โหลด bge-m3)
```

## เอกสาร

- [CLAUDE.md](CLAUDE.md) — design document ฉบับเต็ม: หลักการ, pipeline, anti-patterns, changelog การตัดสินใจทั้งหมด
- [data/DATACARD.md](data/DATACARD.md) — datasheet ของ corpus (ตาม Gebru et al. 2021)
- [data/ANNOTATION_GUIDELINE.md](data/ANNOTATION_GUIDELINE.md) — เกณฑ์ตัดสิน v2.2 + calibration set 39 ข้อ
- [data/README.md](data/README.md) — โครงสร้างไฟล์ข้อมูล

## สถานะ

🎓 Senior thesis, กำลังพัฒนา (2026) — corpus จริง (tier A) กำลังขยายผ่านการเก็บข้อมูลแบบมี consent
ตาม PDPA ม.19 · โค้ดนี้เผยแพร่เพื่อการศึกษา — ผู้เขียนสงวนสิทธิ์การใช้เชิงพาณิชย์ของข้อมูลตาม license ต้นทางแต่ละแหล่ง
