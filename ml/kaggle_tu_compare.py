"""
External comparison: ระบบเรา (lexicon evidence + Claude, ไม่มี blacklist/DB) vs rule-label ของ Kaggle TU dataset

จุดประสงค์ (thesis): rule-label ("มีคำเร่ง/เงิน/ลิงก์ → suspicious") กับ evidence-based verdict ต่างกันตรงไหน
ไม่ใช่การวัด accuracy — Kaggle label ไม่ใช่ ground truth (rule-derived, ดู kaggle_tu_import.py)

ต่อ template: lexicon dimensions ที่พบ + RAG gate + Claude verdict/title/summary
Output: data/processed/kaggle_tu_comparison.jsonl (resumable — ข้าม id ที่ทำแล้ว)

รัน: python -m ml.kaggle_tu_compare [--limit N] [--workers 6]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

warnings.filterwarnings("ignore")
os.environ.setdefault("PII_SALT", "compare-local")

from app.engines.qa_engine import RAG_WEAK_DIMENSIONS  # noqa: E402
from app.evidence.pattern_evidence import PatternEvidence  # noqa: E402
from app.services.ai_service import analyze_with_ai  # noqa: E402
from app.services.pattern_service import scan_text  # noqa: E402

CORPUS_PATH = Path("data/raw/scam_corpus.jsonl")
OUT_PATH = Path("data/processed/kaggle_tu_comparison.jsonl")
SOURCE_PREFIX = "Kaggle: Thai Scam From online Platforms"
_lock = threading.Lock()


def load_templates() -> list[dict]:
    recs = [json.loads(l) for l in CORPUS_PATH.read_text(encoding="utf-8").splitlines() if l.strip()]
    return [r for r in recs if r["source"]["name"].startswith(SOURCE_PREFIX)]


def load_done() -> set[str]:
    """ids ที่สำเร็จแล้ว — แถวที่ ok=False (เช่น API credit หมด) ถูกลบออกจากไฟล์เพื่อรันใหม่"""
    if not OUT_PATH.exists():
        return set()
    rows = [json.loads(l) for l in OUT_PATH.read_text(encoding="utf-8").splitlines() if l.strip()]
    good = [r for r in rows if r.get("ok")]
    if len(good) != len(rows):
        print(f"dropping {len(rows) - len(good)} failed rows for retry", flush=True)
        with OUT_PATH.open("w", encoding="utf-8") as f:
            for r in good:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return {r["id"] for r in good}


def run_one(rec: dict) -> dict:
    text = rec["text"]
    ev = PatternEvidence(dimensions=scan_text(text))
    dims = [d.dimension for d in ev.found]
    use_rag = any(d not in RAG_WEAK_DIMENSIONS for d in dims)
    result = analyze_with_ai(
        original_input=text,
        input_type="text",
        matched_pattern_names=ev.matched_pattern_names,
        blacklist_found=False,
        pattern_evidence_text=ev.to_evidence_text(),
        history_evidence_text="ประวัติการสนทนา: ไม่มี (เป็น turn แรก)",
        skip_rag=not use_rag,
    )
    s = result.get("structured") or {}
    kaggle = rec["annotation"]["labels"][0]
    return {
        "id": rec["id"],
        "text": text,
        "kaggle_verdict": rec["verdict"],
        "kaggle_category": rec.get("category"),
        "kaggle_notes": kaggle.get("notes"),
        "lexicon_dims": dims,
        "lexicon_terms": ev.terms_found,
        "rag_used": use_rag,
        "our_verdict": s.get("verdict") if s.get("response_type", "analysis") == "analysis" else s.get("response_type"),
        "our_title": s.get("title"),
        "our_summary": s.get("summary") or s.get("message"),
        "our_tactics": s.get("tactics"),
        "ok": bool(result.get("success")) and bool(s),
        "error": None if result.get("success") else result.get("message"),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--ids", default=None, help="jsonl ที่มี field id — รันซ้ำเฉพาะ ids เหล่านี้ (ลบผลเก่าของ ids นั้นก่อน)")
    ap.add_argument("--tag", default=None, help="ป้ายกำกับรอบ (เช่น post-fix-1) เก็บใน field run_tag")
    args = ap.parse_args()

    templates = load_templates()
    done = load_done()
    if args.ids:
        rerun_ids = {json.loads(l)["id"] for l in Path(args.ids).read_text(encoding="utf-8").splitlines() if l.strip()}
        rows = [json.loads(l) for l in OUT_PATH.read_text(encoding="utf-8").splitlines() if l.strip()] if OUT_PATH.exists() else []
        kept = [r for r in rows if r["id"] not in rerun_ids]
        with OUT_PATH.open("w", encoding="utf-8") as f:
            for r in kept:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        done = {r["id"] for r in kept}
        print(f"rerun {len(rerun_ids)} ids (removed old rows)", flush=True)
    todo = [r for r in templates if r["id"] not in done]
    if args.limit:
        todo = todo[: args.limit]
    print(f"templates {len(templates)} | done {len(done)} | todo {len(todo)} | workers {args.workers}", flush=True)
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    start = time.time()
    n_ok = n_err = 0
    with OUT_PATH.open("a", encoding="utf-8") as out, ThreadPoolExecutor(max_workers=args.workers) as ex:
        futures = {ex.submit(run_one, r): r["id"] for r in todo}
        for i, fut in enumerate(as_completed(futures), 1):
            try:
                row = fut.result()
            except Exception as e:  # noqa: BLE001
                row = {"id": futures[fut], "ok": False, "error": repr(e)}
            if args.tag:
                row["run_tag"] = args.tag
            with _lock:
                out.write(json.dumps(row, ensure_ascii=False) + "\n")
                out.flush()
            n_ok += int(row.get("ok", False))
            n_err += int(not row.get("ok", False))
            if i % 25 == 0 or i == len(todo):
                el = time.time() - start
                print(f"  {i}/{len(todo)} ok={n_ok} err={n_err} elapsed={el:.0f}s eta={el / i * (len(todo) - i):.0f}s", flush=True)
    print("done", flush=True)
    sys.stdout.flush()
    os._exit(0)  # torch/bge-m3 threads ค้างตอน shutdown บน Windows


if __name__ == "__main__":
    main()
