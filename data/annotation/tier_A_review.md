# Tier A — ข้อความ scam ภาษาไทย "ของจริง" ทั้ง 80 (จาก data/raw/scam_corpus.jsonl)

ทุกแถวมี URL ต้นทางเปิดดูได้ · label ตอนนี้เป็น weak label จาก source (ยังไม่ผ่าน annotator 2 คน)

## IMC 2025 Smishing Dataset (Fishing for Smishing) — 65 ข้อความ

แหล่ง: https://github.com/reportsmishing/Smishing-Dataset-IMC25

| id | ข้อความ | label เดิม | หมายเหตุจาก source |
|---|---|---|---|
| `imc25-5f6a51e2` | คืนเงินประกันการใช้งานไฟฟ้าส่วนภูมิภาค... | danger / other | imc25_scam_type=spam; lure=need and greed |
| `imc25-ea6f00dd` | กสิกรไทย ยกเลิกส่ง SMS แบบลิงก์ เพิ่มความปลอดภัย มีผลตั้งแต่วันนี้ | danger / other | imc25_scam_type=others; lure=distraction,time/urgency |
| `imc25-1f627798` | กรรมธรรม์ T303XXX161 เปลี่ยนสถานะเป็นกู้ชำระเบี้ยอัตโนมัติเนื่องจากไม่ได้ชำระเบี้ยงวดวันที่ 01 พฤศจิกายน 2565 ซึ่งจะมีการคิดดอกเบี้ยตามเงื่อนไขกรมธรรม์ ขอภัยหากชำระแล้ว | danger / other | imc25_scam_type=government; lure=authority,time/urgency |
| `imc25-416f8783` | มีผู้เข้าระบบธนาคารของคุณจากอุปกรณ์อื่น หากไม่ได้ดำเนินการด้วยตนเอง โปรดติดต่อต่อนที | danger / phishing_link | imc25_scam_type=banking; lure=authority,time/urgency |
| `imc25-a542e3d2` | ฝากครั้งแรก 300 บาท รับ 599 บาท คลิก <URL> รับ 1599 บาท | danger / other | imc25_scam_type=spam; lure=need and greed; network=AIS |
| `imc25-fe2235e4` | Lion Air สวัสดีค่ะ ขอบคุณลูกค้าที่ใช้บริการอย่างต่อเนื่อง ทางเราขอม่อมดูป้องกันเที่ยวบินฟรีให้กับคุณ1ใบ | danger / other | imc25_scam_type=spam; lure=need and greed; network=AIS |
| `imc25-6e5e3053` | คุณได้รับการอนุมัตสินเชื่อแล้ว ติดต่อ:<URL> | danger / other | imc25_scam_type=others; lure=authority,time/urgency |
| `imc25-c36dbc8f` | กฟภ.-PEA ตามมาตรการเร่งด่วนเพื่อช่วยเหลือประชาชน ดูแลปัญหาภัยแล้ง กฟภ. จะคืนเงินประกันการใช้ไฟฟ้า ... | danger / other | imc25_scam_type=government; lure=authority,time/urgency; net |
| `imc25-3c6f17aa` | ลงทะเบียนเพื่อขอคืนภาษี | danger / other | imc25_scam_type=spam; lure=need and greed |
| `imc25-6ed93d56` | มีผู้เข้าถึงระบบธนาคารของคุณจากอุปกรณ์นี้ หากไม่ได้ดำเนินการด้วยตนเอง โปรดติดต่อทันที | danger / phishing_link | imc25_scam_type=delivery; lure=distraction,time/urgency |
| `imc25-f2bfdc68` | คุณสามารถถอนได้ 35000 บาทจากทางเรา คลิก <URL> | danger / other | imc25_scam_type=government; lure=authority,need and greed |
| `imc25-fc61f66a` | คุณได้รับการอนุมัติเชื่อแล้ว ติดต่อ : <URL> | danger / phishing_link | imc25_scam_type=banking; lure=authority,time/urgency |
| `imc25-3698a5e7` | citi แจ้งเตือนเพื่อความปลอดภัย: บัตรของท่านที่ซื้าทำด้วย 8253 มีรายการถอนมาจาก DENHARD'S MARKET <LOCATION> CA จำนวน <LOCATION> 0.00 วันที่ <DATE_TIME> ขณะนี้บัตรของท่าน ได้ถูกระงับชั่วคราวเพื่อความปลอดภัย หากท่านเป็นผู้ทำรายการดังกล่าว กรุณาพิมพ์ Y เพื่อยืนยัน หรือพิมพ์ N เพื่อปฏิเสธ ส่งไปที่ <DATE_TIME> อาจเสี่ยงที่จะใช้จ่ายเพิ่มเติมตามเงื่อนไขของเครือข่าย | danger / phishing_link | imc25_scam_type=banking; lure=authority,time/urgency |
| `imc25-7fee0b25` | คืนเงินประกันการใช้ไฟฟ้าส่วนภูมิภาค... | danger / other | imc25_scam_type=spam; lure=need and greed |
| `imc25-e3b89c1a` | กสิกรไทย ยกเลิกส่ง SMS แบ่งลิงก์ เพิ่มความปลอดภัย มีผลตั้งแต่วันนี้ | danger / other | imc25_scam_type=others; lure=distraction,time/urgency |
| `imc25-d97308f3` | กรมธรรม์ T303XXX161 เปลี่ยนสถานะเป็นกู้ชำระเบี้ยอัตโนมัติเนื่องจากไม่ได้ชำระเบี้ยนววันที่ 01 พฤศจิกายน 2565 ซึ่งจะมีการคิดดอกเบี้ยตามเงื่อนไข กรมธรรม์ ขอภัยหากชำระแล้ว หรือปรึกษา <PHONE_NUMBER> ชำระเบี้ยคลิก | danger / other | imc25_scam_type=government; lure=authority,time/urgency |
| `imc25-a2edb262` | มีผู้เข้าสู่ระบบธนาคารของคุณจากอุปกรณ์อื่น หากไม่ได้ดำเนินการด้วยตนเอง โปรดติดต่อต้นทาง <URL> | danger / phishing_link | imc25_scam_type=banking; lure=authority,time/urgency |
| `imc25-29f3d96c` | Lion Air สวัสดีค่ะ ขอบคุณคุณลูกค้าที่ใช้บริการอย่างต่อเนื่อง ทางเราขออมับคุบองเที่ยวบินฟรีให้กับคุณ1ใบ | danger / other | imc25_scam_type=spam; lure=need and greed; network=AIS |
| `imc25-f36df3ea` | กรฟภ-PEA ตามมาตรการเร่งด่วนเพื่อช่วยเหลือประชาชน ดูแลปัญหาภัยแล้ง กฟภ. จะคืนเงินประกันการใช้ไฟฟ้า ... | danger / other | imc25_scam_type=government; lure=authority,time/urgency; net |
| `imc25-851bc402` | ลงทะเบียเพื่อขอคืนภาษี | danger / other | imc25_scam_type=spam; lure=need and greed |
| `imc25-e8a2d747` | มีผู้เข้าถึงระบบธนาคารของคุณจากอุปกรณ์อื่น หากไม่ได้ดำเนินการด้วยตนเอง โปรดติดต่อนั้นที่ | danger / phishing_link | imc25_scam_type=delivery; lure=distraction,time/urgency |
| `imc25-1aea233d` | คุณได้รับการอนุมัติสินเชื่อแล้ว ติดต่อ: <URL> | danger / phishing_link | imc25_scam_type=banking; lure=authority,time/urgency |
| `imc25-3628ca9f` | Citi แจ้งเตือนเพื่อความปลอดภัย: บัตรของท่านที่ชำระด้วย 8253 มีรายการชำระเงินจาก DENHARD'S MARKET <LOCATION> CA จำนวน <LOCATION> 0.00 วันที่ <DATE_TIME> ขณะนี้บัตรของท่าน ได้ถูกระงับชั่วคราวเพื่อความปลอดภัย หากท่านเป็นผู้ทำรายการดังกล่าว กรุณาพิมพ์ Y เพื่อยืนยัน หรือพิมพ์ N เพื่อปฏิเสธ ส่งไปที่ <US_BANK_NUMBER> อาจเสียค่าใช้จ่ายเพิ่มเติม ตามเงื่อนไขของเครือข่าย | danger / phishing_link | imc25_scam_type=banking; lure=authority,time/urgency |
| `imc25-f66b9a0d` | กรมสรรพากรแจ้ง <LOCATION> ไม่สำเร็จคลิกเพื่อตรวจสอบรายละเอียด | danger / other | imc25_scam_type=spam; lure=authority,distraction,need and gr |
| `imc25-9221598c` | ประกาศการอัปเกรดSCBโปรดอัปเดตหินที่ <URL> | danger / phishing_link | imc25_scam_type=banking; lure=authority,distraction |
| `imc25-80851de0` | ธนาคารไทยพาณิชย์แจ้งการอัปเกรด โปรดอัปเกรดทันที <URL> | danger / phishing_link | imc25_scam_type=banking; lure=authority,time/urgency |
| `imc25-f28aac69` | *S C B* อัปเดตออนไลน์โปรดดำเนินการทันที | danger / phishing_link | imc25_scam_type=banking; lure=authority,distraction |
| `imc25-b9df7edf` | ธนาคารไทยพาณิชย์แจ้งการอัปเกรดโปรดอัปเกรดทันที | danger / phishing_link | imc25_scam_type=banking; lure=distraction,time/urgency |
| `imc25-fbbf3cc8` | [ธ.กรุงไทย] ยินดีด้วยค่ะ คุณได้ <NRP> ,LINE : | danger / phishing_link | imc25_scam_type=banking; lure=authority,need and greed,time/ |
| `imc25-1cd12c21` | [ธ.กรุงเทพ] ยินดีด้วยค่ะ คุณได้ <NRP> ,LINE : | danger / phishing_link | imc25_scam_type=banking; lure=need and greed,time/urgency |
| `imc25-e9ff6e31` | อัปเกรดระบบ BBL โโปรดอัปเดตทันที | danger / phishing_link | imc25_scam_type=banking; lure=authority |
| `imc25-ed0d2813` | อัพเกรดระบบ BBL โปรลดอัปเดตทันที | danger / phishing_link | imc25_scam_type=banking; lure=authority,distraction |
| `imc25-f4f982ad` | อัพเดตระบ BBL โปรแกรมออนไลน์ตอนนี้ | danger / phishing_link | imc25_scam_type=banking; lure=authority,time/urgency |
| `imc25-96c28d2f` | อันนี้ไม่แน่ใจ ผมว่าหมายเลขบัตรเครดิตทุกวันนี้ entropy มันต่ำมาก
หมายเลข 16 หลัก ใช้งานได้จริงประมาณ 8-10 หลักเท่านั้น (6 หลักแรกถูกกันไว้สำหรับหน่วยงานออกบัตรประเภทต่างๆ) หมายเลข CVV อีก 3 หลัก เดือน/ปี หมดอายุนี้ความเป็นไปได้ไม่ค่อยสูงแบบ
บัตรแต่ธนาคารออกกับมีมิ้นไป ถ้าเจอ birthday attack มันไม่ได้ยาก (สุ่มแสน หนึ่งแสน) ไม่แน่ใจว่าหากกระบวนการออกบัตรในหลักอื่นที่เหลือไม่ได้สูงจริง (บอกผมเจอลำใกล้กัน) มันไม่แน่ใจว่าเป็น running number หรือซุ่มแต่แบ๊บเบี้ย) อันนี้จะเหลือ entropy | danger / phishing_link | imc25_scam_type=banking; lure=authority,dishonesty,distracti |
| `imc25-8bc01a43` | สวัสดีค่ะ ศูนย์บริการลูกค้า citibank ยินดีให้บริการ ค่ะ
ขอทราบข้อมูล ชื่อ - นามสกุล ...เบอร์มือถือ ... | danger / phishing_link | imc25_scam_type=banking; lure=authority,need and greed,time/ |
| `imc25-568e4f3e` | เรียนลูกค้า BBL ที่เคารพ ระบบล่่าสุดกรุณา อัปเดตทันที | danger / phishing_link | imc25_scam_type=banking; lure=authority,distraction,time/urg |
| `imc25-4dc15736` | ALERT! บัตร x ของท่านถูกระบุต้องสงสัยในการใช้จ่ายผ่านอินเทอร์เน็ต ช่วยคราว เนื่องจากพบข้อมูลที่น่าสงสัยจำนวน 2 รายการ รายการใช้งานล่าสุด NOK 0.00 (Declined)@ GANESHAYOGA JULIA FOLK,<LOCATION> <DATE_TIME> 18:58 กรุณายืนยันความถูกต้องผ่าน | danger / phishing_link | imc25_scam_type=banking; lure=authority,distraction,time/urg |
| `imc25-0c16283e` | ธนาคารส่ง SMS ที่แนบลิงก์ไปยังเว็บไซต์ปลอม เพื่อหลอกขอข้อมูลส่วนตัวของลูกค้าที่เช่น เลขที่บัตรเครดิต, รหัสบัตร ATM, Password ซึ่งมีลูกค้าของหลายธนาคารได้ตกเป็นเหยื่อของมิจฉาชีพโดยการเปิดเผยข้อมูลส่วนตัวจนเกิดความเสียหายมาแล้ว ธนาคารกสิกรไทย ขอนำว่า อย่าหลงเชื่อคลิกลิงก์หรือกรอกข้อมูลใด ๆ เนื่องจากธนาคารไม่มีนโยบายส่งลิงก์เพื่อให้ลูกค้ารอกข้อมูลส่วนตัว | danger / phishing_link | imc25_scam_type=banking; lure=distraction,need and greed,tim |
| `imc25-136c15da` | ประกาศการอัปเกรดธนาคารกสิกรไทย โปรดดูรายละเอียดที่ | danger / other | imc25_scam_type=government; lure=authority,distraction |
| `imc25-3020f3df` | คุณมีเงิน1,000บาทสามารถรับได้ | danger / other | imc25_scam_type=others; lure=need and greed |
| `imc25-f0afe5e9` | อัพเกรดระบบธนาคารกรุงเทพอัพเกรดทันที | danger / other | imc25_scam_type=others; lure=distraction |
| `imc25-2cbe80fd` | <LOCATION> โปรดอัพเกรดเดียวนี้ | danger / other | imc25_scam_type=others; lure=need and greed |
| `imc25-e77e2b9c` | รับเงิน 1000 บาทของคุณ เร็ว ๆ ใกล้จะหมดอายุแล้ว | danger / other | imc25_scam_type=others; lure=need and greed,time/urgency |
| `imc25-a437dad8` | คุณได้รับสินเชื่อจาก ธปท. 70,000 บ. คลิก: https:// | danger / other | imc25_scam_type=others; lure=need and greed,time/urgency |
| `imc25-80021a5d` | คุณถูกกรรางวัลจับฉลากประจำเดือนของเรา รับสิทธิ์ได้ที่นี่: | danger / other | imc25_scam_type=others; lure=need and greed,time/urgency |
| `imc25-64da36ec` | ขอบคุณที่ซื้อสินค้ากับเรา eTax Invoice คลิก | danger / other | imc25_scam_type=others |
| `imc25-1fbdb78b` | สวัสดี <NAMED_ENTITY> 3,000 บาทด้วยมือถือ แล้วเงินเดือนออกวันเดียวกัน... | danger / other | imc25_scam_type=others; lure=need and greed,time/urgency |
| `imc25-c6f28ecc` | คุณได้รับเงินกู้ 200,000 เข้าสู่ระบบเพื่อรับเงินค่ะ LINE: <URL> | danger / other | imc25_scam_type=others; lure=need and greed,time/urgency |
| `imc25-3c22c029` | คุณได้รับสิทธิ์สินเชื่อฉุกเฉิน50,000 บาท คลิก: <URL> | danger / other | imc25_scam_type=others; lure=need and greed,time/urgency |
| `imc25-bbe1a4da` | ร้านค้า Shopee รับสมัครพนักงานพาร์ทไทม์ เพื่อเพิ่มปริมาณยอดซื้อของร้านค้า Shopee มีเพียงแค่โทรศัพท์มือถือก็สามารถสร้างรายได้ 500-6000 บาทต่อวัน หนึ่งเดือนคุณสามารถรับรายได้ 80,000 บาท และค่าคอมมิชชั่นจะถูกคิดให้ต่อวันค่ะ เพื่อน ๆ ที่ต้องการสร้างรายได้อย่างรวดเร็วให้เพิ่ม LINE ของผู้จัดการ อายุรายได้เร็วและทักผู้จัดการ

เบอร์มือถือ LINE: <PHONE_NUMBER>
ID: <LOCATION> | danger / other | imc25_scam_type=others; lure=authority,need and greed |
| `imc25-472a557f` | คุณถูกการ์ดจับรางวัลประจำเดือนของเรา : <URL> | danger / other | imc25_scam_type=others; lure=need and greed,time/urgency |
| `imc25-661833df` | คุณสามารถรับ220,000 บาทจากทางเรา คลิก: | danger / other | imc25_scam_type=others; lure=need and greed,time/urgency |
| `imc25-1a0e2976` | ขอแสดงความยินดีท่านได้รับโบนัส 39999บาท มีผลภายใน 24 ชม | danger / other | imc25_scam_type=others; lure=need and greed,time/urgency |
| `imc25-875c66ee` | ขอแสดงความยินดี! เราต้องการขอคุณที่ ใช้ผลิตภัณฑ์ของเรามาช่วยขานาน! | danger / other | imc25_scam_type=others; lure=need and greed,time/urgency |
| `imc25-b7c47efb` | โปรดอย่าแชร์รหัส WhatsApp Business ของคุณ: | danger / other | imc25_scam_type=others; lure=authority |
| `imc25-b2dcb76a` | คุณถูกจับรางวัลประจำเดือนของเรา : | danger / other | imc25_scam_type=others |
| `imc25-f99d1ef8` | <URL> shopee รับสมัครพนักงาน OCKkHY2WbVxgz | danger / other | imc25_scam_type=others; lure=herd,need and greed; network=AI |
| `imc25-d4a5bcad` | บริษัท central ฝ่ายธุรกิจของ Shopee เปิดโอกาสให้คนที่กำลังหางานพาร์ทไทม์ online ทำงานง่ายได้จริง ทำงานที่บ้านได้ อย่างสบายๆ รายได้เบื้องต้น 500-2,000 บาทต่อวัน บริษัทถูกต้องตามกฎหมาย 100% รองรับทำงานเป็นทีมรายได้ตามราย ไม้กระทบงานประจำที่ทำอยู่ เงินเดือนคิดในวันต่อวัน ✔เริ่มง่ายทำงาน ได้เลยจะได้รายได้ง่ายสูงสุด 5,000-10,000 วัน ต้องการอายุ : 23 ถึง 50 ปี หากสนใจติดต่อได้ที่ .. เบอร์โทรศัพท์ : <UK_NHS> ไลน์ Line ID : <US_DRIVER_LICENSE> | danger / other | imc25_scam_type=others; lure=need and greed,time/urgency |
| `imc25-25f6e321` | ยินดีด้วยค่ะ! คุณได้สิทธิ์เติมน้ำมันฟรี 1,500 กด | danger / other | imc25_scam_type=others; lure=need and greed |
| `imc25-67628691` | เงินเดือน1000บาทโอนเข้าบัญชีเรียบร้อย <URL> | danger / other | imc25_scam_type=spam; lure=need and greed,time/urgency |
| `imc25-830fc61c` | คุณได้รับสินเชื่อจาก ธป. <DATE_TIME> | danger / other | imc25_scam_type=spam; lure=need and greed,time/urgency |
| `imc25-3355b656` | สวัสดีค่ะ เราติดต่อมาจากบริษัทสินเชื่อที่โทรหาคุณเมื่อสักครู่นี้ | danger / other | imc25_scam_type=spam; lure=herd,need and greed |
| `imc25-a51fe312` | คุณได้รับ โครงการสินเชื่อช่วยเหลือ 30,000 จาก Chayo group สนใจคลิก | danger / other | imc25_scam_type=spam; lure=need and greed |
| `imc25-feaad8de` | ยินดีด้วยคุณ ได้รับวงเงิน จาก( TTB ) 250,000 ค... | danger / other | imc25_scam_type=spam; lure=need and greed |
| `imc25-abb67c9f` | รับฟรี 22 coins และสมัคร dtac Safe ป้องกันคุณจากเว็บหลอกลวง คลิกเลย | danger / other | imc25_scam_type=telecom; lure=authority,distraction |

## Ngern Tid Lor (financial education content) — 5 ข้อความ

แหล่ง: https://www.tidlor.com/th/article/lifestyle/general/how-to-avoid-phishing-scams

| id | ข้อความ | label เดิม | หมายเหตุจาก source |
|---|---|---|---|
| `tidlor-ce5e4ad5` | คุณเป็นผู้โชคดีได้รับวงเงินกู้จากธนาคารแห่งประเทศไทย (ธปท.) 200,000 บาท | danger / loan_offer |  |
| `tidlor-3a95632c` | เงินของคุณถูกถอนออกไปจากบัญชี 50,000 บาท | danger / financial_fraud |  |
| `tidlor-0c0432a3` | คุณมียอดใช้ผ่านบัตรเครดิต 100,000 บาท | danger / financial_fraud |  |
| `tidlor-c52f3962` | ยินดีด้วย! คุณคือผู้โชคดีได้รับเงินกู้สินเชื่อโควิดแบบฟรี ๆ 40,000 บาท คลิกลิงก์เพื่อกรอกข้อมูลเลย | danger / loan_offer |  |
| `tidlor-9f145719` | บัตรเครดิตของคุณกำลังจะถูกโจรกรรม รีบกรอกข้อมูลยืนยันตัวตนผ่านลิงก์เพื่ออายัด | danger / phishing_link |  |

## Police Region 9 (Thai Royal Police) — 4 ข้อความ

แหล่ง: https://www.police9.go.th/ระวังภัย-sms-มิจฉาชีพ-กับกล/

| id | ข้อความ | label เดิม | หมายเหตุจาก source |
|---|---|---|---|
| `police9-a0255547` | บัญชีของคุณถูกระงับการใช้งาน กรุณาคลิกลิงก์เพื่อยืนยันตัวตน | danger / phishing_link |  |
| `police9-fd1b0245` | คุณมีคดีความ กรุณาคลิกลิงก์เพื่อตรวจสอบรายละเอียด | danger / impersonation_authority |  |
| `police9-c9064f94` | รับเงินคืน ค่าไฟฟ้า กรุณาคลิกลิงก์เพื่อตรวจสอบรายละเอียด | danger / impersonation_authority |  |
| `police9-0ae26c66` | คุณได้รับรางวัล iPhone 14 กรุณาคลิกลิงก์เพื่อรับรางวัล | danger / prize_scam |  |

## Anti Fake News Center Thailand (DES Ministry) — 3 ข้อความ

แหล่ง: https://www.antifakenewscenter.com/คลังความรู้/รวมข้อความ-sms-ที่มิจฉาชีพมักแนบลิงก์หลอกเหยื่อ/

| id | ข้อความ | label เดิม | หมายเหตุจาก source |
|---|---|---|---|
| `afnc-8a9b47a9` | ธนาคารปรับปรุงระบบ โปรดอัปเดตข้อมูลตามลิงก์ | danger / phishing_link |  |
| `afnc-aa279aca` | ยังไม่ชำระค่าบริการ | danger / financial_fraud |  |
| `afnc-6e93e97e` | บัญชีเงินฝากโดนแฮก | danger / phishing_link |  |

## Bangkok Biznews — 8 มุกยอดฮิตมิจฉาชีพ — 3 ข้อความ

แหล่ง: https://www.bangkokbiznews.com/business/962824

| id | ข้อความ | label เดิม | หมายเหตุจาก source |
|---|---|---|---|
| `bbn-422c243b` | เงินเดือน 2,000 บาท โอนเข้าบัญชีเรียบร้อย | danger / financial_fraud |  |
| `bbn-f36025e5` | ยินดีด้วยคุณได้รับเงินรางวัล 20,000 บาท | danger / prize_scam |  |
| `bbn-f50ee7ac` | โครงการเราชนะ ลงทะเบียนเพิ่มข้อมูลที่ลิงก์ | danger / impersonation_authority |  |
