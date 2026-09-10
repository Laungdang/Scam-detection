# Datasheet — Thai Scam Detection Corpus (Data v2)

รูปแบบตาม Gebru et al. (2021) *Datasheets for Datasets* — ใช้เป็น appendix ของ thesis
**Version:** 2.0 (2026-08-29) | **ไฟล์:** `data/raw/scam_corpus.jsonl` | **Schema:** `ml/scrape/schema.py`
**สถิติ:** รัน `python -m ml.scrape.validate_corpus` (ตัวเลขด้านล่าง ณ 2026-08-29)

---

## 1. Motivation

**สร้างเพื่ออะไร:** train/evaluate ML classifier (ML mode) และเป็นฐานเคสอ้างอิง (RAG) ของ Q&A mode ในระบบตรวจสอบมิจฉาชีพภาษาไทย (CLAUDE.md Section 1)

**ทำไมต้องสร้างเอง:** ไม่มี public Thai scam message dataset ขนาดพอใช้ (ตรวจ HF/Kaggle/GitHub 2026-05 และ 2026-08 — มีเฉพาะ IMC25 ที่มี Thai subset 65 ข้อความ)

**ใครสร้าง:** ผู้ทำ thesis (คนเดียว) — ยังไม่มี annotator คนที่ 2 (ดู §7 ข้อจำกัด)

**บทเรียนที่นำมาสู่ v2:** v1 (2026-05) มี 1,672 records แต่ตรวจสอบที่มาได้แค่ 80; ชุด RAG 1,088 เคสถูกสร้างโดย LLM พร้อมชื่อสำนักข่าวที่ตามไม่ได้ (fabricated provenance) → v2 บังคับ tier + provenance ทุก record (CLAUDE.md 10.1)

## 2. Composition

### 2.1 หน่วยข้อมูล
1 record = 1 ข้อความ (SMS/LINE/แชท) หรือ 1 บทความเตือนภัย (tier N) พร้อม label + provenance

### 2.2 Tier (CLAUDE.md 10.2)

| tier | ชื่อ | n | verdict | ใช้ train | val | test | RAG |
|---|---|---|---|---|---|---|---|
| A | real_thai — scam ไทยจริง มี URL | **80** | danger 80 | ✅ | ✅ | ✅ | ✅ |
| S | safe_real — ข้อความไทยปกติจริง | **500** | safe 500 | ✅ | ✅ | ✅ | (เฉพาะไม่ใช่ Wisesight) |
| B | real_foreign — IMC25 EN แปลไทย | **584** | danger 584 | ✅ | ✅ | ❌ | ❌ |
| C | synthetic — Typhoon 508 + Kaggle TU 341 | **849** | danger 621 / caution 30 / safe 198 | เฉพาะ approved (**146** — Kaggle "normal" ที่ A1 review 2026-08-30 ว่าเป็นข้อความปกติจริง; ที่เหลือ 703 pending) | ❌ | ❌ | ❌ |
| N | narrative — บทความ AFNC/ThaiCERT | **1,519** | danger 1,480 / safe 39 | ❌ | ❌ | ❌ | ✅ |
| | **รวม** | **3,191** | | usable train 1,164 | 1,164 | 580 | 2,099 |

### 2.3 แหล่ง

| แหล่ง | tier | n | ช่วงเวลา | license | extraction |
|---|---|---|---|---|---|
| Anti Fake News Center (กระทรวงดีอี) — หมวดอาชญากรรมออนไลน์ | N (+A 3) | 1,159 | 2022-09 → 2026-08 | fair use academic | WP REST API, snapshot sha256 |
| ThaiCERT (สกมช.) — ข่าวสารภัยคุกคาม (กรอง consumer scam) | N | 363 | 2024 → 2026-08 | fair use academic | WP REST API, snapshot sha256 |
| IMC 2025 Smishing Dataset — Thai subset | A | 65 | 2023-2024 | CC-BY-4.0 | CSV verbatim |
| IMC 2025 — English subset แปลไทย (Google Translate) | B | 584 | 2023-2024 | CC-BY-4.0 | translated |
| Police Region 9, Ngern Tid Lor, Bangkok Biznews | A | 12 | 2024-2025 | fair use academic | verbatim_html (manual seed, URL preserved) |
| PyThaiNLP Wisesight Sentiment | S | 500 | 2019 | CC0 | verbatim |
| Typhoon v2.5 (SCB 10X) few-shot จาก tier A | C | 508 | 2026-05 | synthetic | llm_generated, **pending_review** |
| [Kaggle: Thai Scam From online Platforms (kkorakott)](https://www.kaggle.com/datasets/kkorakott/thai-scam-from-online-platforms-dataset) — บริบทนักศึกษา TU | C | 341 (จาก 2,999 แถว) | 2026 (v1) | CC BY-NC-SA 4.0 | template-generated + augmentation; label เป็น rule (risk_score threshold) **ไม่ใช่ human label**; card อ้างว่าเก็บจาก platform จริงแต่ข้อมูลไม่สอดคล้อง (ตรวจ 2026-08-29) — ใช้เป็น external comparison (`ml/kaggle_tu_compare.py`) |

### 2.4 Label
- `verdict`: danger / caution / safe — ปัจจุบัน **ไม่มี caution** ใน corpus (v1 label เป็น binary; guideline v2 เพิ่ม caution แล้ว รอ re-annotate)
- `category` (9): financial_fraud, impersonation_authority, phishing_link, romance_scam, investment_scam, prize_scam, borrowing_scam, loan_offer, other
- tier N category มาจาก keyword rule (`annotation.final.resolved_by = keyword_rule`) — ใช้เป็น hint สำหรับ RAG เท่านั้น
- **สถานะ annotation:** tier A/S ทั้ง 580 records ยังเป็น weak label จาก source (`resolved_by = source_weak_label`, `guideline_version = null`) — ยังไม่ผ่าน 2-annotator protocol
- **IAA pilot (2026-08-30, guideline v1.1):** A1 (ผู้ทำ thesis) vs A2 บน 7 calibration template จาก Kaggle-TU comparison — κ = 0.77 (substantial; ต่อ record n=14: 0.63), ไม่ตรง 1 (รอ adjudicator); ชุดเพิ่ม 12 ข้อ A2 ตรง guideline 11/12 — ดู `data/processed/iaa_round1_report.md`; **ยังไม่ใช่ κ ของ corpus** (n=7, synthetic text)
- **IAA รอบ 2 (2026-08-30, blind sheet 40 แถว, guideline v1.3):** A1 vs A2 **κ = 0.24 (fair)** — pilot รอบ 1 สูงเกินจริง; A1 (ผู้เขียน) ตรง guideline แค่ 23/40 → guideline v1.3 มีกฎที่แม้ผู้เขียนก็ไม่ใช้ตอน blind (opener→caution, DM เดี่ยว→caution, metadata→safe) และ A2 อ่านโจทย์กลับด้าน 3 แถว → นำไปสู่ **guideline v2.0** (2026-08-31: verdict = สถานะการกระทำ, 9 สัญญาณ, needs_info บังคับ)
- **IAA รอบ 4 (2026-08-31, v2.1, quiz, 3 annotator):** A1 vs guideline κ 0.88; **A1 vs A3 κ 0.61** (substantial — คู่แรกที่ถึงเกณฑ์ ≥ 0.6); A1 vs A2 0.27, A2 vs A3 0.30 (A2 = strict annotator, retest 0.88 แต่ danger 28/39); mean pairwise 0.39; majority 2/3 มี 37/39 แถว ตรง guideline 31/37 → **guideline v2.2** ตาม majority 6 แถว (`data/processed/iaa_round4_report.md`) — κ ที่รายงานใน thesis: A1/A3 บน 39 แถว v2.1 = 0.61; tier A annotation ใช้คู่ A1+A3
- **IAA รอบ 3 (2026-08-31, v2.0, 39 แถว):** A1 vs guideline κ **0.71** (design ตรงผู้เขียน) แต่ A1 vs A2 κ **0.27** — A2 ให้ danger 28/38 (รวม OTP ที่ระบบส่ง) แม้ quick card มี self-test → ต้อง training A2 หรือเปลี่ยนคน; 2 คำตัดสินค้าง (marketplace โอนก่อน caution/danger, ขอเลขบัญชีจะโอนให้ safe/danger) — `data/processed/iaa_round3_report.md`; **ยังไม่ annotate tier A**

### 2.5 สิ่งที่ไม่มีใน corpus
- SMS ปกติจริง (แจ้งยอด/OTP/โปรโมชั่นถูกกฎหมาย) — tier S ทั้งหมดเป็น social media text → model v1 เรียน "ข้อความทางการ = scam" (ดู §7)
- ข้อความจาก collection form (consent) — ยังไม่เปิด form

## 3. Collection Process

| ขั้น | เครื่องมือ | reproducible |
|---|---|---|
| Thai verbatim seeds | `ml/scrape/seed_verbatim.py` | ✅ deterministic id |
| IMC25 Thai / EN→TH | `ml/scrape/imc25_dataset.py`, `imc25_english_translated.py` | ✅ (แปลอาจต่างเล็กน้อยตาม Google Translate) |
| Wisesight | `ml/scrape/wisesight_safe.py --limit 500` | ✅ seed |
| Typhoon synthetic | `ml/scrape/typhoon_synthetic.py` → `typhoon_review.py` | ❌ LLM non-deterministic (เก็บ output ไว้แล้ว) |
| AFNC / ThaiCERT | `ml/scrape/wp_news.py --site all --max-pages 30` | ✅ per-post snapshot ใน `data/raw/snapshots/wp/` (local) |
| v1 → v2 migration | `ml/scrape/migrate_v2.py` (backup `data/archive/scam_corpus.v1.jsonl`) | ✅ |

robots.txt ของ AFNC/ThaiCERT ตรวจ 2026-08-29: อนุญาต; ใช้ WP REST API (public) rate 1 req/0.8s; User-Agent ระบุว่าเป็นงานวิจัย

## 4. Preprocessing

- **PII:** ทุก record ผ่าน `pii_masker.mask_pii(text, "strict")` ตอน migrate (`pii.masked = true`) — URL เหลือ scheme+domain, เบอร์/บัญชี/เลขบัตร → mask; tier N mask ตอน embed RAG
- known false positive: เลข tracking 10+ หลัก อาจถูก mask เป็นเลขบัญชี (พบ 1 ใน 39 ที่เปลี่ยน)
- **Split (`ml/preprocess.py`):** test = tier A∪S เท่านั้น (30% ของ A∪S), val = A∪S 15% + B 15%, train = ที่เหลือ + C approved; tier N ไม่เข้า ML
- **Test lock:** ยังไม่ lock (2026-08-29) — จะ lock เมื่อ tier A ถึงเป้า 300 หรือก่อน train v2 ครั้งแรก (CLAUDE.md 10.5)

## 5. Uses

| ใช้ได้ | ใช้ไม่ได้ |
|---|---|
| train/eval Thai scam classifier — **รายงาน metric บน tier A∪S แยกเสมอ** | อ้างว่า metric บน B/C สะท้อนของจริง |
| RAG สำหรับ Q&A (tier A, N — มี URL ให้ cite) | ใช้ tier N train ML (เป็นบทความ ไม่ใช่ข้อความ scam) |
| วิเคราะห์ distribution ของ scam type ตามข่าวหน่วยงาน (tier N, 2022-2026) | สรุปสถิติอาชญากรรมจริง (เป็น sample ของข่าว ไม่ใช่ population) |

## 6. Distribution & Maintenance

- อยู่ใน repo (private) — ถ้าเผยแพร่ต้องตัด tier N body (fair use เฉพาะงานวิจัย) เหลือ URL + snapshot_hash
- อัพเดท: รัน `wp_news.py --since YYYY-MM-DD` รายเดือน; record ใหม่เข้า train/val เท่านั้นหลัง test lock
- Archive v1: `data/archive/` (README ในนั้น)
- ติดต่อ: ผู้ทำ thesis (repo owner)

## 7. Known Limitations (สำหรับบท Limitations)

1. **tier A เล็ก (80)** — public Thai scam text หายาก; เป้า 300 ผ่าน collection form เป็นหลัก — **หมายเหตุ 2026-09-01:** รูปในบทความ AFNC เป็นแบนเนอร์ทั่วไป ไม่ใช่ screenshot SMS (ข้อสรุปเดิมว่า "OCR ได้ tier A หลายร้อย" ผิด) เหลือแค่ข้อความที่บทความ quote (`data/raw/sources/wp_quote_candidates.jsonl`) ที่ต้องคนคัด
2. **ไม่มี inter-annotator agreement** — label ทั้งหมดเป็น weak label จาก source; κ ยังรายงานไม่ได้
3. **tier S ไม่ใช่ SMS** — Wisesight เป็น social media → distribution shift; model v1 ตัดสิน OTP/แจ้งยอดธนาคารจริงเป็น danger
4. **tier B pattern shift** — แปลเครื่อง, บริบทต่างประเทศ (IRS, $); v1 error rate บน translated 12% vs verbatim 6.5%
5. **tier C ยังไม่ review** — 508 records ไม่ถูกใช้จนกว่ามีคน approve
6. **tier N category เป็น keyword rule** — ไม่ใช่ human label; 83 records = other
7. **quote candidates (630)** จากบทความ — ส่วนใหญ่เป็นชื่อเพจ/สินค้า ไม่ใช่ข้อความ scam; ต้องคัดมือก่อนเป็น tier A
8. **Kaggle TU dataset ไม่ใช่ข้อมูลจริงตามที่ card อ้าง** — 2,999 แถว = 341 template × augmentation (emoji/typo/suffix "line: @fakeid", "ส่งในกลุ่มได้เลย"); label ทำนายได้ 100% จาก `risk_score_expected` (สูตร keyword rule) และข้อความเดียวกันไม่เคยได้ label ต่างกัน → เป็น rule-label; label "suspicious" ของเขาขัดกับ guideline เรา (เช่น "ของถูกมาก แต่ต้องจองภายในวันนี้" = suspicious ทั้งที่ไม่มีการขอ) — ถ้า train ตรงๆ จะเรียน rule กลับมา จึงใช้เป็น external comparison เท่านั้น
   - **ผล comparison (2026-08-29, `data/processed/kaggle_tu_report_prefix.md` / `_postfix.md`):** ระบบเรา vs rule-label ตรงกัน 82.8% (236/285) ก่อนแก้ → 88.6% (263/297) หลังแก้ lexicon/prompt; ต่างข้ามขั้ว safe↔danger 2 → 1; 44-56 template เป็น "คำขอถึงบอท" (ขอแนวข้อสอบ) ระบบตอบ off_topic ซึ่งถูกต้องในบริบท production
   - 49 เคสที่ต่าง ถูก LLM judge (guideline-strict) + skeptic ตัดสิน 2 รอบ: ก่อนแก้ เราตรง guideline 16/49, Kaggle 31/49; หลังแก้ เรา 31/49 — **ไม่ใช่ ground truth** (14 เคส judge/skeptic เห็นต่าง รอคน 2 คน) และ 49 เคส = ~20 template จริง; ข้อเสนอแก้ guideline อยู่ใน `data/ANNOTATION_GUIDELINE_v1.1_proposal.md`
   - **บทเรียนเชิงระบบ** (ใส่บท Discussion): (ก) lexicon ที่รายงาน "ไม่พบ" ทำให้ LLM anchor ไปทาง safe ได้เท่ากับที่ "พบ" anchor ไปทาง danger — lexicon ต้องครอบคลุมภาษาบริบทผู้ใช้ (inbox/DM/แอดมินคณะ/หมดสิทธิ์) และ evidence ต้องบอกว่าเป็นรายการจากคำที่รู้จักเท่านั้น; (ข) regex จำนวนเงินเปิด RAG ให้ประกาศงานค่าจ้างปกติ → เคส scam ถูกยกมาเป็นข้อเท็จจริง (แยกเป็นมิติ `amount_mention` แล้ว); (ค) ระบบเดิมไม่แยกทิศทางเงิน (ผู้ซื้อขอพร้อมเพย์ผู้ขาย) — ยังเหลือ 5 template ที่ Claude ให้ caution แม้เพิ่มกฎแล้ว
   - safe candidates สำหรับ tier S (Kaggle normal ∧ เรา safe): 146 template → `data/processed/kaggle_tu_safe_candidates_postfix.jsonl` (ต้องคนกวาดตา)
