# data/ — Thai Scam Detection Corpus (Data v2)

> เอกสารหลัก: **[DATACARD.md](DATACARD.md)** (datasheet — สถิติ, แหล่ง, ข้อจำกัด)
> กติกา label: **[ANNOTATION_GUIDELINE.md](ANNOTATION_GUIDELINE.md)**
> design rationale: CLAUDE.md Section 10 (Training Data Strategy v2)
> ผล v1 + lesson learned: [WEEK4_FINDINGS.md](WEEK4_FINDINGS.md), [archive/README.md](archive/README.md)

## โครงสร้าง

```
data/
├── raw/
│   ├── scam_corpus.jsonl            ← corpus หลัก (schema v2: tier + provenance + annotation)
│   ├── sources/
│   │   ├── imc25_raw.csv            ← IMC25 ต้นฉบับ (cache)
│   │   ├── typhoon_pending.jsonl    ← synthetic รอ review
│   │   ├── typhoon_reviewed.jsonl
│   │   └── wp_quote_candidates.jsonl← ข้อความใน "..." จากบทความ — ต้องคนยืนยันก่อนเป็น tier A
│   └── snapshots/wp/{site}/{id}.json← raw post JSON (gitignored, hash อยู่ใน record)
├── processed/                       ← train/val/test (จาก ml/preprocess.py) + TEST_LOCK.json (เมื่อ lock)
├── lexicon/scam_lexicon.yaml        ← คำสัญญาณ 12 มิติ (Q&A evidence + annotation checklist)
├── archive/                         ← Data v1 artifacts — ห้ามใช้ train/eval v2
├── chroma_db/                       ← RAG (สร้างจาก tier A+N ด้วย scripts/setup_rag.py)
├── DATACARD.md
├── ANNOTATION_GUIDELINE.md
└── WEEK4_FINDINGS.md
```

## Record (schema v2 ย่อ)

```json
{
  "id": "wp-afnc-1a2b3c4d",
  "text": "...",
  "verdict": "danger", "category": "phishing_link",
  "tier": "N",
  "source": {"name": "...", "url": "https://...", "scraped_at": "...", "extraction_method": "verbatim_html",
             "published_date": "...", "license": "fair_use_academic", "snapshot_hash": "sha256...", "consent_id": null},
  "annotation": {"labels": [...], "final": {"verdict": "...", "category": "...", "resolved_by": "keyword_rule"}, "guideline_version": null},
  "review": null,
  "pii": {"masked": true, "masker_version": "...", "pii_found_count": 0}
}
```

tier: **A** real_thai · **S** safe_real · **B** real_foreign (แปล) · **C** synthetic · **N** narrative (RAG only) — กฎการใช้ดู `ml/scrape/schema.py::TIER_ALLOWED_IN`

## คำสั่งที่ใช้บ่อย

```bash
python -m ml.scrape.validate_corpus                 # สถิติ + ตรวจ schema v2
python -m ml.scrape.wp_news --site all --since 2026-09-01   # ดึงบทความใหม่ (AFNC + ThaiCERT)
python -m ml.scrape.typhoon_review                  # review synthetic → approved/rejected
python -m ml.preprocess --task multi                # split ตาม tier rules (ใช้ lock ถ้ามี)
python -m ml.preprocess --task multi --lock-test    # lock test set (ครั้งเดียว)
python -m scripts.setup_rag                         # rebuild chroma จาก tier A + N (ตัด digest/ข่าวต่างประเทศ)
python -m ml.rag_eval                               # วัด retrieval hit@3 + benign leak (14 คำถาม)
```

## สถานะ (2026-08-29)

| | n |
|---|---|
| tier A real_thai | 80 (เป้า 300) |
| tier S safe_real | 500 (Wisesight — ต้องการ SMS ปกติจริง) |
| tier B translated | 584 |
| tier C synthetic | 849 = Typhoon 508 + Kaggle TU 341 — approved 146 (safe บริบทนักศึกษา, A1 review 2026-08-30), pending 703 |
| tier N narrative | 1,519 (AFNC 1,156 + ThaiCERT 363) |
| annotated ตาม guideline v1.1 | 0 (A1 ตัดสิน calibration 14 เคสแล้ว — รอ A2 ตอบ blind sheet) |
| test lock | ยังไม่ lock |

**Guideline:** v1.1 (2026-08-29) — quick card + needs_info + calibration 39 แถว; A2 ใช้ `annotation/v1.1_calibration_blind.csv` + `processed/A2_annotation_packet.md` แล้วรัน `python -m ml.annotation.agreement --a processed/kaggle_tu_human_adjudication.jsonl --b <A2 jsonl>`

งานถัดไป: A2 blind sheet → κ → collection form (consent) → OCR screenshot ใน tier N → 2-annotator pass บน tier A/S → lock test → retrain v2
