"""
Inter-annotator agreement — Cohen's κ ระหว่าง annotator 2 คน (CLAUDE.md 10.4, ANNOTATION_GUIDELINE §5)

input: jsonl ที่แต่ละแถวมี {"id", "annotator", "verdict", "category"(optional)} — เช่น
       data/processed/kaggle_tu_human_adjudication.jsonl (A1) + ไฟล์คำตอบ A2 รูปแบบเดียวกัน
output: κ (verdict), κ (category ถ้ามี), confusion table, รายการที่ไม่ตรง (ให้คนที่ 3 ตัดสิน)

รัน: python -m ml.annotation.agreement --a data/processed/kaggle_tu_human_adjudication.jsonl --b data/processed/a2_answers.jsonl
     python -m ml.annotation.agreement --demo   # ตัวอย่างคำนวณ
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


def cohen_kappa(pairs: list[tuple[str, str]]) -> float:
    """κ = (p_o - p_e) / (1 - p_e); คืน 1.0 ถ้า p_e == 1 (ทุกคนตอบค่าเดียวกันหมด)"""
    n = len(pairs)
    if n == 0:
        return float("nan")
    po = sum(1 for a, b in pairs if a == b) / n
    ca = Counter(a for a, _ in pairs)
    cb = Counter(b for _, b in pairs)
    pe = sum(ca[k] * cb[k] for k in set(ca) | set(cb)) / (n * n)
    if pe >= 1.0:
        return 1.0
    return (po - pe) / (1 - pe)


def interpret(k: float) -> str:
    # Landis & Koch (1977)
    if k != k:
        return "n/a"
    if k < 0:
        return "poor"
    if k < 0.2:
        return "slight"
    if k < 0.4:
        return "fair"
    if k < 0.6:
        return "moderate"
    if k < 0.8:
        return "substantial"
    return "almost perfect"


def load(path: Path) -> dict[str, dict]:
    """รองรับ jsonl (id, verdict, category, needs_info) และ csv blind sheet (คอลัมน์ชื่อเดียวกัน)"""
    if path.suffix.lower() == ".csv":
        import csv

        out: dict[str, dict] = {}
        with path.open(encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                v = (row.get("verdict") or "").strip().lower()
                if not v:
                    continue  # ยังไม่กรอก — ข้าม (จะนับเฉพาะแถวที่ทั้งคู่ตอบ)
                cat = (row.get("category") or "").strip().lower() or None
                ni = [x.strip() for x in (row.get("needs_info") or "").replace(",", ";").split(";") if x.strip()]
                out[row["id"]] = {"id": row["id"], "verdict": v, "category": cat, "needs_info": ni, "notes": row.get("notes")}
        return out
    rows = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    return {r["id"]: r for r in rows}


def compare(a: dict[str, dict], b: dict[str, dict], field: str) -> tuple[list[tuple[str, str]], list[str]]:
    ids = sorted(set(a) & set(b))
    pairs = [(a[i].get(field), b[i].get(field)) for i in ids if a[i].get(field) is not None and b[i].get(field) is not None]
    disagree = [i for i in ids if a[i].get(field) != b[i].get(field)]
    return pairs, disagree


def report(a: dict[str, dict], b: dict[str, dict], name_a: str, name_b: str) -> None:
    for field in ("verdict", "category"):
        pairs, disagree = compare(a, b, field)
        if not pairs:
            continue
        k = cohen_kappa(pairs)
        print(f"\n=== {field}: n={len(pairs)} | agreement={sum(1 for x, y in pairs if x == y) / len(pairs):.1%} | κ={k:.3f} ({interpret(k)}) | target ≥ 0.7 ===")
        labels = sorted(set(x for p in pairs for x in p))
        print(f"{'':>10}" + "".join(f"{l:>10}" for l in labels) + f"   ← {name_b}")
        for la in labels:
            row = Counter(y for x, y in pairs if x == la)
            print(f"{la:>10}" + "".join(f"{row[lb]:>10}" for lb in labels))
        print(f"   ↑ {name_a}")
        if disagree:
            print(f"\nไม่ตรงกัน ({len(disagree)}) → คนที่ 3 ตัดสิน:")
            for i in disagree:
                print(f"  {i}: {name_a}={a[i].get(field)} | {name_b}={b[i].get(field)}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--a", help="jsonl ของ annotator 1")
    ap.add_argument("--b", help="jsonl ของ annotator 2")
    ap.add_argument("--demo", action="store_true")
    args = ap.parse_args()

    if args.demo:
        a = {f"x{i}": {"verdict": v} for i, v in enumerate("safe safe caution danger danger caution safe danger".split())}
        b = {f"x{i}": {"verdict": v} for i, v in enumerate("safe caution caution danger danger caution safe caution".split())}
        report(a, b, "A1", "A2")
        return 0
    if not (args.a and args.b):
        ap.error("ต้องระบุ --a และ --b (หรือ --demo)")
    a, b = load(Path(args.a)), load(Path(args.b))
    print(f"A1 {len(a)} records | A2 {len(b)} records | ร่วมกัน {len(set(a) & set(b))}")
    report(a, b, "A1", "A2")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
