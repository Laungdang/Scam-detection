"""
นำผล human review จาก CSV กลับเข้า corpus — ตั้ง review.status ให้ record tier C

CSV (จาก data/annotation/kaggle_tu_safe_review.csv): คอลัมน์ id, text, ..., "NOT_SAFE (ใส่ x ถ้าไม่ปกติ)", note
- แถวที่ NOT_SAFE ว่าง  → review.status = approved  (คนยืนยันว่าเป็นข้อความปกติจริง → ใช้ train ได้, ยังเป็น tier C)
- แถวที่ NOT_SAFE = x   → review.status = rejected  (ไม่ใช้) + note เก็บไว้
ทุกแถวบันทึก reviewer, reviewed_at, guideline_version

หมายเหตุ (CLAUDE.md 10.2): tier C approved ใช้ได้เฉพาะ train — ไม่เข้า val/test/RAG; ไม่เปลี่ยนเป็น tier S เพราะเป็น synthetic

รัน: python -m ml.scrape.apply_review_csv --csv data/annotation/kaggle_tu_safe_review.csv --reviewer A1 [--dry-run]
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

CORPUS = Path("data/raw/scam_corpus.jsonl")
GUIDELINE_VERSION = "1.3"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True)
    ap.add_argument("--reviewer", required=True, help="เช่น A1")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    decisions: dict[str, tuple[str, str]] = {}
    with open(args.csv, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        flag_col = next(c for c in reader.fieldnames if c.startswith("NOT_SAFE"))
        for row in reader:
            flag = (row.get(flag_col) or "").strip().lower()
            status = "rejected" if flag in ("x", "✓", "1", "yes", "y") else "approved"
            decisions[row["id"]] = (status, (row.get("note") or "").strip())

    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    records = [json.loads(l) for l in CORPUS.read_text(encoding="utf-8").splitlines() if l.strip()]
    applied = Counter()
    for r in records:
        if r["id"] in decisions and r.get("tier") == "C":
            status, note = decisions[r["id"]]
            r["review"] = {"status": status, "reviewer": args.reviewer, "reviewed_at": ts, "notes": note or None}
            r.setdefault("annotation", {})["guideline_version"] = GUIDELINE_VERSION
            applied[status] += 1
    print(f"decisions in csv: {len(decisions)} | applied: {dict(applied)} | not found in corpus: {len(decisions) - sum(applied.values())}")
    if args.dry_run:
        print("(dry-run)")
        return 0
    CORPUS.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n", encoding="utf-8")
    print(f"corpus updated → {CORPUS}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
