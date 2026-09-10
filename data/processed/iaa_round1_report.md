# Inter-annotator agreement — รอบที่ 1 (2026-08-30)

**ชุด:** 7 คำถาม calibration จาก external comparison (Kaggle-TU) = 14 record (template × variant) + ชุดที่ 2 อีก 12 ข้อ
**Annotator:** A1 = ผู้ทำ thesis (ตอบ 2026-08-29 ก่อนมี guideline v1.1) · A2 = คนที่ 2 (ตอบ 2026-08-30 จาก packet โดยไม่เห็นคำตอบ A1)
**Guideline:** A1 ตอบก่อน v1.1 ถูกเขียน (คำตอบ A1 คือที่มาของ v1.1) · A2 อ่าน Quick card + §0-§1.1 ของ v1.1

## ผล

| ระดับ | n | agreement | Cohen's κ | Landis-Koch |
|---|---|---|---|---|
| ต่อ template (cluster — วิธีที่ guideline §5 กำหนด) | 7 | 6/7 = 86% | **0.77** | substantial |
| ต่อ record (นับ variant ซ้ำ — ไม่แนะนำ) | 14 | 11/14 = 79% | 0.62 | substantial |
| ชุดที่ 2 vs guideline v1.1 (ไม่ใช่ IAA — A1 ไม่ได้ตอบชุดนี้) | 12 | 11/12 | — | — |

**ข้อควรระวังในการรายงาน:** n เล็กมาก (7 template) — κ มี CI กว้าง ใช้เป็น pilot เท่านั้น; รอบถัดไปต้องใช้ blind sheet 39 แถว (`data/annotation/v1.1_calibration_blind.csv`) และ tier A จริง

## ไม่ตรงกัน → คนที่ 3 ตัดสิน

| # | ข้อความ | A1 | A2 | guideline v1.1 |
|---|---|---|---|---|
| Q5 | มีลิงก์ให้กรอกข้อมูลเพื่อรับสิทธิ์ ลองเช็คก่อนนะ | caution + needs_info: url | danger | caution + url (C38) — เขียนจากคำตอบ A1 |

**A3 (adjudicator, 2026-08-30) ตัดสิน: `danger`** → final verdict ของ Q5 = danger (ทั้ง 3 record `resolved_by: adjudicator`) — **ขัดกับ guideline v1.1 แถว C38 / §1.3 / prompt rule "ลิงก์ไม่มี URL → caution + url"** ที่เขียนจากคำตอบ A1 → ต้องตัดสินใจว่าจะ bump v1.2 ให้ตาม adjudication หรือคง v1.1 แล้วบันทึกเป็น known disagreement (ดู §5 ข้อ 6)

หมายเหตุ: A2 ยังให้ **danger** กับ "งานออนไลน์วันละ 10,000 ไม่ต้องสัมภาษณ์ สมัครด่วน" (ชุดที่ 2 #8) ที่ guideline ให้ caution (opener ไม่มีช่องทาง) — เป็นจุดเดียวกับที่ระบบเคย over-flag → กฎ "opener ไม่มีช่องทาง = caution" อาจสวนสัญชาตญาณคน ควรทบทวนใน v1.2

## สิ่งที่ A2 เพิ่มให้ guideline (ยังไม่ใส่ — รอ bump v1.2)

- Q1/Q6: A2 ใช้ "เครดิตพ่อค้าในกลุ่ม / มีคนในกลุ่มยืนยันไหม" เป็นข้อมูลชี้ขาด → เสนอเพิ่มรหัส `seller_reputation` (group vouch/รีวิว) ใน needs_info closed list
- Q6: A2 ถาม "ขายอะไร" — ข้อความที่ไม่ระบุสินค้าเลยควรนับเป็น needs_info ด้วยหรือไม่ (v1.1 ยังไม่มี)
- #14: A2 แยก "ข้อความ" (caution) กับ "โทร จำเสียงได้" (safe) เอง — ตรงกับ C04/C05 แสดงว่ากฎ metadata อ่านเข้าใจได้

## Resolved (agreement) — บันทึกใน `kaggle_tu_human_adjudication.jsonl`

Q1 caution · Q2 danger · Q3 safe · Q4 danger · Q6 caution · Q7 caution — 12/14 record `status: resolved`, 3 record (Q5 variants) `awaiting_adjudicator`
