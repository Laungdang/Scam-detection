# Week 4 — Error Analysis + Label Cleanup Experiment

เอกสารบันทึก findings สำหรับ thesis chapter "Limitations & Discussion"

---

## 1. Error Analysis (model v0.4.0-xgb-multi)

### Overall
- Test set: 251 records, errors: **25 (10.0% error rate)**
- Manual_entry sources error rate: **12.0%**
- Verbatim_html sources error rate: **6.5%** ← real Thai data ทำได้ดีกว่า

### Top error patterns

| Pattern | Count | Insight |
|---|---|---|
| `other → phishing_link` | 6 | "other" records ที่จริงเป็น phishing แต่ถูก label ผิดใน IMC25 |
| `investment_scam → financial_fraud` | 3 | Semantic overlap (ทั้งคู่เกี่ยวกับเงิน) |
| `other → safe` | 3 | "other" รวม noise (โปรโมชั่น, fragment) |
| `romance_scam → safe` | 2 | "Wrong number" opener สั้นเหมือนทักทายปกติ |
| `phishing_link → romance_scam` | 2 | Placeholder confusion (`<NAMED_ENTITY>`, `<URL>`) |

### Key finding: "other" = 44% ของ errors
- 11 จาก 25 errors มี true label = "other"
- ตัวอย่างที่ model ทำนาย **ถูกแล้ว** แต่ label เป็น "other":
  - "บัญชีของคุณถูกล็อค คลิก: `<URL>`" → model: phishing_link ✓ (correct prediction, wrong gold)
  - "เคล็ดลับการลดน้ำหนัก..." → model: safe ✓ (correct — ไม่ใช่ scam จริง)

→ ปัญหาคือ **label quality** ไม่ใช่ model quality

---

## 2. Label Cleanup Experiment (ที่ rollback)

### Approach
1. **Rule-based classification** (deterministic) — เช่น มี "DSI/สรรพากร" → impersonation_authority
2. **LLM verification** (Typhoon) สำหรับ records ที่ rules ไม่ตัดสิน
3. Output proposals → audit trail → apply

### Cleanup actions applied
- **relabel:** 200 records ("other" → specific category)
- **remove:** 4 records (noise/fragments)
- **keep_safe:** 16 records (ไม่ใช่ scam จริง — ย้ายไป safe)
- **keep_other:** 36 records (legit misc)

### Distribution change
| Category | Before | After | Δ |
|---|---|---|---|
| phishing_link | 224 | 329 | +105 |
| financial_fraud | 114 | 137 | +23 |
| prize_scam | 82 | 104 | +22 |
| impersonation_authority | 103 | 116 | +13 |
| loan_offer | 86 | 98 | +12 |
| **other** | 240 | **36** | **−204** |

### Result: Mixed (rollback)

| Metric | v0.4.0 baseline | v0.5.0 cleaned | Δ |
|---|---|---|---|
| Accuracy | 0.861 | **0.873** | ↑ +1.2% |
| **Macro-F1** | **0.837** | 0.793 | ↓ −4.4% |
| Weighted-F1 | **0.894** | 0.866 | ↓ −2.8% |
| McNemar p-value | — | 0.68 | not significant |

### ทำไม cleanup ไม่ช่วย

1. **"other" หลังจาก clean เหลือ 5 records ใน test** → model เรียนรู้ไม่ได้ → F1 = 0.0
2. **Automated relabel มี noise** — บาง rules / LLM verdict ผิด
3. **Test set re-stratification** ทำให้สัดส่วน class เปลี่ยน → comparison ลำบาก

### Decision: Rollback to v0.4.0

- McNemar ไม่ significant → ไม่มี evidence ว่า v0.5.0 ดีกว่า
- Production keep v0.4.0
- Artifacts ของ v0.5.0 ยังเก็บไว้ใน `models/v0.5.0-xgb-multi-clean/`
- Backup corpus: `data/raw/scam_corpus.before_relabel.jsonl`
- Relabel audit: `data/raw/sources/relabel_proposals.jsonl`

---

## 3. Thesis chapter "Limitations" — Key points

### Limitation 1: Noisy "other" category in source data

> IMC 2025 Smishing Dataset uses "others" as a catch-all for scam types not in 7 primary categories. In our 240 "other" records, manual + LLM review revealed: ~83% should be reclassified (mostly phishing_link), ~7% are non-scam (promotional/fragments), ~17% are legitimate misc.

### Limitation 2: Automated cleanup did not improve performance

> We attempted rule-based + LLM-assisted (Typhoon v2.5) cleanup of "other" records. Despite improving accuracy (+1.2%), macro-F1 dropped (−4.4%) due to:
> (a) automated relabel introducing its own errors,
> (b) the cleaned "other" class becoming too sparse for the model to learn.
> McNemar test (p=0.68) shows no significant improvement.

### Limitation 3: Cleanup needs full human review

> Automated cleanup at scale (240 records) is insufficient for label quality improvement. Future work should explore (1) full manual relabeling by domain experts, (2) hierarchical taxonomy with "unknown_scam" as default for misc, or (3) ensemble voting across multiple LLM annotators.

### Limitation 4: Source bias affects error distribution

> Manual_entry sources (translated + synthetic, n=158 in test) show 12.0% error rate vs 6.5% for verbatim_html (n=93). Real Thai data is easier for the model to classify correctly, suggesting some distribution shift between augmented and real Thai patterns.

---

## 4. Artifacts ที่เก็บไว้ (สำหรับ thesis reproducibility)

| Artifact | Purpose |
|---|---|
| `models/v0.4.0-xgb-multi/` | Production model (used in inference) |
| `models/v0.5.0-xgb-multi-clean/` | Cleanup experiment model |
| `models/error_analysis/v0.4.0-xgb-multi_errors.json` | Full error report |
| `data/raw/scam_corpus.jsonl` | Production corpus (1672 records, restored) |
| `data/raw/scam_corpus.before_relabel.jsonl` | Pre-cleanup backup |
| `data/raw/sources/relabel_proposals.jsonl` | LLM cleanup audit trail |

ทุก artifact re-runnable ผ่าน:
- `python -m ml.error_analysis --version v0.4.0-xgb-multi`
- `python -m ml.relabel_other --apply` (dry-run default)
