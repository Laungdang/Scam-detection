# หลังแก้ lexicon/prompt (post-fix) — 49 เคสที่เคยต่างจาก Kaggle

guideline verdict = คำตัดสินของ LLM judge ตาม ANNOTATION_GUIDELINE v1.0 (ไม่ใช่ ground truth; 14 เคสยังรอคนตัดสิน)

| | ตรง guideline | / 49 |
|---|---|---|
| Kaggle rule-label | 31 | 63% |
| ระบบเรา **ก่อนแก้** | 16 | 33% |
| ระบบเรา **หลังแก้** | 31 | 63% |

- ดีขึ้น (ผิด→ถูก): **21** | แย่ลง (ถูก→ผิด): **6** | ยังไม่ตรง guideline: 18 | ตอบ off_topic/chat/error: 0
- หลังแก้ ตรงกับ Kaggle: 27/49 (เดิม 0 — ทั้ง 49 คือเคสที่ต่าง)
- RAG ถูกเปิด: ก่อน 45 → หลัง 47

## ยังไม่ตรง guideline หลังแก้

| id | ข้อความ | Kaggle | guideline | ก่อน | หลัง | กลุ่ม |
|---|---|---|---|---|---|---|
| `kaggle-tu-8f27b79d` | ขอเลขบชพร้อมเพย์น่อยคับ จะโอนค่าชีท | safe | safe | caution | caution | inbound_payment_account_request |
| `kaggle-tu-0764939a` | ขอเลขบชพร้อมเพย์หน่อยครับ จะโอนนค่าชีท ทัก DM | safe | safe | caution | caution | inbound_payment_account_request |
| `kaggle-tu-3935a832` | ขอเลขบชพร้อมเพย์หน่อยคับ จะโอนนค่าชีท | safe | safe | caution | caution | recipient_account_as_credential |
| `kaggle-tu-90790b7e` | ขอเลขบัญชีพร้อมเพย์น่อยครับ จะโอนนค่าชีท inbox ได้ | safe | safe | caution | caution | recipient_account_as_credential |
| `kaggle-tu-50ddc59e` | ขอเลขบัญชีพร้อมเพย์หน่อยครับ จะโอนค่าชีท line: @fakeid | safe | caution | danger | danger | payment_direction_misread |
| `kaggle-tu-33a5df50` | ขอโอนนเต็มก่อน เด๋วส่งเลขพัสดุให้ | caution | caution | safe | danger | marketplace_pay_first_unverified |
| `kaggle-tu-d84e1ee6` | งานออนไลน์ได้เงินวันละ 10,000 ไม่ต้องสัมภาษณ์ สมัครด่วน | danger | caution | caution | danger | unrealistic_offer_no_request_channel |
| `kaggle-tu-66cf8b12` | งานออนไลน์ได้เงินวันละ 10,000 ไม่ต้องสัมภาษณ์ สมัครด่วน | danger | caution | caution | danger | unrealistic_offer_no_request_channel |
| `kaggle-tu-9df191cf` | งานออนไลน์ได้เงินวันละ 5000 ไม่ต้องสัมภาษณ์ สมักด่วน | danger | caution | caution | danger | unrealistic_offer_no_request_channel |
| `kaggle-tu-74fa9101` | งานออนไลน์ได้เงินวันละ 8000 ไม่ต้องสัมภาษณ์ สมักด่วน | danger | caution | caution | danger | unrealistic_offer_no_request_channel |
| `kaggle-tu-2e13f99c` | ทักไลน์อย่างเดียวคับ ไม่ค่อยตอบในกลุ่ม | caution | caution | safe | safe | channel_shift_only_directive_misread |
| `kaggle-tu-547e76f4` | งานออนไลน์ได้เงินวันละ 8000 ไม่ต้องสัมภาษณ์ สมัครด่วนนน | danger | caution | caution | danger | income_offer_without_contact_channel |
| `kaggle-tu-8086e564` | มีคนขอรหัสยืนยัน บอกว่าเป็นแอดมินกลุ่ม | caution | safe | danger | danger | narrative_report_not_request |
| `kaggle-tu-21180f5d` | มีลิงก์ให้กรอกข้อมูลเพื่อรับสิทธิ์ ลองเช็คก่อนนะ inbox  | caution | caution | danger | danger | link_mention_no_url_hedged |
| `kaggle-tu-8ff32eb4` | มีลิ้งให้กรอกข้อมูลเพื่อรับสิทธิ์ ลองเช็คก่อนนะ | caution | caution | danger | danger | link_mention_no_url_hedged |
| `kaggle-tu-92174189` | มีลิงก์ให้กรอกข้อมูลเพื่อรับสิทธิ์ ลองเช็คก่อนนะะะ | caution | caution | danger | danger | link_mention_no_url_hedged |
| `kaggle-tu-f86a9303` | รีบโอนก่อนนะะะ เหลือคนเดียวแล้ว | caution | caution | danger | danger | seller_urgency_only_caution_not_danger |
| `kaggle-tu-cee5f9f6` | รุ่นพี่ฝากบอกให้โอนนค่าชีทด่วน ไม่งั้นหมดสิทธิ์ | danger | caution | caution | danger | kaggle_keyword_overtrigger_urgency_money |

## แย่ลง

- `kaggle-tu-d84e1ee6` งานออนไลน์ได้เงินวันละ 10,000 ไม่ต้องสัมภาษณ์ สมัครด่วนนน — guideline caution, ก่อน caution → หลัง danger
- `kaggle-tu-66cf8b12` งานออนไลน์ได้เงินวันละ 10,000 ไม่ต้องสัมภาษณ์ สมัครด่วน — guideline caution, ก่อน caution → หลัง danger
- `kaggle-tu-9df191cf` งานออนไลน์ได้เงินวันละ 5000 ไม่ต้องสัมภาษณ์ สมักด่วน — guideline caution, ก่อน caution → หลัง danger
- `kaggle-tu-74fa9101` งานออนไลน์ได้เงินวันละ 8000 ไม่ต้องสัมภาษณ์ สมักด่วน — guideline caution, ก่อน caution → หลัง danger
- `kaggle-tu-547e76f4` งานออนไลน์ได้เงินวันละ 8000 ไม่ต้องสัมภาษณ์ สมัครด่วนนน — guideline caution, ก่อน caution → หลัง danger
- `kaggle-tu-cee5f9f6` รุ่นพี่ฝากบอกให้โอนนค่าชีทด่วน ไม่งั้นหมดสิทธิ์ — guideline caution, ก่อน caution → หลัง danger

## ดีขึ้น

- `kaggle-tu-590a29c2` ขอโอนเต็มก่อน เด๋วส่งเลขพัสดุให้ — guideline caution, ก่อน safe → หลัง caution
- `kaggle-tu-6a0e2a96` งานออนไลน์ได้เงินวันละ 3000 ไม่ต้องสัมภาษณ์ สมัครด่วน inbox ได้ — guideline danger, ก่อน caution → หลัง danger
- `kaggle-tu-a97bbac9` งานออนไลน์ได้เงินวันละ 5000 ไม่ต้องสัมภาษณ์ สมัครด่วน inbox ได้ — guideline danger, ก่อน caution → หลัง danger
- `kaggle-tu-983ae243` งานออนไลน์ได้เงินวันละ 8000 ไม่ต้องสัมภาษณ์ สมัครด่วน ทัก DM — guideline danger, ก่อน caution → หลัง danger
- `kaggle-tu-2eef8a84` มีคนจองหลายคน ถ้าเอาโอนมัดจำมาก่อนได้เลย ทัก DM — guideline caution, ก่อน danger → หลัง caution
- `kaggle-tu-11868295` มีคนจองงหลายคน ถ้าเอาโอนมัดจำมาก่อนได้เลย ทัก DM — guideline caution, ก่อน danger → หลัง caution
- `kaggle-tu-57f7514d` มีใครขายชีท SC135 บ้างครับ line: @fakeid — guideline safe, ก่อน danger → หลัง safe
- `kaggle-tu-2ae2fe19` ระบบแจ้งให้ยืนยันข้อมูลบางอย่างภายในวันนี้ — guideline caution, ก่อน safe → หลัง caution
- `kaggle-tu-8d37ea0e` รีบโอนก่อนนะ เหลือคนเดียวแล้ว ทัก DM — guideline caution, ก่อน danger → หลัง caution
- `kaggle-tu-99f13ace` รุ่นพี่ฝากบอกให้โอนค่าชีทด่วนนน ไม่งั้นหมดสิทธิ์ ส่งในกลุ่มได้เลย — guideline danger, ก่อน caution → หลัง danger
- `kaggle-tu-43fd054d` รุ่นพี่ฝากบอกให้โอนค่าชีทด่วน ไม่งั้นหมดสิทธิ์ — guideline danger, ก่อน caution → หลัง danger
- `kaggle-tu-59a4e0aa` ร้านกาแฟแถวรังสิตรับพาร์ทไทม์ ชั่วโมงละ 70 บาท มีสัมภาษณ์หน้าร้าน ส่งใ — guideline safe, ก่อน caution → หลัง safe
- `kaggle-tu-3e6f3d5e` ร้านกาแฟแถวรังสิตรับพาร์ทไทม์ ชั่วโมงละ 60 บาท มีสัมภาษณ์หน้าร้าน ทัก  — guideline safe, ก่อน caution → หลัง safe
- `kaggle-tu-cc6056fe` ร้านกาแฟแถวรังสิตรับพาร์ทไทม์ ชั่วโมงละ 80 บาท มีสัมภาษณ์หน้าร้าน inbo — guideline safe, ก่อน caution → หลัง safe
- `kaggle-tu-17d4cf70` แอดมินคณะขอค่าจองงสิทธิ์สอบ โอนมาที่ พร้อมเพย์ 08x-xxx-xxxx ภายในวันนี — guideline danger, ก่อน caution → หลัง danger
- `kaggle-tu-b554c5e9` แอดมินคณะขอค่าจองสิทธิ์สอบ โอนนมาที่ xxx-x-xxxxx-x ภายในวันนี้ — guideline danger, ก่อน caution → หลัง danger
- `kaggle-tu-22b55ec6` แอดมินคณะขอค่าจองสิทธิ์สอบ โอนมาที่ xxx-x-xxxxx-x ภายในวันนี้ — guideline danger, ก่อน caution → หลัง danger
- `kaggle-tu-18cce6a2` แอดมินคณะขอค่าจองสิทธิ์สอบ โอนนมาที่ พร้อมเพย์ 08x-xxx-xxxx ภายในวันนี — guideline danger, ก่อน caution → หลัง danger
- `kaggle-tu-2d310f04` แอดมินคณะขอค่าจองสิทธิ์สอบ โอนมาที่ บัญชี xxx123 ภายในวันนี้ — guideline danger, ก่อน caution → หลัง danger
- `kaggle-tu-1cbfeb8a` ไม่สะดวกนัดรับ ขอส่งอย่างเดียว โอนก่อนส่งนะะะ ทัก DM — guideline caution, ก่อน danger → หลัง caution
- `kaggle-tu-ac5920d7` ไม่สะดวกนัดรับ ขอส่งอย่างเดียว โอนก่อนส่งนะ ทัก DM — guideline caution, ก่อน danger → หลัง caution

## กลุ่มที่ยังผิด (นับ)

{'inbound_payment_account_request': 2, 'recipient_account_as_credential': 2, 'payment_direction_misread': 1, 'marketplace_pay_first_unverified': 1, 'unrealistic_offer_no_request_channel': 4, 'channel_shift_only_directive_misread': 1, 'income_offer_without_contact_channel': 1, 'narrative_report_not_request': 1, 'link_mention_no_url_hedged': 3, 'seller_urgency_only_caution_not_danger': 1, 'kaggle_keyword_overtrigger_urgency_money': 1}