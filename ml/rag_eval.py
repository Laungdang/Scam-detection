"""
RAG retrieval eval — วัดว่า chroma ดึง "เคสที่ตรงสถานการณ์" มาได้ไหม (hit@k)

ชุดคำถามแบบผู้ใช้จริง + regex ของสิ่งที่ถือว่า "ตรง" (ดูจาก title/body ของเคสที่ดึงมา)
ใช้เปรียบเทียบ embedding model / threshold / การกรอง corpus — รายงานใน thesis ได้

รัน: python -m ml.rag_eval [--k 3] [--no-threshold]
"""

from __future__ import annotations

import argparse
import os
import re
import warnings

warnings.filterwarnings("ignore")
os.environ.setdefault("PII_SALT", "eval")

# (คำถาม, regex ที่ถือว่าเคสตรง, เป็นข้อความปกติหรือไม่)
QUERIES: list[tuple[str, str, bool]] = [
    ("ได้รับ SMS จากกรมการขนส่ง บอกว่ามีใบสั่งค้างชำระ ให้จ่ายที่ลิงก์", r"ขนส่ง|ใบสั่ง|ค่าปรับ", False),
    ("ได้ SMS จากการไฟฟ้า บอกว่าค้างค่าไฟ จะตัดไฟวันนี้ ให้จ่ายที่ลิงก์", r"ไฟฟ้า|ค่าไฟ|มิเตอร์|PEA|MEA", False),
    ("SMS บอกว่าพัสดุตกค้าง ให้กดลิงก์อัปเดตที่อยู่", r"พัสดุ|ไปรษณีย์|Kerry|Flash|ขนส่งพัสดุ", False),
    ("มีคนโทรมาบอกว่าเป็นตำรวจ บอกว่าผมพัวพันคดีฟอกเงิน ให้โอนเงินไปตรวจสอบ", r"ตำรวจ|คดี|ฟอกเงิน|คอลเซ็นเตอร์|call ?center|อ้างเป็นเจ้าหน้าที่", False),
    ("เพื่อนใน Facebook ทักมาชวนลงทุนหุ้น ได้กำไร 20% ต่อเดือน", r"ลงทุน|หุ้น|ผลตอบแทน|เทรด", False),
    ("มีคนอ้างเป็นหลาน บอกเปลี่ยนเบอร์ ขอยืมเงิน 3,000", r"ยืมเงิน|เปลี่ยนเบอร์|อ้างเป็นญาติ|อ้างเป็นลูก|อ้างเป็นหลาน|คนรู้จัก|ฉุกเฉิน|SOS|เสียงคุ้นหู", False),
    ("ซื้อของในเพจ Facebook โอนมัดจำแล้วโดนบล็อก", r"ซื้อของ|สั่งซื้อ|เพจปลอม|ขายของ|มัดจำ|ออเดอร์|โอนแล้ว", False),
    ("SMS จากธนาคาร บอกว่าบัญชีถูกระงับ ให้ยืนยันตัวตนที่ลิงก์", r"ธนาคาร|บัญชี|ระงับ|ยืนยันตัวตน", False),
    ("มีข้อความบอกว่าได้รับเงินดิจิทัล 10,000 จากรัฐบาล ให้กดลิงก์ลงทะเบียน", r"เงินดิจิทัล|10,000|คนละครึ่ง|ลงทะเบียน|รัฐบาล", False),
    ("แอปหาคู่ คุยกันมา 2 เดือน เขาบอกจะส่งของขวัญมาให้ แต่ติดศุลกากร ต้องโอนค่าธรรมเนียม", r"หาคู่|ความรัก|ศุลกากร|ของขวัญ|โรแมนซ์|romance|ตีสนิท", False),
    ("มีคนส่งลิงก์มาบอกว่าเป็นงานพาร์ทไทม์ กดไลค์ได้เงิน", r"งานออนไลน์|พาร์ทไทม์|Part-?time|กดไลค์|แลกไลก์|รับสมัครงาน|รายได้เสริม|รีวิว", False),
    ("ส่งงานด่วนนะครับ พรุ่งนี้เช้าอาจารย์จะตรวจ", r"$^", True),
    ("แม่โอนเงินค่าเทอมให้ด่วนหน่อย พรุ่งนี้วันสุดท้าย", r"$^", True),
    ("ด่วน! Flash Sale ลด 50% วันนี้วันเดียว ที่ Shopee", r"$^", True),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--k", type=int, default=3)
    ap.add_argument("--no-threshold", action="store_true", help="ดูคะแนนดิบทั้งหมด ไม่ตัด threshold")
    args = ap.parse_args()

    from app.services import rag_service
    from app.services.rag_service import retrieve_similar_cases

    if args.no_threshold:
        rag_service.SIMILARITY_THRESHOLD = -1.0

    print(f"model={rag_service.EMBED_MODEL} threshold={rag_service.SIMILARITY_THRESHOLD} k={args.k}")
    hits = 0
    scam_q = 0
    benign_leak = 0
    benign_q = 0
    rel_scores: list[float] = []
    irr_scores: list[float] = []
    for q, pat, benign in QUERIES:
        cases = retrieve_similar_cases(q, top_k=args.k)
        rx = re.compile(pat, re.I)
        matched = [c for c in cases if rx.search(c["input_text"])]
        if benign:
            benign_q += 1
            if cases:
                benign_leak += 1
            status = "LEAK" if cases else "ok  "
        else:
            scam_q += 1
            if matched:
                hits += 1
            status = "HIT " if matched else "MISS"
        for c in cases:
            (rel_scores if rx.search(c["input_text"]) else irr_scores).append(c["similarity"])
        print(f"[{status}] {q[:48]:<48} " + " | ".join(
            f"{c['similarity']:.2f}{'*' if rx.search(c['input_text']) else ' '} {c['input_text'].splitlines()[0][:34]}" for c in cases
        ))
    print(f"\nhit@{args.k} (scam queries): {hits}/{scam_q}")
    print(f"benign queries that still pulled scam cases: {benign_leak}/{benign_q}")
    if rel_scores and irr_scores:
        print(f"similarity — relevant: min {min(rel_scores):.2f} mean {sum(rel_scores)/len(rel_scores):.2f} | "
              f"irrelevant: max {max(irr_scores):.2f} mean {sum(irr_scores)/len(irr_scores):.2f}")
    return 0


if __name__ == "__main__":
    code = main()
    import sys
    sys.stdout.flush()
    # bge-m3/torch worker threads ค้างตอน interpreter shutdown บน Windows → process ไม่จบเอง
    os._exit(code)
