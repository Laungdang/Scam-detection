# data/annotation — แบบตัดสินสำหรับ annotator

| ไฟล์ | ใคร | สถานะ |
|---|---|---|
| **รอบ 3 (guideline v2.0)** — `v2.0_blind_excerpt.md` (อ่านก่อน), `v2_blind_A1.md` / `v2_blind_A2.md` (ตอบ 39 ข้อ), `v2.0_calibration_blind.csv` (ต้นฉบับ) | A1, A2 | **รอ** |
| รอบ 2 (guideline v1.3) — `blind_A1.md/.csv`, `blind_A2.md/.csv`, `v1.1_calibration_blind.csv` | A1, A2 | เสร็จ 2026-08-30 — κ 0.24 → นำไปสู่ v2.0 (`data/processed/iaa_round2_report.md`) |
| `kaggle_tu_safe_review.csv` | A1 review 146 template safe | เสร็จ 2026-08-30 (approved ทั้งหมด) |

**รอบ 3 วิธีทำ:** อ่าน `v2.0_blind_excerpt.md` (5 นาที — มี self-test 3 ข้อ) → ตอบใน `v2_blind_A1.md` / `v2_blind_A2.md` หรือในแชท (`C01 safe`, `C04 caution ถามแม่เบอร์เดิม`) → **ห้ามเปิด `ANNOTATION_GUIDELINE.md` §8** ก่อนส่ง → κ ด้วย `python -m ml.annotation.agreement --a ... --b ...` (รองรับ .md ผ่าน converter ในแชท หรือ .csv)

## วิธีกรอก blind sheet (ทั้ง A1 และ A2 ทำเหมือนกัน แยกกันทำ ห้ามปรึกษา)

1. อ่าน `data/ANNOTATION_GUIDELINE.md` เฉพาะ **Quick card + §0 + §1.1 + §1.3** (~10 นาที) — **ห้ามเปิด §1.2 (calibration table) ก่อนกรอกเสร็จ** เพราะมีเฉลย
2. เปิดไฟล์ของตัวเอง (`blind_A1.csv` / `blind_A2.csv`) กรอก 4 คอลัมน์ท้ายทุกแถว:
   - `verdict`: `safe` / `caution` / `danger`
   - `category`: ถ้า verdict ≠ safe ใส่ 1 ค่า: phishing_link / impersonation_authority / financial_fraud / prize_scam / loan_offer / investment_scam / romance_scam / borrowing_scam / other (safe → เว้นว่าง)
   - `needs_info`: ถ้า caution เพราะข้อมูลไม่พอ ใส่รหัสคั่นด้วย `;` จาก: url / sender_identity / seller_identity / platform_policy / seller_reputation / verify_with_claimed_person / account_name_match (ไม่งั้นเว้นว่าง)
   - `notes`: เหตุผลสั้นๆ (ไม่บังคับ แต่ช่วยตอน adjudicate)
3. คอลัมน์ `input_form_metadata_variant` คือข้อมูลนอกข้อความที่ให้ (เช่น metadata ผู้ส่ง) — `—` = ไม่มี = ถือว่าผู้ส่งไม่รู้จัก
4. save เป็น UTF-8 (Excel: "CSV UTF-8") แล้ว commit ก่อนเปิด §1.2

## คำนวณ κ

```bash
python -m ml.annotation.agreement --a data/annotation/blind_A1.csv --b data/annotation/blind_A2.csv
```

รายงาน κ (verdict) และ κ (category) + รายการที่ไม่ตรง → คนที่ 3 ตัดสิน → บันทึกลง guideline §7 / changelog ตาม protocol §5
