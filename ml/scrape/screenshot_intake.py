"""
Screenshot intake — รูป SMS/แชทที่คนเก็บมา (data/raw/screenshots/log.csv) → OCR → คนตรวจ → tier A

ขั้น 1  python -m ml.scrape.screenshot_intake ocr
        อ่าน log.csv → OCR ทุกรูปด้วย EasyOCR (ไม่ใช้ Claude Vision — ข้อมูลเข้า corpus ต้อง deterministic)
        → เขียน data/raw/screenshots/ocr_candidates.jsonl (1 แถว/รูป: text ที่อ่านได้, confidence, provenance)
        → เขียน data/annotation/screenshot_verify.md ให้คนแก้ข้อความที่ OCR อ่านผิด + ติ๊กว่าใช้ได้

ขั้น 2  คนเปิด screenshot_verify.md แก้ text ให้ตรงกับรูป (คอลัมน์ "ข้อความที่ถูกต้อง") ใส่ x ในคอลัมน์ "ใช้" ถ้าเป็นข้อความ scam จริง

ขั้น 3  python -m ml.scrape.screenshot_intake append --reviewer A1
        อ่านไฟล์ที่แก้แล้ว → mask PII → append เป็น tier A (extraction_method = verbatim_ocr, snapshot_hash = sha256 ของรูป)
        label เริ่มต้น: verdict/category ว่าง (ต้อง annotate ตาม guideline ทีหลัง) → ใส่ verdict="danger", category="other"
        เป็น weak label ชั่วคราว + annotation.guideline_version = null

CLAUDE.md 6.4: OCR ที่นี่ใช้ allow_llm_fallback=False เสมอ
"""

from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import json
import os
import re
from pathlib import Path

os.environ.setdefault("PII_SALT", "intake-local")

ROOT = Path("data/raw/screenshots")
LOG = ROOT / "log.csv"
CANDIDATES = ROOT / "ocr_candidates.jsonl"
VERIFY_MD = Path("data/annotation/screenshot_verify.md")
CORPUS = Path("data/raw/scam_corpus.jsonl")

SOURCE_NAMES = {
    "ccib": "กองบัญชาการตำรวจสืบสวนสอบสวนอาชญากรรมทางเทคโนโลยี (ตำรวจไซเบอร์) — Facebook",
    "police": "สำนักงานตำรวจแห่งชาติ / เพจตำรวจ",
    "bank": "ธนาคาร (หน้าเตือนภัย/เพจทางการ)",
    "telco": "ผู้ให้บริการมือถือ (AIS/True/dtac)",
    "news": "สำนักข่าว",
    "pantip": "Pantip (โพสต์สาธารณะ)",
    "x": "X/Twitter (โพสต์สาธารณะ)",
    "whoscall": "Whoscall / Gogolook",
}


def cmd_ocr() -> int:
    from app.services.ocr_service import extract_text_from_image

    rows = list(csv.DictReader(LOG.open(encoding="utf-8-sig")))
    done = set()
    if CANDIDATES.exists():
        done = {json.loads(l)["file"] for l in CANDIDATES.read_text(encoding="utf-8").splitlines() if l.strip()}
    out = CANDIDATES.open("a", encoding="utf-8")
    n = 0
    for r in rows:
        f = r["file"].strip()
        if not f or f in done:
            continue
        path = ROOT / r["source"] / f
        if not path.exists():
            print(f"  missing: {path}")
            continue
        data = path.read_bytes()
        mt = "image/png" if path.suffix.lower() == ".png" else "image/jpeg" if path.suffix.lower() in (".jpg", ".jpeg") else "image/webp"
        try:
            res = extract_text_from_image(base64.b64encode(data).decode(), image_media_type=mt, allow_llm_fallback=False)
            text, conf = res.text, res.avg_confidence
        except Exception as e:  # noqa: BLE001
            text, conf = "", 0.0
            print(f"  OCR failed {f}: {e!r}")
        rec = {"file": f, "source": r["source"], "post_url": r["post_url"], "post_date": r.get("post_date", ""),
               "note": r.get("note", ""), "snapshot_hash": hashlib.sha256(data).hexdigest(), "ocr_text": text,
               "ocr_confidence": round(float(conf or 0), 3)}
        out.write(json.dumps(rec, ensure_ascii=False) + "\n")
        n += 1
        print(f"  {f}: conf={rec['ocr_confidence']:.2f} | {text[:70]!r}")
    out.close()
    write_verify_md()
    print(f"OCR {n} new image(s) → {CANDIDATES}; verify sheet → {VERIFY_MD}")
    return 0


def write_verify_md() -> None:
    cands = [json.loads(l) for l in CANDIDATES.read_text(encoding="utf-8").splitlines() if l.strip()]
    L = ["# ตรวจข้อความจาก screenshot (OCR) — แก้ให้ตรงรูป แล้วใส่ x ในคอลัมน์ 'ใช้' ถ้าเป็นข้อความ scam จริง", "",
         "1 รูปอาจมีหลายข้อความ: แยกด้วย `||` ในคอลัมน์ 'ข้อความที่ถูกต้อง' · ข้อความที่ไม่ใช่ scam (คำเตือนของเพจ, หัวข้อข่าว) ไม่ต้องใส่", "",
         "| file | แหล่ง | conf | OCR อ่านได้ | ข้อความที่ถูกต้อง | ใช้ |", "|---|---|---|---|---|---|"]
    for c in cands:
        L.append(f"| {c['file']} | {c['source']} | {c['ocr_confidence']:.2f} | {c['ocr_text'][:200].replace('|', '/').replace(chr(10), ' ')} |  |  |")
    VERIFY_MD.parent.mkdir(parents=True, exist_ok=True)
    VERIFY_MD.write_text("\n".join(L) + "\n", encoding="utf-8")


def cmd_append(reviewer: str, dry_run: bool) -> int:
    from app.services.pii_masker import mask_pii
    from ml.scrape.schema import (Annotation, AnnotationLabel, PiiInfo, ScamRecord, SourceAttribution,
                                  append_records, make_id, now_iso)

    cands = {json.loads(l)["file"]: json.loads(l) for l in CANDIDATES.read_text(encoding="utf-8").splitlines() if l.strip()}
    records: list[ScamRecord] = []
    for line in VERIFY_MD.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^\| (\S+) \| (\w+) \| [\d.]+ \| .*? \| (.*?) \| (.*?) \|$", line)
        if not m or m.group(4).strip().lower() not in ("x", "✓", "y", "yes"):
            continue
        f, src, corrected = m.group(1), m.group(2), m.group(3).strip()
        c = cands.get(f)
        if not c or not corrected:
            continue
        for text in [t.strip() for t in corrected.split("||") if t.strip()]:
            masked = mask_pii(text, mode="strict")
            records.append(ScamRecord(
                id=make_id(f"shot-{src}", masked.masked), text=masked.masked, verdict="danger", category="other", tier="A",
                source=SourceAttribution(name=SOURCE_NAMES.get(src, src), url=c["post_url"], scraped_at=now_iso(),
                                         extraction_method="verbatim_ocr", published_date=c.get("post_date") or None,
                                         license="fair_use_academic",
                                         license_note=f"screenshot from public post; OCR (EasyOCR conf {c['ocr_confidence']}) corrected by {reviewer}; image sha256 in snapshot_hash",
                                         snapshot_hash=c["snapshot_hash"]),
                annotation=Annotation(labels=[AnnotationLabel(annotator=f"intake:{reviewer}", verdict="danger", category="other",
                                                              notes="weak label: มาจากโพสต์เตือนภัย — ต้อง annotate ตาม guideline")],
                                      final={"verdict": "danger", "category": "other", "resolved_by": "source_weak_label"},
                                      guideline_version=None),
                pii=PiiInfo(masked=True, masker_version="pii_masker@2026-08", pii_found_count=len(masked.pii_found)),
                annotator_notes=f"screenshot={src}/{f} | {c.get('note', '')}",
            ))
    print(f"records ready: {len(records)}")
    for r in records[:5]:
        print("  -", r.text[:90])
    if dry_run:
        return 0
    added = append_records(records, CORPUS)
    print(f"appended {added} tier A (verbatim_ocr) → {CORPUS}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("ocr")
    a = sub.add_parser("append")
    a.add_argument("--reviewer", required=True)
    a.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    if args.cmd == "ocr":
        return cmd_ocr()
    return cmd_append(args.reviewer, args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
