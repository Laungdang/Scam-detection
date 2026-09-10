# Inter-annotator agreement — รอบที่ 4 (guideline v2.1, quiz artifact, 39 แถว, 2026-08-31)

**ชุด:** calibration set v2.1 §8 — ตอบผ่านหน้าเว็บแบบทดสอบ (กติกา → self-test 3 ข้อมีเฉลย → 39 ข้อ) โดยไม่เห็นกันและกัน

| เทียบ | ตรงกัน | κ | |
|---|---|---|---|
| **A1 vs A2** | 22/39 (56%) | **0.27** | fair (รอบ 2: 0.24, รอบ 3: 0.27) |
| A1 vs guideline v2.1 | 36/39 (92%) | **0.88** | almost perfect (รอบ 3: 0.71) |
| A2 vs guideline v2.1 | 20/39 (51%) | 0.20 | fair (รอบ 3: 0.15) |
| A1 test-retest รอบ 3→4 | 34/38 | 0.83 | |
| A2 test-retest รอบ 3→4 | 37/39 | 0.88 | |

การกระจาย: A1 {'safe': 12, 'caution': 9, 'danger': 18} · A2 {'safe': 4, 'caution': 7, 'danger': 28} · guideline {'safe': 12, 'caution': 10, 'danger': 17}
needs_info ซ้อนกันอย่างน้อย 1 รหัสในแถวที่ทั้งคู่ caution: 2/2

## ไม่ตรงกัน A1/A2 (17)

| id | ข้อความ | A1 | A2 | v2.1 | หมายเหตุ A2 |
|---|---|---|---|---|---|
| C07 | SCB: รายการโอนเงิน 500.00 บาท ไปยัง xxx-x-x1234  | safe | caution | safe | เช็คก่อนว่ามีเงินหายจากบัญชีมั้ย อย่าเพิ่งกดอ |
| C08 | บัญชีของคุณถูกระงับ กรุณายืนยันตัวตนด่วนที่ลิงก์ | danger | caution | danger | โทรเช็คที่ธนาคาร ไม่กด link |
| C09 | ระบบแจ้งให้ยืนยันข้อมูลบางอย่างภายในวันนี้ | caution | danger | caution |  |
| C11 | คุณเป็นผู้โชคดีได้รับวงเงินกู้จาก ธปท. 200,000 บ | danger | caution | danger |  |
| C13 | หวัดดี เปลี่ยนเบอร์ใหม่นะ เซฟไว้ด้วย | safe | danger | safe |  |
| C14 | หวัดดี เปลี่ยนเบอร์ใหม่นะ ขอยืมเงิน 5,000 ด่วน เ | caution | danger | caution |  |
| C15 | ขอโทษที่รบกวน ฉันอ่านโปรไฟล์คุณบน LinkedIn อยากเ | safe | danger | safe |  |
| C19 | ร้านกาแฟแถวรังสิตรับพาร์ทไทม์ ชั่วโมงละ 70 บาท ม | safe | danger | safe |  |
| C23 | มีใครขายชีท SC135 บ้างครับ line: @id | safe | danger | safe |  |
| C25 | ของอยู่ต่างจังหวัด โอนก่อนส่งเท่านั้น ราคาพิเศษถ | caution | danger | caution |  |
| C26 | รีบโอนก่อนนะ เหลือคนเดียวแล้ว | caution | danger | caution |  |
| C27 | รีบโอนก่อนนะ เหลือคนเดียวแล้ว line: @id | caution | danger | caution |  |
| C28 | มีคนจองหลายคน ถ้าเอาโอนมัดจำมาก่อนได้เลย ทัก DM | caution | danger | caution |  |
| C31 | ทักไลน์อย่างเดียวคับ ไม่ค่อยตอบในกลุ่ม | safe | caution | safe | ยังไม่ต้องทัก ถ้าเค้ารู้จักเรา เค้าต้องทักมา |
| C32 | ทักไลน์อย่างเดียวคับ ไม่ค่อยตอบในกลุ่ม line: @id | safe | caution | safe | ยังไม่ต้องทัก ถ้าเค้ารู้จักเรา เค้าต้องทักมา |
| C35 | รุ่นพี่ฝากบอกให้โอนค่าชีทด่วน ไม่งั้นหมดสิทธิ์ | caution | danger | caution |  |
| C38b | มีลิงก์รายละเอียดกิจกรรมส่งมาในกลุ่ม ลองดูนะ | safe | danger | caution |  |
## อ่านผล

1. **A1 vs guideline v2.1 = 0.88** — design นิ่งกับผู้เขียนแล้ว (0.38 → 0.71 → 0.88)
2. **A2 test-retest = 0.88** — A2 *สม่ำเสมอ* แล้ว (รอบ 3→4 ตอบเหมือนเดิม 37/39) และผ่าน self-test (C01/C06 safe) → ไม่ใช่ปัญหาอ่านโจทย์อีกต่อไป แต่ A2 มี **โมเดลตัดสินที่ต่างจาก guideline อย่างเป็นระบบ**: คนไม่รู้จัก + เงิน = danger ทุกกรณี (marketplace โอนก่อน 5/5, opener เปลี่ยนเบอร์/LinkedIn, ประกาศงานร้านกาแฟ, โพสต์หาซื้อ) และใช้ caution = "โทรเช็ค" แม้กับ phishing ชัดเจน (C08)
3. κ A1/A2 = 0.27 จึงวัด "ความต่างของเกณฑ์ระหว่างคน" ไม่ใช่ความคลุมเครือของ guideline — 17 แถวที่ต่างกัน 14 แถวเป็นเรื่อง caution↔danger บนเส้น "ผู้ขายไม่รู้จัก" และ "opener"
4. **ทั้งคู่ตรงกันแต่ต่างจาก guideline 2 แถว** — C03 "ของถูกมาก แต่ต้องจองภายในวันนี้" (ทั้งคู่ caution, guideline safe) และ C24 "ขอโอนเต็มก่อน เดี๋ยวส่งเลขพัสดุให้" (ทั้งคู่ danger, guideline caution) → candidate แก้ guideline v2.2 ถ้า A3 เห็นด้วย

## ทางไปต่อ (ตาม protocol §7 ข้อ 4: ไม่ตรง → คนที่ 3)

- ให้ **A3** (คนที่ตัดสิน Q5) ทำ quiz ชุดเดียวกัน → majority ต่อแถว บอกได้ว่าเกณฑ์ของใครเป็น outlier บน 17 แถว และตัดสิน C03/C24
- ถ้า A3 ไปทาง A1 → รายงาน κ(A1,A3) เป็นหลัก + อธิบาย A2 เป็น "strict annotator" ใน limitations; ถ้า A3 ไปทาง A2 → guideline ต้องขยับเส้น marketplace เป็น danger (v2.2) แล้ว A1 ตอบใหม่
- ห้าม annotate tier A จนกว่า κ ของคู่ที่ใช้จริง ≥ 0.6

## + A3 (2026-08-31) — 3 annotators, 39 แถว

| คู่ | ตรงกัน | κ |
|---|---|---|
| A1 vs A2 | 22/39 | 0.27 fair |
| **A1 vs A3** | 29/39 | **0.61 substantial** ← คู่แรกที่ถึงเกณฑ์ ≥ 0.6 |
| A2 vs A3 | 22/39 | 0.30 fair |
| A1 vs guideline v2.1 | 36/39 | 0.88 |
| A3 vs guideline v2.1 | 30/39 | 0.65 |
| A2 vs guideline v2.1 | 20/39 | 0.20 |
| mean pairwise κ (3 คน) | — | 0.39 |

- majority (≥2/3) มีบน 37/39 แถว (ไม่มี: C13 เปลี่ยนเบอร์ใหม่ safe/danger/caution, C38b ลิงก์กิจกรรม safe/danger/caution)
- majority ตรง guideline v2.1: 31/37
- บน 17 แถวที่ A1/A2 ต่างกัน A3 ไปทาง A1 = 11, A2 = 4, ไม่ตรงใครเลย = 2 → เกณฑ์ของ A2 เป็น outlier (strict annotator)

### majority ≠ guideline (6 แถว) → v2.2

| id | ข้อความ | A1 | A2 | A3 | majority | v2.1 | v2.2 |
|---|---|---|---|---|---|---|---|
| C03 | ของถูกมาก แต่ต้องจองภายในวันนี้ | caution | caution | caution | **caution 3/3** | safe | caution + [seller_identity, seller_reputation] — "จอง" ของถูกจากคนไม่รู้จัก = ต้องจ่ายมัดจำโดยนัย |
| C14 | เปลี่ยนเบอร์ใหม่นะ ขอยืมเงิน 5,000 ด่วน | caution | danger | danger | **danger** | caution | danger — สัญญาณ #11 "อ้างเป็นคนรู้จักจากเบอร์/บัญชีใหม่ + ขอเงิน" (สูตร borrowing scam) |
| C24 | ขอโอนเต็มก่อน เดี๋ยวส่งเลขพัสดุให้ | danger | danger | caution | **danger** | caution | danger — #8 ขยาย: "โอนเต็มก่อน / โอนก่อนเท่านั้น" (จ่ายเต็มเป็นทางเดียว) = danger |
| C25 | ของอยู่ต่างจังหวัด โอนก่อนส่งเท่านั้น ราคาพิเศษถึงวันนี้ | caution | danger | danger | **danger** | caution | danger — เดียวกับ C24 ("เท่านั้น") |
| C31 | ทักไลน์อย่างเดียวคับ ไม่ค่อยตอบในกลุ่ม | safe | caution | caution | **caution** | safe | caution + [seller_reputation, sender_identity] — ดึงออกจากที่สาธารณะโดยไม่มีเหตุผล |
| C32 | C31 + line: @id | safe | caution | caution | **caution** | safe | เดียวกับ C31 |

สังเกต: C26 "รีบโอนก่อนนะ เหลือคนเดียว" (majority caution) และ C28 "มัดจำ" (caution) ยังคง caution → เส้นแบ่งที่ 3 คนใช้จริงคือ **"โอนเต็ม / เท่านั้น" = danger, "มัดจำ / รีบโอนก่อน" = caution** — ชัดกว่ากฎเดิม

A1 ถูก majority overrule 4 แถว (C14, C25, C31, C32) — บันทึกไว้ตาม protocol §7 ข้อ 4; A1 vs v2.2 คาดว่า ≈ 32/39
