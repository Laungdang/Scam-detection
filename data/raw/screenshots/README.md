# data/raw/screenshots — screenshot SMS/แชทจากแหล่งข่าว (→ tier A ผ่าน OCR + คนตรวจ)

## วิธีเก็บ (ทำทีละรูป ~1 นาที)

1. เปิดโพสต์/ข่าวที่มี**ภาพ SMS หรือแชทของมิจฉาชีพจริง** (ไม่เอาแบนเนอร์/กราฟิกที่สื่อทำเอง)
2. Save รูปลงโฟลเดอร์ตามแหล่ง: `data/raw/screenshots/{source}/` ตั้งชื่อ `YYYYMMDD_NN.png` (วันที่โพสต์ + ลำดับ)
3. เพิ่ม 1 บรรทัดใน `log.csv`: ชื่อไฟล์, แหล่ง, URL ของโพสต์ (ต้องเปิดแล้วเห็นรูปนี้), วันที่โพสต์, หมายเหตุ (เช่น "SMS อ้าง SCB", "แชทไลน์ขอ OTP")
4. ครบชุดแล้วรัน `python -m ml.scrape.screenshot_intake` → OCR → ไฟล์ให้คนตรวจข้อความที่อ่านได้ → append เป็น tier A (`extraction_method = verbatim_ocr`)

## กติกา provenance (CLAUDE.md 10.3)
- ไม่มี URL = ไม่เก็บ · รูปที่ตัดต่อ/ครอปข้อความหาย = ข้าม · 1 รูปอาจมีหลายข้อความ ได้หลาย record
- PII ในรูป (เบอร์/บัญชี/ชื่อเหยื่อ) จะถูก mask ตอน intake — ไม่ต้องเบลอเอง
- แหล่งที่ใช้ได้: เพจ/เว็บหน่วยงานรัฐ ธนาคาร สำนักข่าว (fair use วิจัย) · Pantip/X ใช้ได้ถ้าเป็นโพสต์สาธารณะ บันทึก URL โพสต์

## source folder ที่แนะนำ
`ccib` (ตำรวจไซเบอร์ FB) · `police` (เพจตำรวจอื่น) · `bank` (SCB/KBank/BBL/KTB) · `telco` (AIS/True/dtac) · `news` (ไทยรัฐ/ข่าวสด/PPTV/Thai PBS) · `pantip` · `x` · `whoscall`
