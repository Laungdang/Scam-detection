# Scam Detection System — Design Document

เอกสารฉบับนี้คือ **single source of truth** ของสถาปัตยกรรมโปรเจค ทุก design decision ในนี้ผ่านการคิดเรื่องหลักการออกแบบซอฟต์แวร์, ML pipeline, และข้อโต้แย้งทางวิชาการที่อาจารย์เคยให้ feedback มาแล้ว ห้าม implement สวนทางกับเอกสารฉบับนี้โดยไม่อัพเดทเอกสารก่อน

---

## 1. ภาพรวมโปรเจค

**ชื่อ:** ระบบตรวจสอบและให้คำปรึกษามิจฉาชีพออนไลน์ (Scam Detection & Advisory System)

**ปัญหาที่แก้:**
- คนไทยจำนวนมาก (โดยเฉพาะผู้สูงอายุ) ถูกหลอกผ่าน SMS, โทรศัพท์, LINE, ลิงก์ปลอม
- ผู้ใช้ทั่วไปต้องการเครื่องมือเช็คเร็วๆ ว่าข้อมูลที่ได้รับเป็นมิจฉาชีพหรือไม่
- บางกรณีต้องการคำแนะนำเชิงสนทนาเพิ่มเติม ไม่ใช่แค่ผลตรวจ

**ผู้ใช้งาน:** ประชาชนทั่วไป โดยเฉพาะกลุ่มผู้สูงอายุและผู้ที่ไม่คุ้นเคยกับเทคโนโลยี

**Input ที่รองรับ:** ข้อความ, เบอร์โทรศัพท์, เลขบัญชีธนาคาร, เลขบัตรประชาชน, URL, รูปภาพ (screenshot), เสียง (audio → transcribe เป็นข้อความ)

**หมายเหตุ Audio:** Audio ไม่ใช่ input type แยก — เป็นแค่ช่องทาง input (input modality) ที่ระบบ transcribe เป็น text แล้วเข้า pipeline เดียวกับ text input ใช้ประโยชน์กับกลุ่มผู้สูงอายุที่พิมพ์ลำบาก

---

## 2. หลักการออกแบบหลัก (Design Principles)

หลักการเหล่านี้คือ **non-negotiable** ทุก code ในระบบต้องสอดคล้อง

### 2.1 No Premature Decision (ไม่ตัดสินก่อนเก็บหลักฐานครบ)

**ปัญหาเดิมที่อาจารย์ติ:** ระบบเก่า (commit ก่อนหน้า) ตัดสิน `status = suspicious / unclear / non_suspicious` ตั้งแต่ขั้น regex pattern matching แล้วส่งคำตัดสินไปให้ LLM ดู → LLM bias ไปยืนยันคำตัดสิน → context อื่น (RAG, chat history, รูป) กลายเป็นของประดับ

**หลักการใหม่:**
- ทุก signal (blacklist hit, regex match, text features, metadata) ถือเป็น **หลักฐาน (evidence)** เท่านั้น ไม่ใช่ **คำตัดสิน (verdict)**
- การตัดสินเกิดขึ้นที่ **จุดเดียว** ที่ปลายทาง pipeline เห็นหลักฐานครบทุกอย่าง
- ห้าม layer กลางตัดสินใจอะไรที่ส่งผลต่อ output สุดท้าย

### 2.2 Feature-Level Fusion (สำหรับ ML Mode)

โมเดล ML ต้องรับ feature **ทั้งหมดพร้อมกัน** เป็น vector เดียว ไม่ใช่ cascade gate:

```
ผิด (cascade):  blacklist → ถ้าพบ = scam จบ, ถ้าไม่พบ → regex → ถ้า match = scam จบ, ถ้าไม่ → ML
ถูก (fusion):    [blacklist_hit_count, regex_flags, tfidf_vector, url_features] → ML → verdict
```

เหตุผล: cascade ทำให้ feature ปลายๆ ไม่มีโอกาสมีน้ำหนัก และทำให้ model ไม่สามารถเรียนรู้ interaction ระหว่าง feature ได้ (เช่น ข้อความปกติ + blacklist 1 hit อาจจะ safe, แต่ข้อความเร่งร้อน + blacklist 1 hit คือ scam)

### 2.3 Single Decision Point per Pipeline

แต่ละ mode มีจุดตัดสินใจ **จุดเดียว** เท่านั้น:
- **ML Mode:** จุดตัดสินคือ `model.predict()` ครั้งเดียว
- **Q&A Mode:** จุดตัดสินคือ LLM response ครั้งเดียว

ห้ามมีการ "preprocess decision" หรือ "post-override decision" ใน layer อื่น

### 2.4 Mode Isolation

ทั้ง 2 mode (ML และ Q&A) ต้อง **เป็นอิสระ 100%**:
- ไม่มี shared decision logic
- ไม่มี service ที่ "รู้" ว่าตัวเองอยู่ใน mode ไหน
- เปลี่ยน/ลบ mode ใดได้โดยไม่กระทบอีก mode

shared ได้แต่: data access (blacklist API, OCR, DB), preprocessing utilities, response templates

### 2.5 Explainability

ทุกการตัดสินต้อง **อธิบายได้**:
- **ML Mode:** ต้องโชว์ top-k features ที่ทำให้ตัดสิน (feature importance / SHAP)
- **Q&A Mode:** LLM ต้องบอกหลักฐานที่ใช้ในคำตอบ

ห้ามมี "black box" ที่ตอบโดยไม่บอกเหตุผล

### 2.6 Reproducibility (สำหรับ ML Mode)

- การ train ต้อง deterministic (fix random seed)
- เก็บ model artifact + version + training data hash
- inference เดิม input → เดิม output ทุกครั้ง (ไม่เหมือน LLM)

### 2.7 Separation of Concerns

แต่ละ layer มีหน้าที่เดียว ห้ามปนกัน:

```
[I/O Layer]        ← FastAPI routes, Streamlit UI
[Orchestration]    ← เลือก mode, ส่งต่อ
[Mode Engine]      ← ML pipeline หรือ Q&A pipeline
[Feature/Signal]   ← extract features, collect evidence
[Data Access]      ← API client, DB repository
[Domain Logic]     ← preprocessing, normalization
```

I/O layer ห้าม call data access ตรง ๆ Mode engine ห้ามรู้เรื่อง HTTP

### 2.8 PII Minimization (PDPA Compliance)

ข้อมูลที่ผู้ใช้ส่งมามี PII ตาม พ.ร.บ. คุ้มครองข้อมูลส่วนบุคคล (PDPA) — เลขบัตรประชาชน, เลขบัญชี, เบอร์โทร, ชื่อ-นามสกุล โปรเจคนี้ต้องปฏิบัติตามหลักการต่อไปนี้:

**กฎเหล็ก 4 ข้อ:**

1. **ห้ามส่ง raw PII ออกนอกระบบโดยไม่มาส์ก** — โดยเฉพาะส่งเข้า Claude API (อยู่ US, ข้อมูลออกนอกประเทศ)
2. **ห้าม persist raw PII ลง DB ในสภาพดิบ** — ต้องมาส์กหรือ hash ก่อน
3. **Raw PII ใช้ได้เฉพาะ in-memory ระหว่าง request เดียวเท่านั้น** — และเฉพาะกับ service ที่ต้องการ exact match (blacklist API)
4. **UI ที่แสดงผลกลับ user ต้องโชว์ masked version** — ป้องกัน shoulder surfing / screenshot leak

**UI Reveal Rule (สำคัญ — ทุก PII บน UI ใช้กฎเดียวกัน):**
- **Default state:** ทุก PII บน UI โชว์ในรูปแบบ `display` mask เสมอ — **ไม่แยก** ว่า PII นั้นเป็นของผู้ใช้เองหรือบุคคลที่ 3
- **Reveal toggle:** ทุก PII บน UI มีปุ่ม 👁 เปิดดูค่าเต็มได้ (local UI state เท่านั้น ไม่ส่งกลับ server, ไม่ persist)
- **เหตุผลที่ไม่แยก "ของใคร":**
  - ระบบไม่มีทางรู้ว่า PII แต่ละชิ้นเป็นของใคร (user อาจพิมพ์เบอร์ตัวเอง + เบอร์มิจฉาชีพในข้อความเดียวกัน)
  - การมี behavior ต่างกันต่อ PII คนละชิ้น = ผู้ใช้สับสน
  - กฎเดียวกันหมด = consistent UX + ง่ายต่อการ implement + defendable ใน thesis ("uniform default-secure with explicit reveal")
- **PDPA-wise ทำได้** เพราะ default = masked (secure), reveal = explicit user action (informed consent ของ user เอง)

**Masking Policy ต่อประเภทข้อมูล:**

| ประเภท | รูปแบบ masked | ตัวอย่าง |
|---|---|---|
| เลขบัตรประชาชน | x-xxxx-xxxxx-xx-x (เก็บ 1 ตัวแรก + 1 ตัวสุดท้าย) | `1-xxxx-xxxxx-xx-5` |
| เลขบัญชีธนาคาร | xxx-x-xx{last4} (เก็บ 4 ตัวท้าย) | `xxx-x-xx5678` |
| เบอร์โทรศัพท์ | xxx-xxx-{last4} (เก็บ 4 ตัวท้าย) | `xxx-xxx-5678` |
| ชื่อ-นามสกุล | first{1}xxx last{1}xxx | `ส***ม ใ***ย` |
| URL | scheme + domain เท่านั้น ตัด path/query | `https://scb-fake.xyz/...` |
| ข้อความทั่วไป | regex-replace PII ที่ฝังในข้อความ | "โอนเงินไป `xxx-x-xx5678`" |

**Hash Policy (สำหรับ dedup/analytics):**
- ใช้ SHA256 + project-wide salt (env var)
- เก็บใน column `input_hash` ของ `check_requests`
- เอาไว้ตอบคำถาม "ผู้ใช้คนนี้เคยส่ง input เดียวกันมาก่อนไหม" โดยไม่ต้องเก็บค่าจริง

**สิ่งที่ต้องอยู่ในเอกสาร thesis ตอน defense:**
- Section อธิบาย PDPA compliance ของระบบ
- Data flow diagram ที่ระบุชัดว่าข้อมูลถูก mask ที่จุดไหน
- คำอธิบายว่าทำไม blacklist API ต้องใช้ raw value (legitimate purpose ภายใต้ PDPA มาตรา 24)

**Consent Mechanism (PDPA มาตรา 19):**
- หน้าแรกของ UI มี Privacy Notice + checkbox "ยอมรับข้อตกลง" ก่อนใช้งาน
- เก็บ consent record ใน table `user_consents` (timestamp, consent_version, ip_hash)
- ถ้า consent version เปลี่ยน (update privacy notice) → บังคับ user ยอมรับใหม่
- มีปุ่ม "ถอน consent + ลบข้อมูล" — เรียก endpoint `/api/user/forget` ลบ record ทั้งหมดของ session/user

**Data Retention Policy:**
| ข้อมูล | ระยะเวลาเก็บ | วิธีลบ |
|---|---|---|
| Raw PII | 0 (in-memory เท่านั้น) | end of request scope |
| Masked input + result | 90 วัน | cron job ทุกวัน DELETE WHERE created_at < NOW() - 90d |
| Input hash (dedup) | 365 วัน | cron job ทุกเดือน |
| Chat session messages | 30 วัน หลัง last activity | cron job |
| Audit log | 1 ปี (PDPA มาตรา 39 ขั้นต่ำ) | archive ก่อนลบ |
| Consent record | จนกว่าจะถอน + 5 ปี (ตามกฎหมาย) | manual |

**Audit Log (PDPA มาตรา 39):**
- Table ใหม่: `pii_access_log` — บันทึกทุกครั้งที่มีการเข้าถึง raw PII
- Field: timestamp, request_id, accessed_field_type, accessor_service (เช่น "blacklist_service"), input_hash (ไม่ใช่ค่าจริง)
- เปิดให้ admin query เพื่อตอบ user ถ้ามีคำขอตามมาตรา 30 (right to access)
- Log ทุก call ที่ผ่าน `blacklist_service.check_blacklist()` อัตโนมัติผ่าน decorator

---

## 3. สถาปัตยกรรมระบบ

### 3.1 High-Level

```
┌─────────────────────────────────────────────────────────────────┐
│                       Streamlit UI                              │
│  ┌──────────────────┐         ┌──────────────────┐              │
│  │ Mode 1:          │         │ Mode 2:          │              │
│  │ ตรวจเร็ว (ML)    │         │ ปรึกษา (Q&A)     │              │
│  └────────┬─────────┘         └────────┬─────────┘              │
└───────────┼──────────────────────────────┼──────────────────────┘
            │                              │
            ▼                              ▼
┌───────────────────────┐        ┌───────────────────────┐
│  POST /api/ml/detect  │        │  POST /api/qa/chat    │
└───────────┬───────────┘        └───────────┬───────────┘
            │                                │
            ▼                                ▼
┌─────────────────────────┐        ┌─────────────────────────┐
│   ML Detection Engine   │        │   Q&A Assistant Engine  │
│  (Pipeline ส่วนที่ 4)    │        │   (Pipeline ส่วนที่ 5)    │
└────────────┬────────────┘        └────────────┬────────────┘
             │                                  │
             └──────────────┬───────────────────┘
                            ▼
              ┌──────────────────────────┐
              │   Shared Infrastructure  │
              │  ─ Preprocessing         │
              │  ─ Input detection       │
              │  ─ Blacklist API client  │
              │  ─ OCR service           │
              │  ─ Audio transcription   │
              │  ─ Database repository   │
              │  ─ Response templates    │
              │  ─ PII Masker (PDPA)     │
              │  ─ Prefill cache         │
              └──────────────────────────┘
```

### 3.2 หลักการแยก Mode

| ประเด็น | ML Mode | Q&A Mode |
|---|---|---|
| **เป้าหมาย** | ตรวจเร็ว ได้คะแนนความเสี่ยง | ให้คำปรึกษาเชิงสนทนา |
| **Latency (ไม่นับ external API)** | ~200-500 ms (TF-IDF+LR) / ~500-1500 ms (BERT บน CPU) | ~1-2 วินาที (Claude inference) |
| **Latency (รวม external API)** | +300-500 ms ถ้า call blacklist | 2-5 วินาที |
| **เก็บ context** | ไม่ (stateless ทุก request) | ใช่ (chat history) |
| **ตัดสินโดย** | ML model | LLM (Claude) |
| **Output verdict** | danger / caution / safe / uncertain | danger / caution / safe |
| **Output extras** | confidence + top features | คำตอบเชิงสนทนา + advice |
| **Per-request API cost** | ~$0 (no external LLM) | ~$0.001-0.005 (Claude API) |
| **Compute footprint** | Model 50MB (LR) / 500MB+ (BERT) RAM resident | Stateless, depends on Claude |
| **อธิบายผลด้วย** | Feature importance / SHAP | LLM citation |
| **เคสที่เหมาะ** | ตรวจครั้งเดียวจบ, batch | ผู้ใช้อยากถาม-ตอบหลายรอบ |

---

## 4. ML Detection Mode — Pipeline แบบละเอียด

### 4.1 Flow ภาพรวม

```
┌────────────────────────────────────────────────────────────────┐
│  INPUT: text / phone / bank / url / image / audio (raw)        │
└────────────────────────────────┬───────────────────────────────┘
                                 │
                                 ▼
┌────────────────────────────────────────────────────────────────┐
│  STAGE 1: Input Normalization                                  │
│  ─ Audio → transcribe เป็น text ก่อน                          │
│  ─ Image → OCR (EasyOCR only, ดู 6.4)                         │
│      └ ถ้า OCR fail/low-conf → set suggest_qa=True ที่ stage 5│
│      └ ถ้าภาพไม่มี text เลย → label="uncertain", suggest_qa   │
│  ─ detect type (regex)                                         │
│  ─ normalize (clean phone format, lowercase URL, strip)        │
│  ─ extract entities (เบอร์/บัญชี ที่ฝังในข้อความ)              │
│  ─ คำนวณ input_hash (SHA256+salt) สำหรับ logging              │
│  OUTPUT: normalized payload (raw, in-memory)                   │
└────────────────────────────────┬───────────────────────────────┘
                                 │
                                 ▼
┌────────────────────────────────────────────────────────────────┐
│  STAGE 2: Signal Collection (parallel)                         │
│  ─ Blacklist API call (ถ้า type รองรับ)                       │
│  ─ Regex pattern scan (เก็บเป็น flag, ไม่ตัดสิน)              │
│  ─ Text feature extraction (TF-IDF / Embedding)                │
│  ─ Metadata features (URL length, digit count, ฯลฯ)            │
│  OUTPUT: dict of raw signals                                   │
└────────────────────────────────┬───────────────────────────────┘
                                 │
                                 ▼
┌────────────────────────────────────────────────────────────────┐
│  STAGE 3: Feature Vector Construction                          │
│  ─ รวมทุก signal เป็น vector เดียวตาม schema คงที่             │
│  ─ handle missing values (เช่น blacklist API ล่ม → use 0)     │
│  OUTPUT: feature vector x ∈ R^n                                │
└────────────────────────────────┬───────────────────────────────┘
                                 │
                                 ▼
┌────────────────────────────────────────────────────────────────┐
│  STAGE 4: Model Inference (จุดตัดสินเดียว)                     │
│  ─ model.predict_proba(x) → probabilities ต่อ class            │
│  ─ no thresholding logic หรือ override ใดๆ ใน stage นี้        │
│  OUTPUT: { class_probs }                                       │
└────────────────────────────────┬───────────────────────────────┘
                                 │
                                 ▼
┌────────────────────────────────────────────────────────────────┐
│  STAGE 5: Post-processing & Explanation                        │
│  ─ argmax → predicted label                                    │
│  ─ ดึง top-k feature importance (SHAP / coef)                  │
│  ─ map class → response template + advice                      │
│  ─ ถ้า confidence < threshold → set suggest_qa=True            │
│  ─ มาส์ก PII ใน response ทุก field ที่จะส่งกลับ user/log       │
│  OUTPUT: structured response (masked)                          │
└────────────────────────────────┬───────────────────────────────┘
                                 │
                                 ▼
┌────────────────────────────────────────────────────────────────┐
│  STAGE 6: Logging                                              │
│  ─ บันทึก masked input + input_hash + signals + prediction     │
│  ─ ห้าม persist raw PII (ดู Section 2.8)                       │
│  ─ ไม่กระทบ response (async ถ้าทำได้)                          │
└────────────────────────────────────────────────────────────────┘
```

### 4.2 ทำไม design นี้ถูก

**ตอบ feedback อาจารย์รอบที่แล้วว่า "ตัดสินก่อน context เลยไม่มีประโยชน์":**
- Stage 2 เก็บ signal ทั้งหมด **พร้อมกัน** ไม่มี short-circuit
- Stage 3 รวมทุก signal เป็น feature vector — blacklist hit เป็นแค่ feature ตัวหนึ่ง, ไม่ใช่ gate
- Stage 4 เป็น **จุดตัดสินเดียว** model เห็นทุก feature พร้อมกันแล้วเลือก class
- ทุก feature มี **weight** ที่ model เรียนรู้จาก data → ไม่มี hardcoded logic

ตัวอย่าง: ถ้า model เรียนรู้ว่า "ข้อความสุภาพ + blacklist 1 hit (อาจเป็น false positive) = safe" → จะตัดสิน safe ได้ ระบบเก่าทำไม่ได้เพราะ blacklist hit จะ trigger suspicious ทันที

### 4.3 ทำไมต้องเก็บ Blacklist API + Regex ไว้

อาจารย์อาจจะถามว่า "ถ้ามี ML แล้วทำไมยังต้องใช้ blacklist + regex?"

**คำตอบ:** ใช้เป็น **feature** ไม่ใช่ **decision rule**
- Blacklist hit count เป็น strong signal (ground truth จากตำรวจ) — model ใช้เป็น feature
- Regex match เป็น keyword feature ที่ interpretable — เสริม TF-IDF
- การมี multi-source feature ทำให้ model robust ต่อ adversarial input (เช่น คนเปลี่ยนคำเลี่ยง regex แต่ blacklist ยังจับได้)

นี่คือ design ตาม principle **defense in depth** ของ classification system

### 4.4 Model Architecture

**Baseline:** TF-IDF + Logistic Regression
- ข้อดี: เร็ว, interpretable (coefficient = importance), เขียน thesis ง่าย
- ใช้เป็น lower bound เปรียบเทียบ

**Main Model:** WangchanBERTa fine-tuned
- Thai pretrained BERT จาก VISTEC
- Fine-tune ด้วย labeled scam dataset
- ใช้เป็นโมเดลหลัก

**Comparison Models (สำหรับ thesis):**
- XGBoost บน combined features
- Random Forest
- (Optional) Multilingual BERT

ทำตารางเปรียบเทียบ accuracy, F1, latency, model size ในเล่ม

### 4.5 Response Schema (`ml_schema.py`)

```python
ScamCategory = Literal[
    "financial_fraud", "impersonation_authority", "phishing_link",
    "romance_scam", "investment_scam", "prize_scam",
    "borrowing_scam", "loan_offer", "other",
]  # 9 หมวด — ตรงกับ ml/scrape/schema.py และ ANNOTATION_GUIDELINE §2 (loan_offer เพิ่มใน corpus ตั้งแต่ v1)

Verdict = Literal["danger", "caution", "safe", "uncertain"]

class MLDetectResponse(BaseModel):
    verdict: Verdict                        # ใช้ vocabulary เดียวกับ Q&A mode
    confidence: float                       # 0.0 - 1.0
    category: ScamCategory | None           # ถ้า verdict != safe: หมวดย่อย
    top_features: list[FeatureContribution] # for explainability
    advice_text: str                        # จาก template
    masked_input: str                       # PII masked แล้ว ส่งกลับ user ได้
    suggest_qa: bool                        # True ถ้า confidence < threshold
    qa_prefill_token: str | None            # token สำหรับ handoff ไป Q&A (ดู 4.7)
    model_version: str                      # "v1.2.3" สำหรับ traceability
    latency_ms: int
```

**Vocabulary Note (สำคัญ):** ทั้ง 2 mode ใช้ vocabulary เดียวกัน — `danger / caution / safe` คือ **severity** (ระดับความเสี่ยง) ไม่ใช่ **class label** เพราะผู้ใช้สนใจ "ระวังแค่ไหน" มากกว่า "เป็น scam หรือไม่" ML mode มี extra value `uncertain` สำหรับเคส confidence ต่ำ ส่วน Q&A mode ไม่มี uncertain เพราะ LLM ต้องตัดสินเสมอ

**`suggest_qa` trigger logic:**
- `confidence < settings.ML_CONFIDENCE_THRESHOLD` (default 0.7, configurable ใน `settings.py`) → True
- `verdict == "uncertain"` → True
- OCR ล้มเหลว/confidence ต่ำ (ดู 6.4) → True
- ภาพไม่มี text → True
- อื่นๆ → False

UI ใช้ flag นี้เพื่อแสดงปุ่ม "ปรึกษา AI ต่อ" (shortcut)

### 4.6 Training Pipeline (แยกจาก inference)

```
data/raw/ → preprocess.py → data/processed/
                                ↓
                          train.py → models/v{N}/model.pkl
                                            + metadata.json
                                            + metrics.json
                                ↓
                          evaluate.py → reports/v{N}/
```

- ทุก train run มี version (semver: `v{major}.{minor}.{patch}` — major=schema เปลี่ยน, minor=feature ใหม่, patch=retrain)
- เก็บ metadata: random seed, dataset hash, hyperparameters, git commit SHA
- inference โหลด model จาก path ที่ระบุใน `settings.MODEL_VERSION`

**Evaluation Methodology (สำคัญสำหรับ thesis):**

- **Cross-validation:** 5-fold stratified CV บน train+val set (รักษา class distribution ในแต่ละ fold)
- **Held-out test set:** 15% locked from start, ใช้รายงาน final metric เท่านั้น (ห้าม tune)
- **Metrics รายงาน:**
  - Per-class: Precision, Recall, F1, Support
  - Aggregate: Macro-F1, Weighted-F1, ROC-AUC, PR-AUC
  - Confusion matrix
  - **ห้ามรายงาน accuracy เป็นตัวหลัก** เพราะ class imbalance ทำให้ misleading
- **Statistical testing:**
  - Model comparison: McNemar's test (paired, สำหรับ binary), 5x2cv F-test (สำหรับ multi-class)
  - Confidence interval: Bootstrap 1000 iterations, 95% CI
  - Significance level: α = 0.05
- **Baselines ที่ต้องเปรียบเทียบ:**
  1. **Majority class** — predict class ที่เยอะที่สุดเสมอ
  2. **Random (stratified)** — random ตามสัดส่วน class
  3. **Keyword-only** — match regex pattern ที่มีอยู่แล้ว
  4. **Blacklist-only** — ตัดสินจาก blacklist API hit อย่างเดียว
  5. **Our ML models** — ทั้ง baseline และ main
- **Error analysis:**
  - confusion matrix per category
  - sample 50 misclassified cases วิเคราะห์ pattern
  - report ใน thesis

**Class Imbalance Strategy:**
- คาดว่า scam vs safe จะ imbalanced (~1:5 ถึง 1:10)
- **sklearn models:** `class_weight='balanced'`
- **Neural models (BERT):** weighted cross-entropy loss
- **Threshold tuning:** optimize threshold on val set แทน default 0.5 → คำนึงถึง precision-recall trade-off ของ use case (false negative = ผู้ใช้โดนหลอก = แย่กว่า false positive = แจ้งเตือนเกิน)
- รายงาน per-class metric เสมอ ไม่ใช่แค่ overall

### 4.7 ML → Q&A Handoff (Cross-Mode Navigation)

ผู้ใช้กดปุ่ม "ปรึกษา AI ต่อ" จากผล ML → ระบบต้องส่งต่อไปยัง Q&A mode โดย**ไม่ทำลาย Mode Isolation (principle 2.4)**

**หลักการ:** โอน **raw input** เท่านั้น — ไม่โอน evidence bundle หรือ feature vector

```
ML Mode                          Q&A Mode
─────────                        ─────────
ML detect → suggest_qa=True   
            ↓
generate prefill_token         
(เก็บ raw input ใน redis/cache  
 TTL 5 นาที, key = token)      
            ↓                  
return response with token  ──→  user click "ปรึกษาต่อ"
                                       ↓
                                 GET /api/qa/chat?prefill={token}
                                       ↓
                                 lookup token → raw input
                                       ↓
                                 Q&A engine collect evidence ใหม่หมด
                                 (blacklist API, RAG, history)
                                       ↓
                                 Claude วิเคราะห์
```

**ทำไมไม่โอน evidence bundle:**
- จะ leak internal state ของ ML engine ไปให้ Q&A engine
- ถ้าเปลี่ยน feature ใน ML mode ทีหลัง → Q&A พังโดยไม่รู้ตัว
- Evidence ใน Q&A อาจจะ stale (blacklist API อัพเดทแล้ว)
- Q&A เก็บ evidence แบบของมันเอง (รวม RAG ที่ ML ไม่มี)

**ข้อแลกเปลี่ยน:** Q&A call blacklist API ซ้ำ → เสีย ~500ms — ยอมรับได้ เพราะ Q&A mode มี budget latency 2-5 วินาทีอยู่แล้ว

---

## 5. Q&A Assistant Mode — Pipeline แบบละเอียด

### 5.1 Flow ภาพรวม

```
┌────────────────────────────────────────────────────────────────┐
│  INPUT: user message + chat_session_id (หรือ prefill_token)    │
└────────────────────────────────┬───────────────────────────────┘
                                 │
                                 ▼
┌────────────────────────────────────────────────────────────────┐
│  STAGE 1: Input Normalization (เหมือน ML Mode)                 │
│  ─ ถ้ามี prefill_token → resolve เป็น raw input ก่อน           │
│  ─ OCR: EasyOCR ก่อน, Claude Vision fallback (ดู 6.4)          │
│  ─ คำนวณ input_hash                                           │
└────────────────────────────────┬───────────────────────────────┘
                                 │
                                 ▼
┌────────────────────────────────────────────────────────────────┐
│  STAGE 2: Evidence Collection                                  │
│  ─ Blacklist API result (raw count, ไม่ใช่ "found:bool")       │
│  ─ Regex matches (raw match list, ไม่ใช่ status)               │
│  ─ Retrieve similar cases จาก RAG (chroma)                     │
│  ─ Load chat history (last N messages)                         │
│  OUTPUT: evidence bundle (facts only, no verdict)              │
└────────────────────────────────┬───────────────────────────────┘
                                 │
                                 ▼
┌────────────────────────────────────────────────────────────────┐
│  STAGE 3: PII Masking + Prompt Construction                    │
│  ─ มาส์ก PII ใน evidence bundle ทุก field                      │
│  ─ system prompt: persona + rules + organizational data        │
│  ─ user message: MASKED evidence + MASKED user query           │
│  ─ NO preliminary verdict ใน prompt (ห้ามใส่ "ผลเบื้องต้น=X")  │
│  ─ Claude ไม่เคยเห็น raw PII (compliance ดู Section 2.8)      │
└────────────────────────────────┬───────────────────────────────┘
                                 │
                                 ▼
┌────────────────────────────────────────────────────────────────┐
│  STAGE 4: LLM Inference (จุดตัดสินเดียว)                       │
│  ─ Claude เป็นผู้ตัดสิน verdict เอง จากหลักฐานที่เห็น          │
│  ─ Response เป็น structured JSON                               │
└────────────────────────────────┬───────────────────────────────┘
                                 │
                                 ▼
┌────────────────────────────────────────────────────────────────┐
│  STAGE 5: Response Parsing & Validation                        │
│  ─ parse JSON                                                  │
│  ─ validate schema                                             │
│  ─ ห้าม "override" verdict ของ LLM ที่ layer นี้                │
└────────────────────────────────┬───────────────────────────────┘
                                 │
                                 ▼
┌────────────────────────────────────────────────────────────────┐
│  STAGE 6: Persistence                                          │
│  ─ บันทึก masked message ทั้ง user/bot + input_hash            │
│  ─ บันทึก masked evidence + verdict ลง check_requests/results  │
│  ─ ห้าม persist raw PII (ดู Section 2.8)                       │
└────────────────────────────────────────────────────────────────┘
```

### 5.2 กฎ Anti-Bias (สำคัญที่สุดของ mode นี้)

**ห้ามใส่สิ่งต่อไปนี้ใน prompt ที่ส่งให้ Claude:**
- ❌ `preliminary_status = suspicious`
- ❌ `ผลเบื้องต้น = caution`
- ❌ `ระบบประเมินว่า = scam`
- ❌ คำตัดสินใดๆ ที่เกิดก่อน LLM เห็นข้อมูล

**ใส่ได้เฉพาะหลักฐานดิบ (และต้องมาส์ก PII ก่อน):**
- ✅ `เลขบัญชี xxx-x-xx5678 ถูกรายงานในฐานตำรวจ 47 ครั้ง (ข้อมูลปี 2026)`
- ✅ `พบคำว่า "เร่งโอน", "ห้ามบอกใคร" ในข้อความ`
- ✅ `เคสคล้ายในฐานข้อมูล: หมวด "หลอกโอน", similarity 0.87`
- ✅ `ผู้ใช้คุยมาแล้ว 3 turn เคยส่งเบอร์ xxx-xxx-1234 ที่ blacklist hit มาก่อน`

**สังเกต:** ตัวอย่างด้านบนทุก PII ถูกมาส์กแล้ว (`xxx-x-xx5678` ไม่ใช่เลขบัญชีเต็ม) — บังคับใช้ `pii_masker.mask_pii(text, "strict")` ก่อนสร้าง prompt ทุกครั้ง

**Pattern name ที่ตีความแล้ว = verdict ซ่อน (บทเรียน 2026-08-29):**
ระบบเคยส่ง `Pattern ที่พบ: เร่งให้โอนเงิน` ให้ Claude ทั้งที่ข้อความมีแค่คำว่า "ด่วน" (keyword เดียวใน DB โยงกับชื่อ pattern นั้น) — ผลคือ "ส่งงานด่วนนะ" ถูกตัดสิน caution นี่คือ anchoring แบบเดียวกับ `preliminary_status` แค่ย้ายไปซ่อนในชื่อ pattern

กฎ: หลักฐานจาก pattern ต้องรายงาน **คำที่พบจริง แยกตามมิติ** (ดู 6.8 Scam Lexicon) และต้องรายงาน **มิติที่ไม่พบ** ด้วย เพื่อให้ LLM เห็นว่าไม่มีการขอเงิน/ข้อมูล/ลิงก์:
```
คำสัญญาณที่พบ (ข้อเท็จจริง ไม่ใช่คำตัดสิน — ข้อความปกติก็มีคำพวกนี้ได้):
- เร่งให้รีบตัดสินใจ: "ด่วน"
ไม่พบ: ขอให้โอน/จ่ายเงิน, ขอข้อมูลส่วนตัว/รหัส, ให้กดลิงก์/ติดตั้งแอป, ...
```
System prompt บอก Claude ชัดว่าให้ตัดสินจาก **การขอ** (เงิน / ข้อมูล / กดลิงก์ / ย้ายช่องทาง) ไม่ใช่จากการมีคำเร่งด่วน และ verdict `safe` ไม่ต้องมีหลักฐานยืนยัน — แค่ไม่มีสัญญาณการหลอกก็ safe ได้

**RAG context ห้ามมี status ของเคสเก่า:** ส่งได้แค่ข้อความ + หมวด + แหล่ง/วันที่ + similarity — `result_status`/`matched_pattern` ของเคสใน chroma คือ verdict จาก schema เดิม ห้ามหลุดเข้า prompt

**RAG gate (2026-08-29):** ข้อความ text ที่ lexicon พบแค่มิติ `urgency`/`authority_claim` หรือไม่พบเลย (และไม่มีภาพ/เบอร์/บัญชี/URL) **ไม่ดึง RAG** (`qa_engine.should_use_rag`) — วัดด้วย `ml/rag_eval.py` (14 คำถาม): embedding จับผิวคำ ทำให้ "ส่งงานด่วน" ได้ SMS ปลอม SCB มาประกอบ = anchoring ข้อความปกติ; RAG มีไว้ให้ Claude เทียบ "โครงเรื่อง" เมื่อมีสัญญาณ "การขอ" แล้วเท่านั้น

**RAG stack (2026-08-29):** embedding `BAAI/bge-m3` (แทน MiniLM: hit@3 เท่ากัน 8/11 แต่คะแนน relevant/irrelevant แยกได้ 0.70 vs 0.64 ขณะที่ MiniLM 0.64 vs 0.62 = แยกไม่ได้), threshold 0.60, corpus = tier A + tier N ที่ไม่ใช่ digest/ข่าวต่างประเทศ (830 เคส) — ตั้งใน `Settings.RAG_EMBED_MODEL` / `RAG_SIMILARITY_THRESHOLD`; chroma เก็บชื่อ model ใน metadata → mismatch = raise ไม่ใช่ใช้ต่อเงียบๆ; miss ที่เหลือเป็นแบบ "ไม่มีเคสเกิน threshold → Claude ตัดสินเอง" ไม่ใช่ดึงผิดเรื่อง

**Fail fast:** ถ้า Claude ตอบไม่ใช่ JSON หรือ verdict นอก `danger/caution/safe` → raise `QAAnalysisError` → route คืน HTTP 502 ให้ UI แสดง retry — **ห้าม** default เป็น `safe` (scam จริงแต่ parse พัง → บอก user ว่าปลอดภัย = ทิศทางที่อันตรายที่สุด)

LLM อ่านหลักฐาน → ตัดสิน verdict เอง

### 5.3 Hard Constraints ใน System Prompt

แทนที่จะ override LLM ใน code (ซึ่งผิด principle 2.3 single decision point) → ใส่กฎใน system prompt ให้ LLM ปฏิบัติเอง:

```
กฎตัดสิน:
- ถ้า blacklist hit ≥ 10 ครั้ง verdict ต้องไม่ต่ำกว่า "caution"
- ถ้า blacklist hit ≥ 30 ครั้ง verdict ต้องเป็น "danger"
- ถ้า user ระบุชัดว่ายังไม่ได้โอนเงิน → action priority "ด่วน" คือ "อย่าโอน"
- ถ้า user ระบุว่าโอนไปแล้ว → action priority "ด่วน" คือ "แจ้งธนาคารและ 1441"
```

วิธีนี้ยังคง single decision point (LLM) แต่ใส่ business rule ไว้ใน prompt ไม่ใช่ใน orchestration code

### 5.4 Chat History Handling

- โหลด last 10 messages เป็น context
- ไม่ pad ด้วย system message เพิ่ม
- ผ่าน Claude คำสั่ง "พิจารณา context สะสม"
- **ไม่มี severity floor ใน code** — เดิม orchestration เคยเขียนทับ verdict ของ Claude ถ้าต่ำกว่า turn ก่อน (ผิด 2.3 และทำให้ผู้ใช้แก้ความเข้าใจผิดไม่ได้ เช่น "อ๋อ อันนี้เพื่อนผมเอง" → ยัง caution) ตอนนี้ verdict สูงสุดของ turn ก่อนถูกส่งเป็น **evidence text** (`history_evidence.to_evidence_text()`) ให้ Claude ตัดสินเองว่าจะคง/ลด/เพิ่ม

---

## 6. Shared Infrastructure

โมดูลเหล่านี้ใช้ร่วมกัน 2 mode แต่ **ไม่มี decision logic**:

### 6.1 Preprocessing (`app/utils/preprocessing.py`)
- `normalize_phone_number(s) -> str`
- `normalize_bank_account(s) -> str`
- `normalize_url(s) -> str`
- `prepare_text_for_analysis(s) -> str`

Pure functions, no I/O, no state

### 6.2 Input Detection (`app/utils/input_processor.py`)
- `detect_input_type(s) -> Literal["phone", "bank_account", "url", "text", ...]`
- `extract_entities_from_text(s) -> list[Entity]`

### 6.3 Blacklist API Client (`app/services/blacklist_service.py`)
- `check_blacklist(value, value_type) -> BlacklistResult`
- คืน **raw data** เท่านั้น (found, count, raw_response) ไม่ตีความ
- handle retry, timeout, rate limit

### 6.4 OCR Service (`app/services/ocr_service.py`)

**Interface:**
```python
def extract_text_from_image(image_bytes: bytes) -> OcrResult:
    """
    OcrResult: { text, avg_confidence, char_count, engine_used }
    """
```

**Engine Strategy (สำคัญ — ต่าง mode ใช้ต่างวิธี):**

| เงื่อนไข | ML Mode | Q&A Mode |
|---|---|---|
| **Default** | EasyOCR | EasyOCR |
| **Low confidence** (`< 0.5`) | ❌ ไม่ fallback Claude → ตั้ง `suggest_qa=True` | ✅ Fallback Claude Vision |
| **Text ว่าง / < 10 chars** | ❌ ไม่ fallback Claude → ตั้ง `suggest_qa=True` | ✅ Fallback Claude Vision |
| **Rate limit Claude Vision** | N/A | 50 calls/วัน (per env), log ทุกครั้งที่ fallback |

**ทำไม ML mode ห้าม fallback Claude:**
- ทำลายสัญญา "ML mode = cheap, fast, deterministic"
- ML mode ไม่ควรพึ่ง external API ที่อาจล่ม / quota หมด
- ผู้ใช้ตัดสินใจเองว่าจะใช้ Claude (ผ่าน Q&A mode) หรือไม่ — เป็น informed choice

**Implementation note:**
- OCR service expose `extract_text_from_image(image, allow_llm_fallback: bool)` — caller ระบุนโยบาย ไม่ใช่ service เดา
- ML engine เรียกด้วย `allow_llm_fallback=False` เสมอ
- Q&A engine เรียกด้วย `allow_llm_fallback=True` เสมอ
- หลักการ: **service ไม่รู้ว่ามาจาก mode ไหน** — แต่ caller บอกข้อจำกัด

### 6.5 Database Repository (`app/database/repository.py`)
- CRUD ต่อ table — ไม่มี business logic
- 2 mode ใช้ table ชุดเดียวกัน (request, result, blacklist_check, chat_session, chat_message)
- **Schema เพิ่ม field `mode` ใน `check_requests`** — `Column(String(10), nullable=False)` ค่า `"ml"` หรือ `"qa"` เพื่อ query แยกตาม mode ได้

**Tables ใหม่ที่ต้องเพิ่ม (สำหรับ PDPA — ดู Section 2.8):**
- `user_consents` — consent record (consent_version, accepted_at, ip_hash, withdrawn_at)
- `pii_access_log` — audit log ทุกครั้งที่เข้าถึง raw PII

**Migration plan:**
- ใช้ Alembic สำหรับ schema migration
- migration แรกหลัง Phase 0: เพิ่ม `mode` column, สร้าง 2 table ข้างต้น, เพิ่ม `input_hash` column ใน `check_requests`

### 6.6 Response Templates (`app/services/template_service.py`)
- โหลด template ตาม class/category
- ทำ string interpolation
- ใช้ทั้ง 2 mode

### 6.7 PII Masker (`app/services/pii_masker.py`)

**บังคับใช้สำหรับทุก data flow ที่ออกจาก in-memory request scope** (ดู Section 2.8)

**Interface:**
```python
@dataclass
class MaskedResult:
    masked: str          # ข้อความที่มาส์ก PII แล้ว
    pii_hash: str        # SHA256(original + salt) สำหรับ dedup
    pii_found: list[PIIMatch]  # ตำแหน่ง+ประเภท PII ที่เจอ (สำหรับ audit)

def mask_pii(text: str, mode: Literal["strict", "display"] = "strict") -> MaskedResult:
    """มาส์ก PII ในข้อความ — ใช้ก่อนส่ง Claude / log DB / แสดง UI
    
    strict: เลขบัญชีเหลือ 4 ตัวท้าย, ชื่อเหลือตัวแรก (สำหรับ external API + log)
    display: user-friendly (081-xxx-5678 ผู้ใช้รู้ว่าเป็นเบอร์ไหน)
    """

def mask_field(value: str, field_type: PIIType, mode: Literal["strict", "display"]) -> str:
    """มาส์กค่าเดี่ยว (เลขบัตร, บัญชี, เบอร์, ชื่อ, URL)"""

def hash_value(value: str) -> str:
    """SHA256(value + PII_SALT) — pure hash, ไม่มาส์ก"""

def find_pii_in_text(text: str) -> list[PIIMatch]:
    """detect PII patterns ใน free text"""
```

**Mask modes (เหลือ 2 แทน 3):**
- `strict` — มาส์กแน่น (ใช้ก่อนส่ง Claude, log DB) — เลขบัญชีเหลือ 4 ตัวท้าย, ชื่อเหลือตัวแรก, เลขบัตรเหลือตัวแรก+ตัวท้าย
- `display` — มาส์กแบบ user-friendly (UI) — `081-xxx-5678` ให้ผู้ใช้รู้ว่าหมายถึงเบอร์ไหน

**ทำไมยุบจาก 3 เหลือ 2:** เดิม `external` กับ `log` เหมือนกันต่างกันแค่ "เก็บ hash คู่" — แต่ hash เป็น field แยกใน `MaskedResult` อยู่แล้ว ไม่ต้องเป็น mode แยก

**Acceptance criteria:**
- ผ่าน unit test ครอบคลุม edge cases: PII ฝังในประโยค, PII หลายตัวในข้อความเดียว, false positive (เลข 13 หลักที่ไม่ใช่บัตรประชาชน)
- มี checksum validation สำหรับเลขบัตรประชาชน (Mod 11) ก่อนมาส์ก เพื่อลด false positive

**ใช้ที่ไหนบ้าง (mandatory):**
- ก่อนสร้าง prompt ส่ง Claude (Q&A Stage 3)
- ก่อน persist ลง DB (ทั้ง ML Stage 6, Q&A Stage 6)
- ก่อนส่ง response กลับ user (ML Stage 5, Q&A Stage 5)
- ก่อน log ทุกระดับ (utils/logger.py inject masking ใน formatter)

### 6.8 Scam Lexicon (`data/lexicon/scam_lexicon.yaml` + `app/services/pattern_service.py`)

**คืออะไร:** พจนานุกรม "คำสัญญาณ" แบ่งตาม **มิติทางจิตวิทยา/โครงสร้าง** ที่มิจฉาชีพใช้ (อ้างอิง Stajano & Wilson 2011 "seven principles"; Cialdini) — ไม่ใช่กฎตัดสิน

| มิติ (`key`) | label | ตัวอย่างคำ |
|---|---|---|
| `urgency` | เร่งให้รีบตัดสินใจ | ด่วน, ทันที, หมดเขต, regex `ภายใน N ชม.` |
| `money_request` | ขอให้โอน/จ่ายเงิน | โอน, ค่าธรรมเนียม, มัดจำ, regex เลขบัญชี/จำนวนเงิน |
| `credential_request` | ขอข้อมูลส่วนตัว/รหัส | OTP, รหัสผ่าน, ยืนยันตัวตน, กรอกข้อมูล |
| `link_action` | ให้กดลิงก์/ติดตั้งแอป | คลิก, ลิงก์, ติดตั้งแอป, regex URL/shortener/suspicious TLD |
| `authority_claim` | อ้างหน่วยงาน/แบรนด์ | ธนาคาร, ตำรวจ, DSI, สรรพากร, กสิกร, Shopee |
| `threat` | ขู่/สร้างความกลัว | คดี, อายัด, ระงับ, ถูกแฮก, ค้างชำระ |
| `reward` | ล่อด้วยรางวัล/เงินคืน | รางวัล, ผู้โชคดี, เงินคืน, ฟรี |
| `financial_offer` | เสนอเงินกู้/ลงทุน/รายได้ | สินเชื่อ, ไม่ต้องค้ำ, ผลตอบแทน, regex `N% ต่อเดือน` |
| `secrecy` | ให้ปิดเป็นความลับ | ห้ามบอกใคร, ห้ามวางสาย |
| `channel_shift` | ให้ย้ายไปคุยช่องทางอื่น | แอดไลน์, เพิ่มเพื่อน, regex LINE ID |
| `relationship_lure` | สร้างความสนิท/ทักผิด | ที่รัก, ทักผิด, อยากรู้จัก |
| `borrowing_pretext` | อ้างเป็นคนรู้จัก ขอยืมเงิน | ยืมเงิน, เปลี่ยนเบอร์, ฉุกเฉิน |
| `amount_mention` (อ่อน) | พบจำนวนเงิน — ยังไม่รู้ว่าแจ้งหรือขอ | regex `N บาท` — แยกจาก money_request เพราะค่าจ้าง/ราคาก็มีตัวเลข (kaggle_tu รอบ 2) |
| `refuse_verification` | ปฏิเสธการตรวจสอบ/นัดรับ | ไม่รับนัด, ไม่รับวิดีโอคอล, ส่งอย่างเดียว |
| `inbound_payment_offer` (อ่อน) | ผู้ส่งเสนอจะโอน "ให้" ผู้รับ (ขอเลขบัญชีผู้รับ) | regex `ขอเลขบช… จะโอน` — ทิศทางเงินกลับด้าน ผู้รับไม่เสียอะไร (guideline v1.1 Q3); gate ไม่ดึง RAG ถ้ามีแค่นี้ |

**Lexicon v1.1 (2026-08-29) = 15 มิติ** — regex ใน money_request เพิ่ม `third_party_account` / `account_name_mismatch` (บัญชีม้า = สัญญาณโดยลำพัง, Q2), evidence ของ link_action บอกเมื่อ "พูดถึงลิงก์แต่ไม่พบ URL" (Q5), หมดสิทธิ์/ของหมด ย้ายจาก threat → urgency (Q7) — ทุกข้อมาจาก ANNOTATION_GUIDELINE v1.1 ที่ผู้ทำ thesis ตัดสิน 7 คำถาม แล้ว prompt/lexicon ตามหลัง (ไม่ใช่กลับกัน)

**Caveat ต่อมิติ** (field `caveat` ใน YAML → พิมพ์กำกับใน evidence): `money_request` ไม่บอกทิศทางเงิน (ผู้ซื้อขอพร้อมเพย์ผู้ขาย = ผู้รับไม่เสียอะไร), `channel_shift` inbox/DM บนแพลตฟอร์มเดิมอ่อนกว่า LINE ID ภายนอก — บทเรียนจาก external comparison กับ Kaggle TU dataset (2026-08-29): lexicon ที่ "ไม่พบ" กลายเป็น anchoring ไปทาง safe ได้เท่าๆ กับที่ "พบ" anchoring ไปทาง danger → evidence text ปิดท้ายเสมอว่า "รายการนี้มาจากคำใน lexicon เท่านั้น"

**กฎของไฟล์:**
- ทุกคำมี `evidence` ระบุที่มา (`corpus_tierA(n)`, `afnc`, `police9`, `tidlor`, `thaicert`, `domain`) — defend ได้ว่าไม่ได้นั่งเทียน; คำที่เป็น `domain` ต้อง verify กับ tier A เมื่อ corpus โต
- **ห้ามมี** `verdict` / `weight` / `severity` / `score` ในไฟล์ (มี test บังคับ) — ถ้ามี = กลายเป็น decision rule
- การพบคำใน **มิติเดียว** ไม่ใช่หลักฐานว่า scam — "ด่วน" อยู่ใน flash sale / อาจารย์ทวงงาน / แม่ขอเงินค่าเทอม ได้ทั้งนั้น ผู้ตัดสินดูว่าหลาย มิติ co-occur หรือไม่ (โดยเฉพาะมี "การขอ" หรือไม่)

**Matching (`pattern_service.scan_text`):**
- ตัดคำด้วย PyThaiNLP newmm ทั้ง text และ term แล้ว match เป็น token subsequence → "ด่วน" ไม่ match "รถด่วน", "ถูกมาก" ไม่ match "ถูกมากกว่า" (ระบบเดิมใช้ substring `in` → false positive)
- regex รายงานแค่ **ชื่อ** (`bank_account_format`) ไม่รายงานข้อความที่ match → PII ไม่หลุดออกจาก service
- คืน `DimensionMatch` ทุกมิติ (รวมที่ไม่พบ) — `format_evidence()` สร้างข้อความหลักฐานสำหรับ prompt

**ใครใช้:**
- Q&A: `app/evidence/pattern_evidence.py` → `to_evidence_text()` เข้า prompt (Stage 2-3)
- ML: `ml/features.py` **ควร** นับคำต่อมิติจากไฟล์นี้แทน word list ที่ hardcode อยู่ — ยังไม่ทำ เพราะเปลี่ยน feature schema = bump model major version ต้องรอ retrain กับ Data v2
- Annotation: มิติทั้ง 12 ใช้เป็นโครงของ `data/ANNOTATION_GUIDELINE.md` (Section 10.4)

**Legacy:** table `scam_patterns` ใน DB ไม่ถูกใช้แล้ว (`find_matching_patterns(db, text)` ยังอยู่เป็น compat wrapper สำหรับ Streamlit path เก่า) — ลบ table ได้ใน migration ถัดไป

---

## 7. โครงสร้างไฟล์ที่เสนอ

```
scam-detection-chatbot/
├── CLAUDE.md                          ← เอกสารฉบับนี้
├── README.md
├── requirements.txt
├── .env.example
│
├── data/
│   ├── raw/                           ← labeled dataset
│   │   ├── scam_messages.csv
│   │   └── safe_messages.csv
│   ├── processed/                     ← train-ready
│   │   ├── train.parquet
│   │   ├── val.parquet
│   │   └── test.parquet
│   ├── templates/                     ← response templates
│   │   ├── ml_responses.yaml
│   │   └── advice_by_category.yaml
│   └── chroma_db/                     ← สำหรับ Q&A RAG
│
├── ml/                                ← ML training (แยกจาก serving)
│   ├── preprocess.py
│   ├── features.py                    ← feature extractors
│   ├── train.py                       ← train script
│   ├── evaluate.py                    ← test set eval
│   ├── inference.py                   ← load + predict (used by app)
│   └── notebooks/
│       └── eda.ipynb
│
├── models/                            ← model artifacts
│   └── v1/
│       ├── model.pkl
│       ├── vectorizer.pkl
│       ├── metadata.json
│       └── metrics.json
│
├── app/
│   ├── main.py                        ← FastAPI entrypoint
│   ├── config/
│   │   └── settings.py
│   │
│   ├── api/
│   │   ├── ml_routes.py               ← POST /api/ml/detect
│   │   ├── qa_routes.py               ← POST /api/qa/chat, /sessions
│   │   ├── shared_routes.py           ← /transcribe, /health
│   │   └── user_routes.py             ← /api/user/consent, /api/user/forget
│   │
│   ├── engines/                       ← mode engines
│   │   ├── ml_engine.py               ← ML pipeline orchestrator
│   │   └── qa_engine.py               ← Q&A pipeline orchestrator
│   │
│   ├── features/                      ← feature extractors (สำหรับ ML)
│   │   ├── text_features.py           ← TF-IDF / embedding
│   │   ├── blacklist_features.py      ← hit count, severity
│   │   ├── pattern_features.py        ← regex flags
│   │   ├── url_features.py            ← URL parsing
│   │   └── combiner.py                ← รวมเป็น vector
│   │
│   ├── evidence/                      ← evidence collectors (สำหรับ Q&A)
│   │   ├── blacklist_evidence.py
│   │   ├── pattern_evidence.py
│   │   ├── rag_evidence.py
│   │   └── history_evidence.py
│   │
│   ├── llm/                           ← LLM client + prompt
│   │   ├── claude_client.py
│   │   ├── prompts.py                 ← system prompt + templates
│   │   └── parser.py                  ← parse JSON response
│   │
│   ├── services/                      ← shared services
│   │   ├── blacklist_service.py
│   │   ├── ocr_service.py             ← EasyOCR + optional Claude Vision fallback
│   │   ├── template_service.py
│   │   ├── pii_masker.py              ← PDPA compliance (mandatory)
│   │   ├── prefill_cache.py           ← ML→Q&A handoff token store (Redis/memory)
│   │   └── transcription_service.py
│   │
│   ├── utils/
│   │   ├── preprocessing.py
│   │   ├── input_processor.py
│   │   ├── validators.py
│   │   └── logger.py
│   │
│   ├── database/
│   │   ├── connection.py
│   │   ├── models.py
│   │   └── repository.py
│   │
│   ├── schemas/                       ← Pydantic models
│   │   ├── ml_schema.py
│   │   ├── qa_schema.py
│   │   └── shared_schema.py
│   │
│   └── ui/
│       ├── streamlit_app.py           ← entry, mode selector
│       ├── ml_view.py                 ← ML mode UI
│       ├── qa_view.py                 ← Q&A mode UI
│       └── components.py
│
└── tests/
    ├── ml/
    │   ├── test_features.py
    │   ├── test_inference.py
    │   └── test_engine.py
    ├── qa/
    │   ├── test_evidence.py
    │   ├── test_prompt.py
    │   └── test_engine.py
    └── shared/
        ├── test_preprocessing.py
        ├── test_blacklist.py
        ├── test_pii_masker.py          ← PDPA compliance tests
        └── test_ocr_strategy.py        ← ML no-fallback / Q&A fallback rules
```

**หลักการจัด structure:**
- `ml/` = training (offline), `app/` = serving (online) — ไม่ปนกัน
- `engines/` ไม่ใช่ `services/` — ชัดเจนว่าเป็น orchestrator ของ mode
- `features/` (ML) แยกจาก `evidence/` (Q&A) — สื่อความตั้งใจคนละแบบ
- `llm/` แยกออกมา — ถ้าวันหลังเปลี่ยน provider ไม่กระทบ engine

---

## 8. Anti-Patterns ที่ห้ามทำเด็ดขาด

| ❌ ห้ามทำ | ✅ ทำแบบนี้แทน | เหตุผล |
|---|---|---|
| Pattern match → set status → ส่ง status ให้ LLM | Pattern match → เก็บเป็น match list → ส่ง list ให้ LLM | LLM bias / anchoring (feedback อาจารย์ครั้งที่แล้ว) |
| Blacklist hit = ตัดสิน scam ทันทีจบ flow | Blacklist hit = feature ใน vector → model ตัดสิน | Cascade ไม่ใช่ fusion |
| `if ai_verdict_severity > preliminary` ค่อย override | LLM/model เป็นผู้ตัดสินเดียว ไม่มี override | Multiple decision points |
| ใส่ business rule ใน orchestration code | ใส่ใน prompt (Q&A) หรือ training label (ML) | Single decision point |
| Mode 1 import จาก Mode 2 หรือกลับกัน | ผ่าน shared service เท่านั้น | Mode isolation |
| Hardcode pattern ใน Python code | เก็บใน DB หรือ YAML | Open/closed |
| `try: ... except: pass` แล้วใช้ default status | Fail fast, log error, คืน explicit error response | Hidden failures |
| Train + inference อยู่ไฟล์เดียวกัน | แยก `ml/train.py` กับ `ml/inference.py` | Reproducibility |
| ใช้ Claude เป็น OCR ใน shared service | ใช้ EasyOCR/Tesseract ใน shared, Claude อยู่ใน Q&A เท่านั้น | Cost + mode isolation |
| Streamlit เรียก service ตรง | Streamlit → HTTP → FastAPI → service | Layer separation |
| ส่ง raw PII (เลขบัตร/บัญชี/ชื่อเต็ม) เข้า Claude prompt | มาส์กผ่าน `pii_masker.mask_pii(text, "strict")` ก่อนเสมอ | PDPA / Section 2.8 |
| Persist raw PII ลง DB / log file | เก็บ masked + input_hash เท่านั้น | PDPA / data leak prevention |
| ML mode fallback ไป Claude Vision ตอน OCR ล้มเหลว | ตั้ง `suggest_qa=True` ให้ผู้ใช้เลือกเอง | Cost discipline / mode promise |
| โอน evidence bundle ข้าม mode (ML → Q&A) | โอนแค่ raw input ผ่าน prefill_token, Q&A collect evidence ใหม่ | Mode isolation / fresh evidence |
| Hardcode masking pattern ในหลายไฟล์ | ใช้ `pii_masker.py` ที่เดียวเท่านั้น | DRY / auditability |
| keyword เดียว → ชื่อ pattern ที่ตีความแล้ว ("ด่วน" → "เร่งให้โอนเงิน") ส่งให้ LLM | รายงานคำที่พบจริงแยกตามมิติ + มิติที่ไม่พบ (6.8) | ชื่อ pattern ที่ตีความ = verdict ซ่อน → anchoring |
| ส่ง `result_status` ของเคส RAG เข้า prompt | ส่งแค่ข้อความ + หมวด + similarity | status เก่า = preliminary verdict |
| severity floor / override verdict ของ LLM ด้วย history ใน code | ส่ง verdict turn ก่อนเป็น evidence text ให้ LLM ตัดสินเอง | Single decision point (2.3) |
| LLM ตอบพัง → default `safe` เงียบๆ | raise `QAAnalysisError` → HTTP 502 + retry | scam จริงแต่ parse พัง → บอก safe = อันตรายที่สุด |
| match keyword แบบ substring (`kw in text`) | ตัดคำ (newmm) แล้ว match token subsequence | "รถด่วน" ≠ "ด่วน" |
| system prompt ห้าม LLM "ใช้ความรู้ตัวเอง" ครอบถึงการตัดสิน | จำกัดเฉพาะข้อเท็จจริง (เบอร์/เว็บ/สถิติ); การตัดสินใช้วิจารณญาณเต็มที่ | ถ้าห้ามคิด LLM จะพึ่ง pattern ที่ป้อน = anchoring |

---

## 9. Roadmap & Phases

### Phase 0: Foundation + Cleanup (ก่อนเริ่มสิ่งใหม่)

**ลำดับสำคัญมาก:**

1. [ ] Backup โค้ดปัจจุบันเป็น branch `legacy-llm-only`
2. [ ] **เขียน `pii_masker.py` + tests ก่อนทุกอย่าง** (component อื่นต้องพึ่ง)
3. [ ] เพิ่ม `PII_SALT`, `ML_CONFIDENCE_THRESHOLD`, `MODEL_VERSION` ใน `.env.example` และ `settings.py`
4. [ ] Setup Alembic + เขียน migration แรก: เพิ่ม `mode` column, `input_hash` column, สร้าง `user_consents` + `pii_access_log` tables
5. [ ] เขียน consent endpoint + Privacy Notice page ใน Streamlit
6. [ ] เขียน audit log decorator + apply กับ `blacklist_service.check_blacklist()`
7. [ ] เขียน cron job stub สำหรับ data retention (ยังไม่ต้องรัน แค่ scaffold)
8. [ ] ลบ logic "preliminary status" ออกจาก main flow
9. [ ] แยก endpoint ปัจจุบัน → `/api/qa/chat` (ยังใช้ LLM แบบเดิมไปก่อน — known temporary debt, จะ refactor ใน Phase 3)
10. [ ] เก็บ chroma DB ไว้ (ใช้ใน Q&A mode)

### Phase 1: ML Foundation
- [ ] เตรียม dataset (ดูข้อ 10)
- [ ] เขียน `ml/preprocess.py`, `ml/features.py`
- [ ] Train baseline (TF-IDF + LogReg)
- [ ] Evaluate บน test set → ได้ metric baseline
- [ ] เขียน `ml/inference.py` + load model

### Phase 2: ML Serving
- [ ] เขียน `app/engines/ml_engine.py`
- [ ] เขียน `POST /api/ml/detect`
- [ ] เขียน Streamlit ML view
- [ ] integration test end-to-end

### Phase 3: Q&A Refactor
- [ ] เขียน `app/evidence/*` (เปลี่ยนจาก preliminary_status เป็น raw evidence)
- [ ] อัพเดท system prompt → ใส่ hard constraints
- [ ] เขียน `app/engines/qa_engine.py` (ไม่มี preliminary_status)
- [ ] integrate `pii_masker` ที่ Stage 3 (ก่อนส่ง Claude)
- [ ] เพิ่ม Claude Vision fallback ใน OCR service (Q&A only)
- [ ] เขียน `prefill_cache` service สำหรับรับ handoff token จาก ML
- [ ] เขียน `POST /api/qa/chat?prefill={token}`

### Phase 4: ML Improvement
- [ ] Train WangchanBERTa
- [ ] Train XGBoost (สำหรับเปรียบเทียบ)
- [ ] Hyperparameter tuning
- [ ] เพิ่ม SHAP explanation

### Phase 5: UI Integration
- [ ] Mode selector หน้าแรก
- [ ] ML view: input → result card + feature importance
- [ ] Q&A view: chat interface
- [ ] ปุ่ม "ส่งเคสนี้ไปอีก mode" (ใช้ prefill_token)
- [ ] แสดง PII ใน masked form ทุกที่ในหน้าจอ (display mode)
- [ ] ปุ่ม 👁 reveal/hide PII ต่อชิ้น (local UI state เท่านั้น) — ดู Section 2.8 UI Reveal Rule

### Phase 6: Thesis Writing
- [ ] Architecture chapter (อ้าง CLAUDE.md นี้)
- [ ] ML methodology
- [ ] Q&A methodology
- [ ] Comparison table (ML vs LLM: accuracy, latency, cost, explainability)
- [ ] User study (optional)

---

## 10. Training Data Strategy (v2)

> **v2 (2026-08-29) แทนที่ v1 ทั้งหมด** — v1 ให้ความสำคัญกับ "จำนวน" แต่ audit เมื่อ 2026-08-29 พบว่า
> (a) corpus 1,672 records มี Thai scam verbatim ที่ตรวจสอบที่มาได้แค่ 80 (4.8%)
> (b) RAG 1,088 เคสมาจาก LLM generate โดยใส่ชื่อสำนักข่าวเป็น attribution — ตามกลับไปหาต้นทางไม่ได้ (fabricated provenance)
> (c) Week 4 พิสูจน์ว่า label noise คือคอขวดหลัก ไม่ใช่ model
> v2 จึงเปลี่ยนหลักเป็น **"ทุก record ต้อง defend ได้"** — ยอมให้ corpus เล็กลง

### 10.1 หลักการ

1. **Provenance ก่อนปริมาณ** — record ที่ไม่มีที่มาที่ตรวจสอบได้ ห้ามอยู่ใน test set และห้ามถูก cite ใน Q&A mode
2. **Tier แยกชัด, report แยกชัด** — metric หลักของ thesis คือผลบน tier A เท่านั้น
3. **Test set ล็อคครั้งเดียว** — สร้างจาก tier A ตั้งแต่วันแรก, commit hash, ห้าม re-stratify (บทเรียน Week 4)
4. **Label ต้องมี protocol** — annotation guideline เป็นเอกสาร, IAA วัดจริง
5. **ข้อมูลที่ LLM สร้าง = synthetic เสมอ** ไม่ว่า prompt จะบอกให้ "ดึงจากข่าว" หรือไม่ — LLM ไม่มีความสามารถดึงข้อมูลจริง attribution ที่มันใส่มาถือเป็น fabricated จนกว่าจะมีคน verify URL

### 10.2 Tier System

ทุก record ใน corpus ต้องมี field `tier` ค่าใดค่าหนึ่ง:

| Tier | ชื่อ | นิยาม | ใช้ train | ใช้ val | ใช้ test | cite ใน Q&A RAG |
|---|---|---|---|---|---|---|
| **A** | `real_thai` | ข้อความ scam ภาษาไทยจริง — มี source URL ที่เปิดดูแล้วเจอข้อความนั้น หรือมาจาก collection form ที่มี consent | ✅ | ✅ | ✅ **เท่านั้น** | ✅ |
| **S** | `safe_real` | ข้อความไทยปกติจริง: SMS ธนาคาร/OTP/โปรโมชั่นถูกกฎหมาย (จาก form) + Wisesight (CC0) | ✅ | ✅ | ✅ | ✅ (เฉพาะที่มี URL) |
| **B** | `real_foreign` | scam จริงภาษาอื่นที่แปลเป็นไทย (IMC25 EN → TH) | ✅ | ✅ | ❌ | ❌ |
| **C** | `synthetic` | LLM generate (Typhoon, Claude ฯลฯ) — รวมชุด xlsx เดิมที่ใช้ทำ RAG | ✅ เฉพาะที่ผ่าน human review | ❌ | ❌ | ❌ |
| **N** | `narrative` | เคสเล่าเรื่องจากข่าว/หน่วยงาน (ไม่ใช่ข้อความ scam โดยตรง) มี URL | ❌ | ❌ | ❌ | ✅ (RAG เท่านั้น) |

**กฎ:**
- Tier B/C ห้ามอยู่ใน test set เด็ดขาด — ถ้ามีคนถาม "test บนข้อมูลจริงหรือเปล่า" คำตอบต้องเป็น "ใช่ 100%"
- Tier C ต้องมี `review.status = "approved"` + `review.reviewer` ก่อนเข้า train — record ที่ `pending_review` ถือว่ายังไม่มีอยู่
- Tier N ใช้กับ RAG เท่านั้น ห้าม train ML (ข่าวเล่าเรื่อง ≠ ข้อความ scam — model จะเรียน "ข้อความพูดถึง scam" แทน)
- รายงานผลใน thesis: ตาราง metric ต้องมีคอลัมน์ "tier A only" เป็นคอลัมน์หลัก และ "all tiers" เป็นคอลัมน์รอง

### 10.3 Provenance Schema (บังคับทุก record)

```json
{
  "id": "sha1(text)",
  "text": "...",
  "tier": "A",
  "verdict": "danger",
  "category": "phishing_link",
  "source": {
    "name": "Anti Fake News Center Thailand",
    "url": "https://www.antifakenewscenter.com/...",
    "retrieved_at": "2026-09-01T10:00:00+07:00",
    "license": "fair_use_academic | CC0 | CC-BY-4.0 | consent_form",
    "extraction_method": "verbatim_html | verbatim_ocr | consent_form | translated | llm_generated",
    "snapshot_hash": "sha256 ของ HTML/screenshot ต้นทาง ณ เวลาที่เก็บ"
  },
  "annotation": {
    "labels": [{"annotator": "A1", "verdict": "danger", "category": "phishing_link", "confidence": 4}],
    "final": {"verdict": "danger", "category": "phishing_link", "resolved_by": "agreement | adjudicator"},
    "guideline_version": "1.0"
  },
  "pii": {"masked": true, "masker_version": "..."}
}
```

- `snapshot_hash` มีไว้พิสูจน์ว่าไม่ได้แก้ข้อความหลังเก็บ — เก็บ snapshot จริงไว้ที่ `data/raw/snapshots/{hash}.html` (gitignore, เก็บ local + backup)
- record ที่มาจาก collection form: `url` = null, `license` = `consent_form`, ต้องมี `consent_id` อ้างถึง record ใน form
- `text` ต้องผ่าน `pii_masker.mask_pii(text, "strict")` ก่อนเข้า corpus **เสมอ** — corpus ต้องไม่มีเบอร์/บัญชี/ชื่อจริง (ใช้ placeholder `<PHONE>`, `<BANK_ACCOUNT>`, `<URL>` แบบเดียวกับ IMC25)

### 10.4 Annotation Protocol

- เอกสาร `data/ANNOTATION_GUIDELINE.md` (versioned) — นิยาม verdict + ทุก category พร้อมตัวอย่างบวก/ลบ และ edge case ที่เจอจริง เช่น:
  - ข้อความจากธนาคารจริงที่เตือนเรื่อง scam → `safe`
  - โปรโมชั่นเกินจริงแต่ไม่หลอกเอาเงิน/ข้อมูล → `caution`
  - ข้อความที่ scam อยู่ที่ลิงก์อย่างเดียว ตัวข้อความกลางๆ → `danger` + `phishing_link`
- Tier A และ S ทุก record: label โดย **2 คน** อิสระ, ไม่ตรงกัน → คนที่ 3 ตัดสิน
- รายงาน Cohen's κ (verdict) และ κ (category) ใน thesis — target ≥ 0.7; ถ้าต่ำกว่า → revise guideline แล้ว re-annotate (บันทึก guideline_version)
- Tier B/C: label เดียวจาก source/generator ถือเป็น weak label — ใช้ได้เฉพาะ train
- ห้าม LLM เป็น annotator สำหรับ tier A/S (ทำได้แค่ pre-label เพื่อช่วยคนทำงานเร็วขึ้น และต้องบันทึกว่า pre-label มาจาก LLM)

### 10.5 Split & Test Lock

- Test set: สุ่มจาก tier A ∪ S เท่านั้น, stratified by `verdict × category`, ขนาด 30% ของ tier A (เพราะ tier A เล็ก ต้องให้ test มีทุก category) — สัดส่วนเปลี่ยนจาก v1 (15%) โดยตั้งใจ
- ไฟล์ `data/processed/TEST_LOCK.json` (version, hash, ids) สร้างด้วย `python -m ml.preprocess --lock-test` แล้ว commit — รันครั้งต่อไป test = ids ที่ lock เสมอ
- **เวลา lock:** lock เมื่อ tier A ถึงเป้าใน 10.6 หรือก่อน train v2 ครั้งแรก (แล้วแต่อะไรถึงก่อน) — ไม่ lock ตอนนี้ (2026-08-29) เพราะ tier A = 80 จะได้ test scam แค่ 24 ข้อความถาวร; ระหว่างรอ ห้าม tune อะไรกับ split ที่ยังไม่ lock
- **เพิ่ม data ทีหลัง → เข้า train/val เท่านั้น** test ไม่โต ไม่ re-stratify ทุก model version เทียบกันได้บน test ชุดเดียว
- ถ้าจำเป็นต้องเปลี่ยน test (เช่น พบ label ผิด) → ทำครั้งเดียว, ประกาศเป็น `test_v2`, และรายงานทุก model ใหม่บน test_v2 ทั้งหมด
- val: 15% ของ tier A ∪ S ที่เหลือ + tier B (ห้าม tier C ใน val — val ใช้ tune threshold ต้องสะท้อนของจริง)

### 10.6 Collection Channels (tier A / S)

เรียงตาม yield ที่คาดหวัง:

| ช่องทาง | ได้อะไร | tier | ข้อควรระวัง |
|---|---|---|---|
| **Collection form** (Google Form): ผู้ร่วมส่ง SMS/LINE ที่เคยได้รับ (scam + ปกติ) | ข้อความเต็ม ของจริง ทั้ง 2 class | A, S | ต้องมี consent notice (PDPA ม.19), mask PII ทันทีที่ import, เก็บ consent_id |
| **Anti Fake News Center** (antifakenewscenter.com) | บทความ quote SMS + เคสเล่าเรื่อง | A, N | `ml/scrape/wp_news.py` ผ่าน WP REST API (robots อนุญาต) เก็บ URL + snapshot ทุกโพสต์ — ทำแล้ว 1,156 (2022-2026); **แก้ไข 2026-09-01: รูปในบทความเป็นแบนเนอร์ "ข่าวปลอม" ทั่วไป ไม่ใช่ screenshot SMS (ตรวจ 1,156 snapshot: 1 รูป/บทความ, ชื่อไฟล์ Web-N.webp ทั้งหมด) → OCR ไม่ได้ tier A จากแหล่งนี้** — ได้เฉพาะข้อความที่บทความ quote (ต้องคนคัด) |
| **ThaiCERT** (thaicert.or.th) | บทความเตือนภัยรายสัปดาห์ | A, N | เดียวกัน — ทำแล้ว 363 (กรองข่าว vuln/malware ออก) |
| **Facebook ตำรวจไซเบอร์ / บช.สอท.** | screenshot SMS | A | ผ่าน `ocr_service` ของเราเอง (`verbatim_ocr`), เก็บ screenshot เป็น snapshot, ต้องมีคน verify OCR |
| **IMC25 Thai subset** | SMS ไทยจริง 65 | A | ใช้อยู่แล้ว |
| **สำนักข่าว** (ไทยรัฐ, ข่าวสด, มติชน ฯลฯ) | เคสเล่าเรื่องเป็นหลัก | N | เช็ค robots.txt รายเว็บ, ส่วนใหญ่ไม่ quote ข้อความเต็ม |
| **Wisesight** | safe text (social media) | S | มีอยู่แล้ว 500 — ลดสัดส่วนเมื่อได้ SMS ปกติจริงจาก form |

**เป้าที่สมจริง (ภายใน 2026-10-31):** tier A ≥ 300, tier S ≥ 300 (อย่างน้อยครึ่งเป็น SMS จริง ไม่ใช่ Wisesight) — 300 record ที่ defend ได้ทุกตัวมีค่ากว่า 1,672 ที่ defend ได้ 80

### 10.7 Legacy Data (v1) Handling

| ชุดข้อมูล v1 | จัดเป็น | การกระทำ |
|---|---|---|
| 80 Thai verbatim (police9, tidlor, AFNC, IMC25-TH) | tier A | re-verify URL ยังเปิดได้ + เพิ่ม snapshot_hash → เก็บ |
| 500 Wisesight | tier S | เก็บ |
| 584 IMC25 translated | tier B | เก็บ (train only) |
| 508 Typhoon synthetic (`pending_review`) | tier C | quarantine จนกว่ามีคน review — ถ้าไม่มีเวลา review ก็ไม่ใช้ |
| 1,088 เคส xlsx (RAG เดิม, LLM generate + fabricated attribution) | tier C | **ถอดออกจาก chroma** เก็บไฟล์เป็น archive `data/archive/v1_rag_llm_generated.xlsx` + เขียนใน thesis เป็น lesson learned |
| `scam_corpus.before_relabel`, `relabel_proposals` | archive | ย้ายไป `data/archive/` |
| model v0.4.0 / v0.5.0 | archive | เก็บเป็น "data v1 exploratory results" — ไม่เทียบตรงกับ v2 (test set คนละชุด) |

### 10.8 Data Card

`data/DATACARD.md` ตาม Datasheets for Datasets (Gebru et al. 2021): Motivation, Composition (per-tier stats + สร้างอัตโนมัติจาก `validate_corpus`), Collection process, Preprocessing (PII masking), Uses (ML train / RAG แยก), Distribution (license ต่อ source), Maintenance — ใช้เป็น appendix ของ thesis โดยตรง

### 10.9 Class Imbalance (คงจาก v1)

- sklearn: `class_weight='balanced'`; BERT: weighted CE
- Threshold tune บน val (tier A/S/B) — false negative แย่กว่า false positive
- SMOTE/undersampling ทำเฉพาะ train, **ห้ามแตะ test**

---

## 11. Tech Stack

### Backend
- Python 3.13
- FastAPI (API)
- SQLAlchemy + PostgreSQL (DB)
- Alembic (DB migration)
- Pydantic (validation)
- APScheduler หรือ cron (data retention jobs)

### ML
- scikit-learn (baseline + classical models)
- transformers + PyTorch (WangchanBERTa)
- XGBoost
- SHAP (explainability)
- PyThaiNLP (Thai NLP utilities)

### Q&A
- anthropic SDK (Claude)
- chromadb (RAG)
- sentence-transformers (embeddings)

### Shared
- EasyOCR (image text extraction — default)
- Pillow + OpenCV (image preprocessing สำหรับ OCR)
- requests (blacklist API)
- redis (prefill_token cache + rate limit) — fallback: in-memory dict + TTL
- (Optional) Whisper หรือ Google Speech-to-Text สำหรับ audio transcription

### UI
- Streamlit

### Dev
- pytest (testing)
- ruff (linting)
- mypy (type check)

---

## 12. คำตอบสำหรับคำถามที่อาจารย์น่าจะถาม

**Q: ทำไมแยก 2 mode? ทำอันเดียวไม่ดีกว่าหรือ?**  
A: เพราะ 2 use case ต่างกันชัดเจน (ตรวจเร็ว vs ปรึกษา) และ ML กับ LLM มี trade-off คนละแบบ (latency, cost, explainability) การมี 2 mode ให้ผู้ใช้เลือก = real-world UX ที่ดีกว่า และยังให้เปรียบเทียบ approach ในเล่ม thesis ได้

**Q: ทำไมยังต้องใช้ blacklist API ในเมื่อมี ML?**  
A: Blacklist API คือ ground truth จากตำรวจ (high precision, low recall) ML model ใช้เป็น feature ตัวหนึ่ง ไม่ใช่ทดแทน — มัน complementary

**Q: ทำไมไม่ใช้ ML อย่างเดียวสำหรับทุก mode?**  
A: ML ตอบ "ทำไม" หรือ "ทำต่อยังไง" เชิงสนทนาไม่ได้ ผู้ใช้บางคนต้องการการพูดคุย ไม่ใช่แค่ label

**Q: ตัดสินแบบ ML เชื่อได้แค่ไหน?**  
A: เราโชว์ metric บน held-out test set + confusion matrix + feature importance ต่อทุก prediction ผู้ใช้ตัดสินใจเชื่อ/ไม่เชื่อได้

**Q: ถ้า ML ทำนายผิดล่ะ?**  
A: เราโชว์ confidence score ถ้า < threshold (เช่น 0.7) จะแสดง "unclear, แนะนำใช้ Q&A mode" + เก็บ misclassification เข้า retrain pipeline

**Q: ทำไม Q&A ไม่ใส่ preliminary verdict ใน prompt?**  
A: เพราะทำให้ LLM bias (anchoring) แทนที่จะวิเคราะห์ context อย่างจริงจัง (อาจารย์เคย feedback มาแล้ว) — เราส่ง raw evidence ให้ LLM สังเคราะห์เอง

**Q: 2 mode share database table เดียวกัน — confusing ไหม?**  
A: ไม่ — schema มี field `mode VARCHAR(10) NOT NULL` ใน table `check_requests` (ค่า `"ml"` หรือ `"qa"`) ระบุชัดเจน query แยกได้ และ analytics ดูได้ว่าผู้ใช้ใช้ mode ไหนมากกว่า รายละเอียด schema migration ดู Section 6.5

**Q: ผู้ใช้ส่งเลขบัตรประชาชน/บัญชี — ระบบจัดการ PDPA ยังไง?**  
A: ดู Section 2.8 และ 6.7 — ทุก PII ถูกมาส์กก่อนออกจาก request scope (ส่ง Claude / log DB / แสดง UI) ค่าดิบใช้ได้เฉพาะใน-memory และเฉพาะกับ blacklist API ซึ่งต้อง exact match ตามมาตรา 24 ของ PDPA (legitimate interest) เก็บ SHA256 hash ใน DB สำหรับ dedup โดยไม่ต้องเก็บค่าจริง

**Q: ทำไม ML mode ไม่ใช้ Claude Vision เป็น OCR fallback?**  
A: ดู Section 6.4 — เพราะจะทำลายสัญญา "ML mode = cheap, fast, no external dependency" และทำให้ผู้ใช้จ่ายค่า Claude API โดยไม่รู้ตัว แทนที่จะ fallback เงียบๆ เราตั้ง `suggest_qa=True` ให้ UI แนะนำผู้ใช้ตัดสินใจเองว่าจะใช้ Q&A mode (ที่มี LLM) ต่อหรือไม่

**Q: ทำไมไม่โอน evidence จาก ML ไป Q&A เพื่อประหยัด API call?**  
A: ดู Section 4.7 — การโอน evidence จะ break Mode Isolation (principle 2.4) และทำให้ 2 mode ผูกกันแบบ implicit เปลี่ยน ML feature ทีหลังจะพัง Q&A เราเลือกโอนแค่ raw input ผ่าน prefill_token, Q&A collect evidence ใหม่หมด เสีย latency ~500ms ซึ่งยอมรับได้ใน budget ของ Q&A mode

**Q: ทำไมยุบ vocabulary ของ verdict ให้เหมือนกัน 2 mode?**  
A: เดิม ML ใช้ `scam/safe/uncertain` (class label) แต่ Q&A ใช้ `danger/caution/safe` (severity) — ผู้ใช้สนใจ "ระวังแค่ไหน" มากกว่า "เป็น class ไหน" → unify เป็น severity เหมือนกัน, ML เพิ่ม `uncertain` สำหรับ low-confidence (จะ trigger suggest_qa)

**Q: Audio input เข้า ML mode ได้ไหม?**  
A: ได้ — audio ไม่ใช่ input type แยก เป็นแค่ช่องทาง (modality) ที่ระบบ transcribe เป็น text แล้วเข้า pipeline ปกติ ทั้ง 2 mode รองรับ ใช้ shared `transcription_service`

**Q: ถ้า user ขอลบข้อมูลตัวเอง (PDPA มาตรา 33) ระบบทำยังไง?**  
A: มี endpoint `/api/user/forget` — ลบ chat_session, check_requests, results, masked logs ทั้งหมดที่ผูกกับ user/session นั้น เก็บไว้แค่ audit log (ตามกฎหมายต้องเก็บ 1 ปี) แต่ไม่มี PII ใน audit log อยู่แล้ว เก็บแค่ input_hash

**Q: ถ้า WangchanBERTa inference ช้าเกินไป (เกิน 1 วินาที) ทำยังไง?**  
A: ตัวเลือก: (1) downgrade เป็น TF-IDF+LR เป็น default, BERT เป็น fallback สำหรับเคสซับซ้อน (2) deploy บน GPU/TPU instance (3) distill model เล็กลง — ทั้งหมดเป็น engineering decision หลัง benchmark, ระบุใน thesis chapter "Deployment Considerations"

---

## 13. แนวทางการทำงานร่วมกับ AI Assistant

เมื่อ user ขอให้ implement feature:
1. **อ่าน CLAUDE.md นี้ก่อน** เช็คว่า feature ที่จะทำตรงกับ phase ไหน
2. **ห้ามฝ่าฝืน design principles (ข้อ 2)** ถ้าจำเป็นต้องฝ่าฝืน → อัพเดท CLAUDE.md ก่อน
3. **ห้ามทำ anti-patterns (ข้อ 8)**
4. **แต่ละ change ต้องอยู่ใน layer ของตัวเอง** ตาม structure ข้อ 7
5. **เพิ่ม test** ในไฟล์ที่ตรงกับ layer ที่แก้

เมื่อ user ถามว่า "design ตรงนี้ทำไมต้องเป็นแบบนี้":
- อ้าง section ที่เกี่ยวข้องของ CLAUDE.md
- ถ้าไม่มีคำตอบ → propose ให้อัพเดท CLAUDE.md

---

## 14. Changelog

| Date | Change | Reason |
|---|---|---|
| 2026-05-16 | Initial CLAUDE.md | กำหนด architecture หลัง prof feedback เรื่อง premature decision |
| 2026-05-16 | + Section 2.8 (PII/PDPA) | User feedback: เพิ่ม data privacy considerations |
| 2026-05-16 | + Section 4.7 (ML→QA handoff) | User feedback: UX seamless ระหว่าง 2 mode |
| 2026-05-16 | + Section 6.4 OCR strategy (Q&A fallback) | User feedback: EasyOCR อ่านสลิปไม่แม่น |
| 2026-05-16 | + Audio input, evaluation methodology, class imbalance, consent/retention/audit | Self-audit รอบ 2 |
| 2026-05-16 | Unify verdict vocabulary (`danger/caution/safe`) ทั้ง 2 mode | Inconsistency fix |
| 2026-05-16 | Add `mode` column ใน schema, Alembic setup | Schema-FAQ inconsistency fix |
| 2026-09-10 | **Web deploy: Hugging Face Space (Docker, free CPU) + Neon Postgres** — `deploy/` (Dockerfile อบ bge-m3+EasyOCR ลง image, requirements pin ตามเครื่อง dev, start.sh = alembic upgrade → uvicorn :7860, README front-matter), `scripts/deploy_hf.py` (ประกอบ staging เฉพาะ runtime ไฟล์ — **ไม่รวม corpus/thesis/ml/ เพราะ Space เป็น public repo** — สร้าง Space + mirror upload + ตั้ง secrets จาก .env + restart); `Settings.database_url()` รับ `DATABASE_URL` override (Neon ต้องมี sslmode=require); secrets บังคับ: CLAUDE_API_KEY, DATABASE_URL, PII_SALT, APP_ACCESS_CODE | ผู้ทำ thesis ขอ deploy ขึ้นเว็บจริง; เลือก HF free tier เพราะ bge-m3 ต้องการ RAM ~4GB (Render free 512MB ไม่พอ) และ user เป็นนักศึกษา (งบ 0) |
| 2026-09-10 | **Deployment scope: Q&A (RAG+LLM) เท่านั้น** — ML mode ปิดด้วย `ENABLE_ML_MODE=false` (default): `main.py` include ml_router เฉพาะเมื่อเปิด, UI ซ่อน mode tabs ตาม `/api/config`; **โค้ด ML ไม่ลบ** (เก็บเป็น baseline + เปิดกลับเมื่อ tier A ≥ 300 → retrain v2) + closed-pilot gate: `APP_ACCESS_CODE` (header `X-Access-Code`, ตรวจใน middleware I/O layer), `rate_limiter.py` sliding window ต่อ IP เฉพาะ `POST /api/qa/chat` (6/นาที, 200/วัน), `scripts/run_pilot.ps1` (uvicorn + cloudflared quick tunnel) | ผู้ทำ thesis ตัดสิน: ML v0.4.x train บน data v1 ที่ archive แล้ว ผลไม่ดีตามหวัง (คอขวดคือ data ไม่ใช่ model — Week 4) → pilot deploy เฉพาะส่วนที่ defend ได้; gate/rate-limit เป็น access control ไม่ใช่ decision logic (ไม่ขัด 2.3) |
| 2026-08-29 | Section 10 → Training Data Strategy v2 (tier system, provenance schema, annotation protocol, test lock, legacy handling) | Data audit: verifiable Thai verbatim แค่ 80/1672; RAG 1,088 เคสมี fabricated attribution จาก LLM; Week 4 ชี้ label noise เป็นคอขวด |
| 2026-08-29 | + 6.8 Scam Lexicon (12 มิติ, YAML + provenance), 5.2 กฎ pattern evidence/RAG/fail-fast, 5.4 ลบ severity floor, anti-pattern 6 แถว | Logic review: "ด่วน" คำเดียว → pattern "เร่งให้โอนเงิน" → Claude anchor เป็น caution; พบ override/fallback ซ่อนใน qa_engine |
| 2026-08-29 | Data v2 implemented: schema v2 (`ml/scrape/schema.py`), `migrate_v2.py` (1,672 → tier A80/S500/B584/C508), `wp_news.py` (AFNC+ThaiCERT → tier N 1,519), `preprocess.py` tier rules + test lock, `setup_rag.py` จาก tier A+N (1,599 เคสมี URL), `ANNOTATION_GUIDELINE.md` v1.0, `DATACARD.md`; 10.5 ระบุเวลา lock | ทำตาม Section 10 v2; RAG เดิม (LLM-generated) ถอดแล้ว → `data/archive/` |
| 2026-08-29 | RAG: bge-m3 + threshold 0.6 + ตัด digest/ข่าวต่างประเทศ (830 เคส) + lexicon gate `should_use_rag`; `ml/rag_eval.py` | MiniLM แยก relevant/irrelevant ไม่ได้ (0.64 vs 0.62); ข้อความปกติดึง scam มาประกอบ |
| 2026-08-29 | External comparison กับ Kaggle TU dataset (tier C, 341 template): `ml/kaggle_tu_compare.py` + LLM adjudication 2 รอบ (49 disagreement) → lexicon 12→14 มิติ (+`amount_mention`, `refuse_verification`, caveat ทิศทางเงิน, คำบริบทนักศึกษา), prompt +ceiling/advance-fee/narrative rules; agreement กับ rule-label 82.8% → 88.6%, บน 49 เคส ตรง guideline 16 → 31; `data/ANNOTATION_GUIDELINE_v1.1_proposal.md` (14 เคสรอคนตัดสิน) | บทเรียน: lexicon ที่ "ไม่พบ" = anchoring ไปทาง safe; regex จำนวนเงินเปิด RAG ให้ค่าจ้างปกติ; RAG category ถูกยกเป็นข้อเท็จจริง — ทุกข้อแก้ที่ lexicon/prompt ไม่ใช่ code override |
| 2026-08-29 | **ANNOTATION_GUIDELINE v1.1** (ผู้ทำ thesis ตัดสิน 7 คำถาม → drafter + reviewer 3 มุม): ขั้น 0 narrative, opener รายการปิด 4 แบบ, สัญญาณโดยลำพัง/แบบประกอบ, **`needs_info`** ("ข้อมูลไม่พอ" = caution + รหัสจากรายการปิด 6 ค่า → Q&A ใช้ `follow_up` ถามต่อ), calibration 39 แถว + blind sheet `data/annotation/v1.1_calibration_blind.csv`, quick card; v1.0 → `data/archive/`. Prompt เพิ่ม `needs_info`/`category` ใน JSON, กฎบัญชีม้า/ทิศทางเงิน/ลิงก์ไม่มี URL; lexicon v1.1 = 15 มิติ; RAG gate ข้าม inbound_payment_offer. Live check 10 เคส calibration = 10/10 | คำตอบของผู้ทำ thesis คือ ground truth ของ guideline; LLM judge/skeptic ใช้ชี้จุดที่ต้องตัดสินเท่านั้น (A2 ยังต้องตอบ blind sheet เพื่อวัด κ) |
| 2026-08-30 | **IAA รอบแรก**: A2 ตอบ packet 7+12 ข้อ → κ (ต่อ template, n=7) = 0.77 substantial (ต่อ record n=14: 0.63), ไม่ตรง 1 (Q5 ลิงก์ไม่มี URL: A1 caution+url / A2 danger); ชุดที่ 2 ตรง guideline 11/12 (#8 opener ไม่มีช่องทาง A2 ให้ danger) — `data/processed/iaa_round1_report.md`, `ml/annotation/agreement.py` | n เล็ก = pilot; รอบถัดไปใช้ blind sheet 40 แถว + tier A จริง; A2 เสนอ `seller_reputation` เป็น needs_info ค่าใหม่ (รอ v1.3) |
| 2026-08-30 | **Guideline v1.2**: A3 adjudicator ตัดสิน Q5 = danger → กฎ (f) "กรอกข้อมูลผ่านลิงก์เพื่อรับสิทธิ์" นับแม้ไม่เห็น URL; `needs_info: url` จำกัดเฉพาะลิงก์ที่ไม่ผูกกับการขอ; C38 → danger + C38b คู่เทียบ; prompt ตาม; live check Q5 danger / ลิงก์รายละเอียด caution+url | ผู้ทำ thesis เลือก (ก) ให้ guideline ตาม majority adjudication ตาม protocol §5 ข้อ 6 — ตัวอย่างจริงว่า IAA เปลี่ยน guideline |
| 2026-08-30 | **Guideline v1.3**: needs_info +`seller_reputation` (เครดิต/รีวิว/คนในกลุ่มยืนยัน) จากข้อเสนอ A2; marketplace standard set 3 ค่า; prompt/follow_up ตาม | ผู้ทำ thesis รับข้อเสนอ — annotator คนที่ 2 มีส่วนกำหนด guideline |
| 2026-08-30 | **IAA รอบ 2 (blind sheet 40 แถว)**: A1 vs A2 **κ = 0.24** (fair, 19/40); A1 vs guideline 0.38, A2 vs guideline 0.26 — pilot รอบ 1 (0.77, n=7) ประเมินสูงเกินจริง; พบ (1) A2 อ่านโจทย์เป็น "เสียอะไรถ้า*ไม่*ทำตาม" (C01/C03/C07) (2) A1 ผู้เขียนเองไม่ทำตามกฎ opener→caution, ย้ายช่องทางเดี่ยว→caution, metadata→safe และให้ C38 = safe ทั้งที่ A3 ตัดสิน danger — `data/processed/iaa_round2_report.md` | ตาม protocol §5 ข้อ 6: κ < 0.7 → ประชุม calibration + แก้ guideline (v1.4) แล้ว blind ซ้ำ **ก่อน** annotate tier A; ห้ามแก้ prompt ให้ตามคนใดคนหนึ่ง |
| 2026-08-31 | **ANNOTATION_GUIDELINE v2.0** (ออกแบบใหม่ ผู้ทำ thesis เห็นด้วย): verdict = สถานะการกระทำ (safe ทำได้ / caution เช็ค X ก่อน / danger อย่าทำ); decision tree 3 คำถาม; สัญญาณ danger รายการปิด 9 ข้อ (จาก blind รอบ 2: #6 ข้อเสนอเกินจริงไม่ต้องมีช่องทาง, #8 ปฏิเสธตรวจสอบ+โอนเต็ม, #9 shortener+ข้อเสนอ); caution ต้องมี needs_info; แกน `watch_for` แทน opener→caution; ตัด metadata/opener/DM-เดี่ยว rules ที่ผู้เขียนเองไม่ใช้; calibration 39 แถว; v1.3 → archive. Prompt ตาม (+`watch_for` field, category เฉพาะ danger); `ml/guideline_eval.py` = regression ระบบ vs calibration: **38/39, needs_info 10/10** (จาก 31/39 ก่อนปรับ) | IAA รอบ 2 κ 0.24 ชี้ว่า v1.x ถามคำถามผิดชนิด ("เป็น scam ไหม" แทน "ควรทำอะไร"); ทุกกฎใหม่มีที่มาจากคำตอบ blind ของ A1/A2 ไม่ใช่ reviewer LLM |
| 2026-08-31 | **IAA รอบ 3 (v2.0, 39 แถว)**: A1 vs guideline **κ 0.71** (จาก 0.38 — design ตรงกับผู้เขียน) แต่ A1 vs A2 **κ 0.27**: A2 ให้ danger 28/38 รวม OTP ที่ระบบส่ง/แจ้งยอด SCB ทั้งที่ self-test ระบุตรงๆ → ปัญหา annotator ไม่ใช่ guideline; ทั้งคู่ให้ danger กับ marketplace โอนก่อน (C24/26/27) และ "ขอเลขบัญชีจะโอนให้" (C21/22) ที่ v2.0 ให้ caution/safe → 2 คำตัดสินรอผู้ทำ thesis; A1 test-retest รอบ 2→3 ไม่นิ่งบนแถว marketplace — `data/processed/iaa_round3_report.md` | κ ที่รายงานได้จริงต้องรอ A2 ที่อ่าน guideline จริง (training) หรือเปลี่ยนคน; ห้าม annotate tier A จนกว่า κ ≥ 0.6 |
| 2026-08-31 | **Guideline v2.1**: ผู้ทำ thesis ปิด 2 คำตัดสิน — marketplace โอนก่อน = caution (คง); **คนไม่รู้จักขอเลขบัญชี/พร้อมเพย์เรา "จะโอนให้" = danger สัญญาณ #10** (บัญชีม้าโดยไม่รู้ตัว: โอนเข้าแล้วอ้าง "โอนเกิน ช่วยโอนคืน" = ฟอกเงินผ่านบัญชีเรา — กลับคำตัดสิน Q3 เดิม); prompt/lexicon note ตาม; blind sheet รอบ 4 regenerate | A1 กับ A2 ตอบ danger ตรงกันใน blind รอบ 3 แม้ guideline ให้ safe — ผู้ทำ thesis ให้เหตุผลเชิงกลไก (mule) จึงเปลี่ยนกฎ |
| 2026-08-31 | **IAA รอบ 4 (quiz artifact `data/annotation/annotation_quiz.html`, v2.1, 39 แถว)**: A1 vs guideline **κ 0.88**; A2 test-retest 0.88 (สม่ำเสมอ, ผ่าน self-test) แต่ A1 vs A2 ยัง **0.27** — A2 มีเกณฑ์ต่างอย่างเป็นระบบ (คนไม่รู้จัก+เงิน = danger ทุกกรณี, caution = "โทรเช็ค" แม้ phishing ชัด); ทั้งคู่ตรงกันแต่ต่าง guideline: C03 (caution vs safe), C24 (danger vs caution) → candidate v2.2; `data/processed/iaa_round4_report.md` | ต่อไป: A3 ทำ quiz ชุดเดียวกันเป็น majority บน 17 แถวที่ต่าง — κ ที่รายงานใช้คู่ที่ ≥ 0.6; อธิบาย A2 เป็น strict annotator ใน limitations ถ้า A3 ไปทาง A1 |
| 2026-08-31 | **A3 ทำ quiz → 3 annotator**: A1/A3 **κ 0.61** (คู่แรก ≥ 0.6), A1/A2 0.27, A2/A3 0.30, mean pairwise 0.39; A3 ไปทาง A1 11/17; majority (2/3) มี 37/39 แถว ตรง guideline 31/37 → **guideline v2.2** ตาม majority 6 แถว: #8 ขยาย "โอนเต็ม/โอนก่อนเท่านั้น" = danger (มัดจำ/รีบโอนก่อน = caution), #11 ใหม่ "อ้างคนรู้จักจากเบอร์ใหม่ + ขอเงิน" = danger, "จอง" ของถูก = caution, "ทักไลน์อย่างเดียว" = caution; A1 ถูก overrule 4 แถว; prompt ตาม; quiz artifact v2.2 | protocol §7 ข้อ 4 (คนที่ 3 ตัดสิน); κ ที่รายงานใน thesis = A1/A3 บน 39 แถว v2.1 (0.61) + จะวัด v2.2 ซ้ำก่อน tier A |
| 2026-08-31 | **ANNOTATION_GUIDELINE v2.0** (ออกแบบใหม่ ผู้ทำ thesis เห็นด้วย): verdict = สถานะการกระทำ (safe ทำได้ / caution เช็ค X ก่อน / danger อย่าทำ); decision tree 3 คำถาม; สัญญาณ danger รายการปิด 9 ข้อ (จาก blind รอบ 2: #6 ข้อเสนอเกินจริงไม่ต้องมีช่องทาง, #8 ปฏิเสธตรวจสอบ+โอนเต็ม, #9 shortener+ข้อเสนอ); caution ต้องมี needs_info; แกน `watch_for` แทน opener→caution; ตัด metadata/opener/DM-เดี่ยว rules ที่ผู้เขียนเองไม่ใช้; calibration 39 แถว; v1.3 → archive. Prompt ตาม (+`watch_for` field, category เฉพาะ danger); `ml/guideline_eval.py` = regression ระบบ vs calibration: **38/39, needs_info 10/10** (จาก 31/39 ก่อนปรับ) | IAA รอบ 2 κ 0.24 ชี้ว่า v1.x ถามคำถามผิดชนิด ("เป็น scam ไหม" แทน "ควรทำอะไร"); ทุกกฎใหม่มีที่มาจากคำตอบ blind ของ A1/A2 ไม่ใช่ reviewer LLM |
| 2026-08-29 | RAG: bge-m3 + threshold 0.6 + ตัด digest/ข่าวต่างประเทศ (830 เคส) + lexicon gate `should_use_rag`; `ml/rag_eval.py` | MiniLM แยก relevant/irrelevant ไม่ได้ (0.64 vs 0.62); ข้อความปกติดึง scam มาประกอบ |
| 2026-08-29 | External comparison กับ Kaggle TU dataset (tier C, 341 template): `ml/kaggle_tu_compare.py` + LLM adjudication 2 รอบ (49 disagreement) → lexicon 12→14 มิติ (+`amount_mention`, `refuse_verification`, caveat ทิศทางเงิน, คำบริบทนักศึกษา), prompt +ceiling/advance-fee/narrative rules; agreement กับ rule-label 82.8% → 88.6%, บน 49 เคส ตรง guideline 16 → 31; `data/ANNOTATION_GUIDELINE_v1.1_proposal.md` (14 เคสรอคนตัดสิน) | บทเรียน: lexicon ที่ "ไม่พบ" = anchoring ไปทาง safe; regex จำนวนเงินเปิด RAG ให้ค่าจ้างปกติ; RAG category ถูกยกเป็นข้อเท็จจริง — ทุกข้อแก้ที่ lexicon/prompt ไม่ใช่ code override |
| 2026-08-29 | **ANNOTATION_GUIDELINE v1.1** (ผู้ทำ thesis ตัดสิน 7 คำถาม → drafter + reviewer 3 มุม): ขั้น 0 narrative, opener รายการปิด 4 แบบ, สัญญาณโดยลำพัง/แบบประกอบ, **`needs_info`** ("ข้อมูลไม่พอ" = caution + รหัสจากรายการปิด 6 ค่า → Q&A ใช้ `follow_up` ถามต่อ), calibration 39 แถว + blind sheet `data/annotation/v1.1_calibration_blind.csv`, quick card; v1.0 → `data/archive/`. Prompt เพิ่ม `needs_info`/`category` ใน JSON, กฎบัญชีม้า/ทิศทางเงิน/ลิงก์ไม่มี URL; lexicon v1.1 = 15 มิติ; RAG gate ข้าม inbound_payment_offer. Live check 10 เคส calibration = 10/10 | คำตอบของผู้ทำ thesis คือ ground truth ของ guideline; LLM judge/skeptic ใช้ชี้จุดที่ต้องตัดสินเท่านั้น (A2 ยังต้องตอบ blind sheet เพื่อวัด κ) |
