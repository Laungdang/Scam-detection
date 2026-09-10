# ข้อเสนอแก้ ANNOTATION_GUIDELINE v1.0 → v1.1 (รอคนตัดสิน)

ที่มา: external comparison กับ Kaggle TU dataset (2026-08-29) — 49 เคสที่ระบบเราไม่ตรงกับ rule-label ถูกตัดสินโดย LLM 2 บทบาท (judge ตาม guideline + skeptic) ใน 2 รอบ
**ผลรวม (LLM judge, ไม่ใช่ ground truth):** เราถูก 16 / Kaggle ถูก 31 / ผิดทั้งคู่ 2 — 49 เคสมาจาก ~20 template (augmentation) จึงนับเป็น ~20 กรณี

> ห้าม apply อัตโนมัติ — ผู้ทำ thesis ตัดสินทีละข้อ, bump `guideline_version: 1.1`, แล้ว re-annotate record ที่กระทบ (guideline §5 ข้อ 6)

## A. ข้อเสนอจากรอบ 1 (20 เคส)

1. §1.1 ขั้น 1: เพิ่มบรรทัดใต้ "→ ไม่มีเลย → safe" ว่า "ยกเว้น opener ของ scam pattern ที่รู้จัก (เปลี่ยนเบอร์ใหม่, ทักผิด/อยากรู้จัก, เสนองาน/รายได้/ผลตอบแทนเกินจริง) ที่ยังไม่มีการขอหรือช่องทาง → caution" เพื่อแก้ความขัดแย้งกับ §1.2 แถว 64/66 และ §7 #4 (จาก d84e1ee6, 66cf8b12, 9df191cf, 74fa9101, 547e76f4)
2. §1.1 ขั้น 1: ระบุว่า call-to-action ลอย ๆ ("สมัคร/ลงทะเบียน/จอง") ที่ไม่ระบุช่องทาง ลิงก์ เบอร์ บัญชี หรือข้อมูลที่ต้องให้ ไม่นับเป็น "การขอ" (จาก 547e76f4, bd7646b2)
3. §1.1 ขั้น 2: นิยาม "เร่ง+โอน" ให้ชัดว่าหมายถึงเร่งให้โอนทันที/ภายในเวลาสั้น ("โอนตอนนี้เลย", "ภายใน 1 ชม.") ไม่รวม urgency เชิงโปรโมชั่นตาม §3 ("ราคาพิเศษถึงวันนี้") — ข้อนี้ยังโต้แย้งอยู่ (skeptic เห็นว่า ถึงวันนี้+โอนก่อนส่ง ควรนับ) ให้ adjudicator ตัดสินพร้อม ac731ae5/2803e3fe ก่อนเขียนลง
4. §1.2 calibration: เพิ่ม 2 แถวชุด "งานออนไลน์": (ก) "งานออนไลน์ได้เงินวันละ 10,000 ไม่ต้องสัมภาษณ์ สมัครด่วน" → caution (opener ไม่มีช่องทาง); (ข) ข้อความเดียวกัน + "inbox ได้" หรือ "ทัก DM" → danger + investment_scam (รายได้เกินจริง + ย้ายช่องทาง = สูตรเดียวกับแถว @job888) (จาก 6a0e2a96, a97bbac9, 983ae243)
5. §1.2 calibration: เพิ่มแถว "ขอเลขบชพร้อมเพย์หน่อยคับ จะโอนค่าชีท" → safe (ผู้รับเป็นฝ่ายได้เงิน ทำตามแล้วไม่เสียอะไรตาม §0) และแถวเดียวกัน + "line: @id" → caution (ID ภายนอกจากคนไม่รู้จัก) — verdict safe ของแถวแรกยังโต้แย้ง (skeptic คง caution สำหรับ 3935a832/90790b7e) ให้ adjudicator ยืนยันก่อน
6. §1.2 calibration: เพิ่มแถว "ขอโอนเต็มก่อน เดี๋ยวส่งเลขพัสดุให้" (ผู้ขายไม่รู้จัก) → caution + financial_fraud; safe เฉพาะเมื่อบริบทระบุร้าน/คนรู้จักที่ตรวจสอบได้ (จาก 33a5df50, 590a29c2 — judge และ skeptic เห็นตรงกัน)
7. §1.2 calibration: เพิ่มแถว "ของอยู่ต่างจังหวัด โอนก่อนส่งเท่านั้น ราคาพิเศษถึงวันนี้ inbox ได้" โดยเว้น verdict ให้ adjudicator (judge: caution ตามนิยาม "มิจฉาชีพใช้บ่อยแต่คนจริงก็ใช้"; skeptic: danger เพราะตัดทุกทางตรวจสอบ+โอนบัญชีส่วนตัว+เส้นตาย+ย้ายช่องทาง โดยไม่มีสินค้า/ราคา/ร้าน) และระบุเงื่อนไขยกเป็น danger (ชื่อบัญชีไม่ตรงผู้ขาย, ปฏิเสธ COD/นัดรับ, ราคาต่ำผิดปกติ+มัดจำ)
8. §3 แถว credential_request และ money_request คอลัมน์ "ไม่บ่งชี้เมื่อ": เพิ่ม "ขอเลขบัญชี/พร้อมเพย์ *ของผู้รับ* เพื่อโอนเงิน *ให้* ผู้รับ (ผู้ซื้อถามผู้ขาย) — ผู้รับไม่เสียอะไรตาม §0" และเพิ่มหมายเหตุ escalation: ตามมาด้วยสลิปปลอม / "โอนเกิน ช่วยโอนคืน" / ขอ OTP "เพื่อยืนยันรับเงิน" / ลิงก์รับเงิน → caution/danger (จาก 8f27b79d, 0764939a, 3935a832, 90790b7e)
9. §3 แถว channel_shift: แยก 2 ระดับ — (ก) "inbox/DM/ทักแชท" บนแพลตฟอร์มเดิม = การขอในขั้น 1 แต่ไม่ใช่สัญญาณหลอกขั้น 2 โดยลำพัง และไม่ลบล้างบริบทชอบธรรม (ผู้ซื้อจะจ่ายให้); (ข) "แอดไลน์/ทักไลน์/Telegram ID" ภายนอกจากคนไม่รู้จัก = การขอที่ทำให้บริบทชอบธรรมไม่ชัด → อย่างน้อย caution เทียบ §7 #4 (จาก 6a0e2a96, a97bbac9, 983ae243, 2e13f99c, 0764939a, 50ddc59e)
10. §3 แถว money_request: ขยาย "บัญชีที่ไม่ใช่ช่องทางทางการ" ให้รวม "บัญชีบุคคลที่สามใน P2P (อ้างว่าเป็นของแฟน/ญาติ/เพื่อน ชื่อไม่ตรงผู้ขาย)" (จาก 60bcbc67)
11. §7 edge case ใหม่: "ทักไลน์อย่างเดียว / inbox ได้" ที่ให้ย้ายช่องทางส่วนตัวโดยไม่มี ID แปลกและยังไม่ขอเงิน/ข้อมูล → caution (เทียบ #4) และระบุว่าประโยคที่สั่งผู้รับ ("ทักไลน์อย่างเดียวคับ") = การขอ ไม่ใช่การเล่าเรื่องบุคคลที่สาม (จาก 2e13f99c)
12. §7 edge case ใหม่: ผู้ขายให้โอนเข้าบัญชีชื่อไม่ตรง + อ้าง "บัญชีแฟน/ญาติ ปลอดภัยแน่นอน" + "โอนมาเลย" — เว้น verdict ให้ adjudicator (judge: caution; skeptic: danger รูปแบบบัญชีม้า) แต่ระบุไว้ก่อนว่า ชื่อบัญชีไม่ตรงอย่างเดียวโดยไม่กดดัน → caution (จาก 60bcbc67)

## B. ข้อเสนอเพิ่มจากรอบ 2 (29 เคส)

1. หมายเหตุก่อนอ่าน: data/ANNOTATION_GUIDELINE.md ยังเป็น v1.0 และยังไม่ได้ apply G1–G12 ของรอบ 1 เลย — รายการด้านล่างเป็นส่วนเพิ่มเฉพาะที่รอบ 1 ยังไม่เสนอ; ให้ apply รอบ 1 ก่อนแล้ว bump guideline_version เป็น 1.1 ครั้งเดียวพร้อมรายการนี้ (§5 ข้อ 6 บังคับ re-annotate record ที่กระทบ)
2. NG1 §1.1 เพิ่ม "ขั้น 0" ก่อนขั้น 1: ถ้า text เป็นคำบอกเล่าเหตุการณ์ ไม่ใช่ข้อความที่ส่งถึงผู้รับ ("มีคนขอ…", "อ้างว่าเป็น…", "บอกว่าเป็น…", "โดนทัก…") ให้ทำเครื่องหมาย `input_form: narrative` แล้ว (ก) สำหรับ corpus tier A/S: ไม่ให้ verdict และย้ายไป tier N ตาม §4 (ห้ามเข้า train/test) (ข) สำหรับ Q&A evaluation: ประเมิน "การขอที่ถูกเล่า" เสมือนผู้เล่าเป็นผู้รับ และบันทึกว่า verdict เป็นของเหตุการณ์ ไม่ใช่ของข้อความ; เพิ่ม calibration row "มีคนขอรหัสยืนยัน บอกว่าเป็นแอดมินกลุ่ม" → narrative (ถ้าประเมินเหตุการณ์ = danger: ขอ OTP + อ้างแอดมิน) (จาก 8086e564, 998c0589, dc1c81e5 — Kaggle-TU มี template แบบนี้จำนวนมาก)
3. NG2 §1.1 ขั้น 2: รายการสัญญาณมีแค่ "อ้างหน่วยงาน+ลิงก์" และ "เร่ง+โอน" ทั้งที่ §3 urgency นับ "มาพร้อมการขอเงิน/ข้อมูล/ลิงก์" — เพิ่ม "เร่ง+ขอข้อมูล/ยืนยันตัวตน" และ "อ้างหน่วยงาน/บทบาท + ขอโอนไปบัญชี/พร้อมเพย์บุคคล" เข้ารายการขั้น 2; เพิ่ม calibration row "ระบบแจ้งให้ยืนยันข้อมูลบางอย่างภายในวันนี้" → caution (ขอข้อมูลคลุมเครือ + เส้นตาย + ไม่ระบุผู้ส่ง ไม่มีลิงก์) คู่กับ row เดิม "ถูกระงับ + ยืนยันตัวตน + ลิงก์" → danger (จาก 2ae2fe19)
4. NG3 §3 แถว authority_claim + §1.2 + §2: (ก) ขยาย "อ้างหน่วยงาน" ให้รวม "อ้างบทบาทในองค์กร/สถาบัน" (แอดมินคณะ, เจ้าหน้าที่ทะเบียน, HR, สโมสร, หัวหน้าห้อง, พี่รหัส) และเพิ่มคอลัมน์ "บ่งชี้เมื่อ": "อ้างหน่วยงาน/บทบาท + ขอค่าธรรมเนียมเพื่อรับสิทธิ์ (ค่าจอง/ค่ายืนยันสิทธิ์/ค่าสมัคร) + โอนไปพร้อมเพย์เบอร์บุคคล/บัญชีที่ให้ในแชท (+ เส้นตาย) → danger, financial_fraud"; (ข) นิยาม "ช่องทางทางการ" ของสถาบัน = ระบบทะเบียน/bill payment/QR ในนามสถาบัน ไม่ใช่บัญชีที่ให้มาในแชท; (ค) เพิ่ม calibration row "แอดมินคณะขอค่าจองสิทธิ์สอบ โอนมาที่ พร้อมเพย์ 08x-xxx-xxxx ภายในวันนี้" → danger และ row อ่อนกว่า "…โอนมาที่ บัญชี xxx123 ภายในวันนี้" → danger (confidence ต่ำกว่า) เป็นตัวอย่างขอบเขต; (ง) เติมเหตุผลของ row "แม่โอนค่าเทอมด่วน → safe" ว่า safe เพราะผู้รับรู้จักผู้ส่งจริง ไม่ใช่เพราะเป็นบริบทการศึกษา — กัน annotator เหมาบริบทนักศึกษาเป็นชอบธรรม (จาก 17d4cf70, b554c5e9, 22b55ec6, 18cce6a2, 2d310f04)
5. NG4 §1.1 ขั้น 3 + §3 แถว borrowing_pretext: แก้ความขัดแย้งระหว่าง "annotator รู้ไม่ได้ → caution" กับ calibration "เปลี่ยนเบอร์+ยืมเงิน+ด่วน = danger" และ ขั้น 2 "เร่ง+โอน": ระบุว่า "บริบทชอบธรรมชัดเจน" ในขั้น 3 ต้องมาจากสิ่งที่ annotator ตรวจได้ (metadata/คำยืนยันของผู้ใช้ว่ารู้จักผู้ส่ง) ไม่ใช่จากคำอ้างในตัวข้อความ — คำอ้างความสัมพันธ์/บทบาท (รุ่นพี่, เพื่อน, แอดมิน, ฝากบอก) คือ pretext; นิยาม "ฝากบอก" (relay จากบุคคลที่สามที่ไม่ได้พูดเอง) เป็น pretext ชนิดหนึ่ง; สูตร: อ้างความสัมพันธ์ที่ตรวจไม่ได้ + ขอเงิน + เร่ง + ขู่เสียสิทธิ์/ผลเสีย → danger แม้ไม่มีเลขบัญชี; อ้างความสัมพันธ์ + ค่าใช้จ่ายสมเหตุสมผล ไม่เร่ง ไม่ขู่ ไม่มีบัญชี → caution — **แต่** calibration row "รุ่นพี่ฝากบอกให้โอนค่าชีทด่วน ไม่งั้นหมดสิทธิ์" ให้เว้น verdict ไว้ให้ adjudicator เพราะ judge และ skeptic ต่างตัดสินข้อความเดียวกันสลับกัน (43fd054d=danger, cee5f9f6=caution) (จาก 99f13ace, 43fd054d, cee5f9f6)
6. NG5 §3 แถว link_action + §7 edge case ใหม่: (ก) ข้อความที่พูดถึงลิงก์แต่ไม่แสดง URL → ประเมินโดเมน/shortener/TLD ไม่ได้ → ค่าตั้งต้น caution; ยกเป็น danger เมื่อมีสัญญาณข้อ 2 อื่นชัด (อ้างหน่วยงาน+ขู่, ขอ OTP, ย้ายไป ID ภายนอก); (ข) ข้อความบอกต่อ/เตือนที่มี hedge ("ลองเช็คก่อนนะ", "ระวังนะ") — ระบุว่าจะให้น้ำหนัก hedge หรือไม่: เว้น verdict ของ row "มีลิงก์ให้กรอกข้อมูลเพื่อรับสิทธิ์ ลองเช็คก่อนนะ inbox ได้" ให้ adjudicator (judge: caution ตามข้อห้าม "ห้าม danger เพราะมีลิงก์อย่างเดียว"; skeptic: danger เพราะ reward + เก็บข้อมูล + DM gating) (จาก 21180f5d, 8ff32eb4, 92174189)
7. NG6 §3 แถว urgency + แถวใหม่ + §7 marketplace: (ก) เพิ่ม sub-type "scarcity" (เหลือคนเดียว/เหลือชิ้นเดียว/คนจองหลายคน/โอนก่อนได้ก่อน) และระบุว่านับเป็น "เร่ง" ใน "เร่ง+โอน" หรือไม่ — ต่อยอด G3 รอบ 1 ซึ่งยังไม่ตัดสิน: รอบ 2 skeptic ยอมรับ caution สำหรับ "มัดจำ+คนจองหลายคน+DM" แต่คง danger สำหรับ "รีบโอนก่อน+เหลือคนเดียว(+DM)" → ให้ adjudicator ตัดสิน G3 พร้อมกันทั้ง 3 template (ac731ae5, 2eef8a84, f86a9303); (ข) เพิ่มแถวสัญญาณอ่อน "refuse_verification" (ไม่รับนัด/ไม่รับวิดีโอคอล/ไม่รับ COD/ส่งอย่างเดียว) — บ่งชี้เมื่อ co-occur กับสัญญาณข้อ 2, ไม่บ่งชี้ลำพัง (ผู้ขายส่งอย่างเดียวจริงใช้เป็นปกติ); (ค) §7 edge case: โอนก่อนส่ง/มัดจำ อย่างเดียว → caution; + ปฏิเสธทุกทางตรวจสอบ → ยัง caution (confidence สูงขึ้น); + LINE/Telegram ID ภายนอก / ราคาถูกผิดปกติ / ชื่อบัญชีไม่ตรง / เส้นตายโอน โดยไม่มีสินค้า-ราคา-ร้าน → danger; "ทัก DM/inbox" บนแพลตฟอร์มเดิมไม่ใช่ตัวยก (judge+skeptic ตรงกันใน 9dfccd43 และ 43d920e1) (จาก 2eef8a84, 11868295, f86a9303, 8d37ea0e, 1cbfeb8a, ac5920d7, 9dfccd43, 43d920e1)
8. NG7 §1.2 + §3 แถว financial_offer + §7: (ก) เพิ่ม calibration row ฝั่ง safe ที่ไม่มีเลยตอนนี้: "ร้านกาแฟแถวรังสิตรับพาร์ทไทม์ ชั่วโมงละ 70 บาท มีสัมภาษณ์หน้าร้าน ทัก DM/inbox ได้/ส่งในกลุ่มได้เลย" → safe (สถานที่จริง + ค่าจ้างปกติ + สัมภาษณ์ตัวจริง); caution เฉพาะเมื่อค่าตอบแทนเกินจริง/ไม่ระบุสถานที่/ต้องจ่ายก่อน; (ข) นิยาม "รายได้/ผลตอบแทนเกินจริง" เป็นตัวเลขอ้างอิง (เช่น รายชั่วโมง > ~2 เท่าค่าแรงขั้นต่ำ หรือ วันละ ≥ 1,000 โดยไม่ต้องทักษะ/สัมภาษณ์) เพื่อกัน annotator/LLM เรียก 60-80 บาท/ชม. ว่า "สูงผิดปกติ"; (ค) ระบุว่า "ส่งในกลุ่มได้เลย/ตอบในกลุ่ม" ไม่ใช่ channel_shift; (ง) ปรับถ้อยคำ G9(ก) ของรอบ 1: DM/inbox บนแพลตฟอร์มเดิม = "ช่องทางติดต่อ" ที่ทำให้ข้อเสนอ actionable แต่ไม่ทำให้ข้อความที่ไม่มีการขอเงิน/ข้อมูล/ลิงก์หลุดจาก "ไม่มีการขอ → safe" ด้วยตัวเอง — มิฉะนั้นโพสต์รับสมัคร/ขายของทุกโพสต์จะตกขั้น 4 (caution) โดยอัตโนมัติ (ผลลัพธ์ verdict ของ G9 ไม่เปลี่ยน แต่ถ้อยคำเดิมทำให้ตีความผิดได้) (จาก 59a4e0aa, 3e6f3d5e, cc6056fe)
9. NG8 §3 แถว channel_shift + §7: เพิ่ม caveat ทิศทางแบบเดียวกับที่ G8 รอบ 1 ให้ money_request — contact handle (LINE/IG) ที่ผู้โพสต์แนบมากับโพสต์ "หาซื้อ/ประกาศ/ขอความช่วยเหลือ" ที่ผู้โพสต์เป็นฝ่ายจ่าย ไม่ใช่ "ให้ย้ายช่องทาง" → safe ถ้าไม่มีการขอเงิน/ข้อมูลจากผู้รับ; edge case "มีใครขายชีท SC135 บ้างครับ line: @id" → safe และหมายเหตุสำหรับ annotator: รหัสวิชา/ชื่อเฉพาะที่ไม่รู้จักไม่ใช่สัญญาณ (จาก 57f7514d)
10. NG9 §2 category: ระบุ mapping ให้ชัดเพื่อกัน "other": ค่าชีท/ค่าจองสิทธิ์/ค่ากิจกรรมปลอมจากผู้อ้างเป็นรุ่นพี่-แอดมิน → financial_fraud (advance fee); งานที่ต้องจ่ายค่าสมัครก่อน → financial_fraud (ถ้ามีข้อเสนอรายได้เกินจริงร่วมด้วยยังคง financial_fraud ไม่ใช่ investment_scam เพราะกลไกคือเรียกเก็บเงินก่อน); บันทึกว่า Kaggle ให้ other/investment_scam ในกลุ่มนี้เป็น label noise ที่ต้องแยกออกตอนเทียบ category (จาก 99f13ace, 17d4cf70, fbe86ceb, 998c0589)
11. NG10 §5 workflow: เพิ่มขั้น "cluster ก่อน label" — normalize ข้อความ (ตัดตัวยืด นะะะ→นะ, โอนน→โอน, จองง→จอง) แล้วจัดกลุ่ม near-duplicate ให้ annotator ตัดสินทั้ง cluster ครั้งเดียวและบันทึก cluster_id; ข้อความใน cluster เดียวกันห้ามได้ verdict ต่างกันเว้นแต่มีคำที่เปลี่ยน "การขอ" (เช่น เพิ่ม LINE ID) — หลักฐาน: judge ให้ 43fd054d=danger แต่ cee5f9f6=caution และระบบเราแต่งเรื่องต่างกันใน 2eef8a84/11868295 ทั้งที่ต่างแค่ typo; ใช้กฎเดียวกันกับการรายงานผลใน thesis (นับต่อ template ไม่ใช่ต่อ record)

## C. เคสที่ judge กับ skeptic เห็นต่าง / confidence ต่ำ — ต้องมีคน 2 คนตัดสิน (14)

| id | ข้อความ | Kaggle | เรา | judge (guideline) | conf |
|---|---|---|---|---|---|
| `kaggle-tu-ac731ae5` | ของอยู่ต่างจังหวัด โอนก่อนส่งเท่านั้น ราคาพิเศษถึงวันนี้ inbox ได้ | danger | caution | caution | 3 |
| `kaggle-tu-2803e3fe` | ของอยู่ต่างจังหวัด โอนนก่อนส่งเท่านั้น ราคาพิเศษถึงวันนี้ | danger | caution | caution | 3 |
| `kaggle-tu-60bcbc67` | บัญชีนี้ของแฟนเราเอง ปลอดภัยแน่นอน โอนมาเลย inbox ได้ | danger | caution | caution | 3 |
| `kaggle-tu-3935a832` | ขอเลขบชพร้อมเพย์หน่อยคับ จะโอนนค่าชีท | safe | caution | safe | 4 |
| `kaggle-tu-90790b7e` | ขอเลขบัญชีพร้อมเพย์น่อยครับ จะโอนนค่าชีท inbox ได้ | safe | caution | safe | 4 |
| `kaggle-tu-8086e564` | มีคนขอรหัสยืนยัน บอกว่าเป็นแอดมินกลุ่ม | caution | danger | safe | 2 |
| `kaggle-tu-21180f5d` | มีลิงก์ให้กรอกข้อมูลเพื่อรับสิทธิ์ ลองเช็คก่อนนะ inbox ได้ | caution | danger | caution | 3 |
| `kaggle-tu-8ff32eb4` | มีลิ้งให้กรอกข้อมูลเพื่อรับสิทธิ์ ลองเช็คก่อนนะ | caution | danger | caution | 3 |
| `kaggle-tu-92174189` | มีลิงก์ให้กรอกข้อมูลเพื่อรับสิทธิ์ ลองเช็คก่อนนะะะ | caution | danger | caution | 3 |
| `kaggle-tu-f86a9303` | รีบโอนก่อนนะะะ เหลือคนเดียวแล้ว | caution | danger | caution | 3 |
| `kaggle-tu-8d37ea0e` | รีบโอนก่อนนะ เหลือคนเดียวแล้ว ทัก DM | caution | danger | caution | 3 |
| `kaggle-tu-99f13ace` | รุ่นพี่ฝากบอกให้โอนค่าชีทด่วนนน ไม่งั้นหมดสิทธิ์ ส่งในกลุ่มได้เลย | danger | caution | danger | 3 |
| `kaggle-tu-43fd054d` | รุ่นพี่ฝากบอกให้โอนค่าชีทด่วน ไม่งั้นหมดสิทธิ์ | danger | caution | danger | 3 |
| `kaggle-tu-cee5f9f6` | รุ่นพี่ฝากบอกให้โอนนค่าชีทด่วน ไม่งั้นหมดสิทธิ์ | danger | caution | caution | 4 |

## D. ตารางตัดสินทั้ง 49 เคส

| id | ข้อความ | Kaggle | เรา | guideline | ฝ่ายถูก | เหตุผล |
|---|---|---|---|---|---|---|
| `kaggle-tu-bd7646b2` | ของถูกมาก แต่ต้องจองภายในวันนี้ | caution | safe | safe | ours | urgency_only |
| `kaggle-tu-ac731ae5` | ของอยู่ต่างจังหวัด โอนก่อนส่งเท่านั้น ราคาพิเศษถึงวันนี้ inb | danger | caution | caution | ours | marketplace_transfer_first_ambiguous |
| `kaggle-tu-2803e3fe` | ของอยู่ต่างจังหวัด โอนนก่อนส่งเท่านั้น ราคาพิเศษถึงวันนี้ | danger | caution | caution | ours | marketplace_transfer_first_ambiguous |
| `kaggle-tu-8f27b79d` | ขอเลขบชพร้อมเพย์น่อยคับ จะโอนค่าชีท | safe | caution | safe | kaggle | inbound_payment_account_request |
| `kaggle-tu-0764939a` | ขอเลขบชพร้อมเพย์หน่อยครับ จะโอนนค่าชีท ทัก DM | safe | caution | safe | kaggle | inbound_payment_account_request |
| `kaggle-tu-3935a832` | ขอเลขบชพร้อมเพย์หน่อยคับ จะโอนนค่าชีท | safe | caution | safe | kaggle | recipient_account_as_credential |
| `kaggle-tu-90790b7e` | ขอเลขบัญชีพร้อมเพย์น่อยครับ จะโอนนค่าชีท inbox ได้ | safe | caution | safe | kaggle | recipient_account_as_credential |
| `kaggle-tu-50ddc59e` | ขอเลขบัญชีพร้อมเพย์หน่อยครับ จะโอนค่าชีท line: @fakeid | safe | danger | caution | neither | payment_direction_misread |
| `kaggle-tu-33a5df50` | ขอโอนนเต็มก่อน เด๋วส่งเลขพัสดุให้ | caution | safe | caution | kaggle | marketplace_pay_first_unverified |
| `kaggle-tu-590a29c2` | ขอโอนเต็มก่อน เด๋วส่งเลขพัสดุให้ | caution | safe | caution | kaggle | marketplace_pay_first_unverified |
| `kaggle-tu-d84e1ee6` | งานออนไลน์ได้เงินวันละ 10,000 ไม่ต้องสัมภาษณ์ สมัครด่วนนน | danger | caution | caution | ours | unrealistic_offer_no_request_channel |
| `kaggle-tu-66cf8b12` | งานออนไลน์ได้เงินวันละ 10,000 ไม่ต้องสัมภาษณ์ สมัครด่วน | danger | caution | caution | ours | unrealistic_offer_no_request_channel |
| `kaggle-tu-6a0e2a96` | งานออนไลน์ได้เงินวันละ 3000 ไม่ต้องสัมภาษณ์ สมัครด่วน inbox  | danger | caution | danger | kaggle | channel_shift_inbox_missed |
| `kaggle-tu-9df191cf` | งานออนไลน์ได้เงินวันละ 5000 ไม่ต้องสัมภาษณ์ สมักด่วน | danger | caution | caution | ours | unrealistic_offer_no_request_channel |
| `kaggle-tu-74fa9101` | งานออนไลน์ได้เงินวันละ 8000 ไม่ต้องสัมภาษณ์ สมักด่วน | danger | caution | caution | ours | unrealistic_offer_no_request_channel |
| `kaggle-tu-a97bbac9` | งานออนไลน์ได้เงินวันละ 5000 ไม่ต้องสัมภาษณ์ สมัครด่วน inbox  | danger | caution | danger | kaggle | income_offer_plus_channel_shift |
| `kaggle-tu-983ae243` | งานออนไลน์ได้เงินวันละ 8000 ไม่ต้องสัมภาษณ์ สมัครด่วน ทัก DM | danger | caution | danger | kaggle | income_offer_plus_channel_shift |
| `kaggle-tu-2e13f99c` | ทักไลน์อย่างเดียวคับ ไม่ค่อยตอบในกลุ่ม | caution | safe | caution | kaggle | channel_shift_only_directive_misread |
| `kaggle-tu-547e76f4` | งานออนไลน์ได้เงินวันละ 8000 ไม่ต้องสัมภาษณ์ สมัครด่วนนน | danger | caution | caution | ours | income_offer_without_contact_channel |
| `kaggle-tu-60bcbc67` | บัญชีนี้ของแฟนเราเอง ปลอดภัยแน่นอน โอนมาเลย inbox ได้ | danger | caution | caution | ours | marketplace_third_party_account_ambiguous |
| `kaggle-tu-8086e564` | มีคนขอรหัสยืนยัน บอกว่าเป็นแอดมินกลุ่ม | caution | danger | safe | neither | narrative_report_not_request |
| `kaggle-tu-2eef8a84` | มีคนจองหลายคน ถ้าเอาโอนมัดจำมาก่อนได้เลย ทัก DM | caution | danger | caution | kaggle | marketplace_deposit_weak_signal |
| `kaggle-tu-11868295` | มีคนจองงหลายคน ถ้าเอาโอนมัดจำมาก่อนได้เลย ทัก DM | caution | danger | caution | kaggle | marketplace_deposit_weak_signal |
| `kaggle-tu-21180f5d` | มีลิงก์ให้กรอกข้อมูลเพื่อรับสิทธิ์ ลองเช็คก่อนนะ inbox ได้ | caution | danger | caution | kaggle | link_mention_no_url_hedged |
| `kaggle-tu-8ff32eb4` | มีลิ้งให้กรอกข้อมูลเพื่อรับสิทธิ์ ลองเช็คก่อนนะ | caution | danger | caution | kaggle | link_mention_no_url_hedged |
| `kaggle-tu-92174189` | มีลิงก์ให้กรอกข้อมูลเพื่อรับสิทธิ์ ลองเช็คก่อนนะะะ | caution | danger | caution | kaggle | link_mention_no_url_hedged |
| `kaggle-tu-57f7514d` | มีใครขายชีท SC135 บ้างครับ line: @fakeid | safe | danger | safe | kaggle | buyer_contact_handle_not_channel_shift |
| `kaggle-tu-2ae2fe19` | ระบบแจ้งให้ยืนยันข้อมูลบางอย่างภายในวันนี้ | caution | safe | caution | kaggle | lexicon_miss_credential_verify_data |
| `kaggle-tu-f86a9303` | รีบโอนก่อนนะะะ เหลือคนเดียวแล้ว | caution | danger | caution | kaggle | seller_urgency_only_caution_not_danger |
| `kaggle-tu-8d37ea0e` | รีบโอนก่อนนะ เหลือคนเดียวแล้ว ทัก DM | caution | danger | caution | kaggle | seller_urgency_only_caution_not_danger |
| `kaggle-tu-99f13ace` | รุ่นพี่ฝากบอกให้โอนค่าชีทด่วนนน ไม่งั้นหมดสิทธิ์ ส่งในกลุ่มไ | danger | caution | danger | kaggle | claimed_acquaintance_taken_as_real_context |
| `kaggle-tu-43fd054d` | รุ่นพี่ฝากบอกให้โอนค่าชีทด่วน ไม่งั้นหมดสิทธิ์ | danger | caution | danger | kaggle | claimed_acquaintance_taken_as_real_context |
| `kaggle-tu-cee5f9f6` | รุ่นพี่ฝากบอกให้โอนนค่าชีทด่วน ไม่งั้นหมดสิทธิ์ | danger | caution | caution | ours | kaggle_keyword_overtrigger_urgency_money |
| `kaggle-tu-43d920e1` | รีบโอนนก่อนนะ เหลือคนเดียวแล้ว line: @fakeid | caution | danger | danger | ours | kaggle_softcap_prepay_plus_channel_shift |
| `kaggle-tu-59a4e0aa` | ร้านกาแฟแถวรังสิตรับพาร์ทไทม์ ชั่วโมงละ 70 บาท มีสัมภาษณ์หน้ | safe | caution | safe | kaggle | rag_anchoring_legit_job_post |
| `kaggle-tu-3e6f3d5e` | ร้านกาแฟแถวรังสิตรับพาร์ทไทม์ ชั่วโมงละ 60 บาท มีสัมภาษณ์หน้ | safe | caution | safe | kaggle | rag_anchoring_legit_job_post |
| `kaggle-tu-cc6056fe` | ร้านกาแฟแถวรังสิตรับพาร์ทไทม์ ชั่วโมงละ 80 บาท มีสัมภาษณ์หน้ | safe | caution | safe | kaggle | rag_anchoring_legit_job_post |
| `kaggle-tu-fbe86ceb` | สมักงานง่ายๆ ได้เงินเร็ว แต่ต้องจ่ายค่าสมัครก่อน line: @fake | caution | danger | danger | ours | kaggle_softcap_upfront_fee_job |
| `kaggle-tu-a8e28c7c` | สมัครงานง่ายๆ ได้เงินเร็ว แต่ต้องจ่ายค่าสมัครก่อน ทัก DM | caution | danger | danger | ours | kaggle_under_advance_fee_job |
| `kaggle-tu-998c0589` | อ้างว่าเป็นรุ่นพี่คณะ ขอให้โอนเงินช่วยจองงสิทธิ์ ทัก DM | caution | danger | danger | ours | kaggle_under_peer_impersonation_fee |
| `kaggle-tu-dc1c81e5` | อ้างว่าเป็นรุ่นพี่คณะ ขอให้โอนเงินช่วยจองสิทธิ์ inbox ได้ | caution | danger | danger | ours | kaggle_under_peer_impersonation_fee |
| `kaggle-tu-17d4cf70` | แอดมินคณะขอค่าจองงสิทธิ์สอบ โอนมาที่ พร้อมเพย์ 08x-xxx-xxxx  | danger | caution | danger | kaggle | ours_under_urgent_transfer_unofficial_channel |
| `kaggle-tu-b554c5e9` | แอดมินคณะขอค่าจองสิทธิ์สอบ โอนนมาที่ xxx-x-xxxxx-x ภายในวันน | danger | caution | danger | kaggle | ours_under_urgent_transfer_unofficial_channel |
| `kaggle-tu-22b55ec6` | แอดมินคณะขอค่าจองสิทธิ์สอบ โอนมาที่ xxx-x-xxxxx-x ภายในวันนี | danger | caution | danger | kaggle | ours_under_urgent_transfer_unofficial_channel |
| `kaggle-tu-18cce6a2` | แอดมินคณะขอค่าจองสิทธิ์สอบ โอนนมาที่ พร้อมเพย์ 08x-xxx-xxxx  | danger | caution | danger | kaggle | role_claim_fake_fee_urgent_transfer |
| `kaggle-tu-2d310f04` | แอดมินคณะขอค่าจองสิทธิ์สอบ โอนมาที่ บัญชี xxx123 ภายในวันนี้ | danger | caution | danger | kaggle | role_claim_fake_fee_urgent_transfer |
| `kaggle-tu-9dfccd43` | โอนเต็มก่อนเท่านั้น ไม่รับนัด ไม่รับวิดีโอคอล inbox ได้ | danger | caution | caution | ours | marketplace_prepay_refuse_verification |
| `kaggle-tu-1cbfeb8a` | ไม่สะดวกนัดรับ ขอส่งอย่างเดียว โอนก่อนส่งนะะะ ทัก DM | caution | danger | caution | kaggle | marketplace_prepay_only |
| `kaggle-tu-ac5920d7` | ไม่สะดวกนัดรับ ขอส่งอย่างเดียว โอนก่อนส่งนะ ทัก DM | caution | danger | caution | kaggle | marketplace_prepay_only |