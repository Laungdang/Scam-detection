"""
System vs guideline calibration set — ระบบ Q&A (lexicon + Claude, ไม่มี blacklist/DB) ตอบตรง §8 ของ
ANNOTATION_GUIDELINE กี่แถว — ใช้เป็น regression test ของ prompt ทุกครั้งที่ guideline/prompt เปลี่ยน

รัน: python -m ml.guideline_eval [--workers 4] [--out data/processed/guideline_eval.jsonl]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import warnings
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

warnings.filterwarnings("ignore")
os.environ.setdefault("PII_SALT", "eval")

GUIDE = Path("data/ANNOTATION_GUIDELINE.md")


def load_calibration() -> list[dict]:
    rows = []
    text = GUIDE.read_text(encoding="utf-8")
    start = text.index("## 8.")
    for line in text[start:].splitlines():
        m = re.match(r"^\| (C\d+[a-z]?) \| (.+?) \| (.+?) \| (.+?) \|$", line)
        if not m:
            continue
        verdict_cell = m.group(3)
        v = re.match(r"(safe|caution|danger)", verdict_cell).group(1)
        ni = re.findall(r"\[(.*?)\]", verdict_cell)
        needs = [x.strip() for x in ni[0].split(",")] if ni else []
        rows.append({"id": m.group(1), "text": m.group(2).strip(), "verdict": v, "needs_info": needs})
    return rows


def run_one(row: dict) -> dict:
    from app.engines.qa_engine import should_use_rag
    from app.evidence.pattern_evidence import PatternEvidence
    from app.services.ai_service import analyze_with_ai
    from app.services.pattern_service import scan_text

    ev = PatternEvidence(dimensions=scan_text(row["text"]))
    rag = should_use_rag("text", ev, False)
    r = analyze_with_ai(
        original_input=row["text"], input_type="text", matched_pattern_names=ev.matched_pattern_names,
        blacklist_found=False, pattern_evidence_text=ev.to_evidence_text(),
        history_evidence_text="ประวัติการสนทนา: ไม่มี (เป็น turn แรก)", skip_rag=not rag,
    )
    s = r.get("structured") or {}
    got = s.get("verdict") if s.get("response_type", "analysis") == "analysis" else s.get("response_type")
    return {**row, "system_verdict": got, "system_needs_info": s.get("needs_info") or [], "watch_for": s.get("watch_for"),
            "category": s.get("category"), "follow_up": s.get("follow_up"), "rag": rag, "ok": bool(r.get("success"))}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--out", default="data/processed/guideline_eval.jsonl")
    args = ap.parse_args()
    rows = load_calibration()
    print(f"calibration rows: {len(rows)}", flush=True)
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        results = list(ex.map(run_one, rows))
    Path(args.out).write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in results) + "\n", encoding="utf-8")
    ok = [r for r in results if r["ok"]]
    agree = sum(1 for r in ok if r["system_verdict"] == r["verdict"])
    ni_ok = sum(1 for r in ok if r["verdict"] == "caution" and set(r["system_needs_info"]) & set(r["needs_info"]))
    n_c = sum(1 for r in ok if r["verdict"] == "caution")
    print(f"\nverdict agree: {agree}/{len(ok)} = {agree / len(ok):.0%} | caution rows with ≥1 matching needs_info: {ni_ok}/{n_c}")
    print("\nMISMATCH:")
    for r in ok:
        if r["system_verdict"] != r["verdict"]:
            print(f"  {r['id']:<5} guideline={r['verdict']:<8} system={str(r['system_verdict']):<8} | {r['text'][:55]}")
    sys.stdout.flush()
    os._exit(0)


if __name__ == "__main__":
    main()
