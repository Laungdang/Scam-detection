"""
สรุปผล external comparison (Kaggle rule-label vs ระบบเรา) → agreement matrix + disagreement groups

input : data/processed/kaggle_tu_comparison.jsonl  (จาก ml/kaggle_tu_compare.py)
output: data/processed/kaggle_tu_report.md          (ตาราง + ตัวอย่าง สำหรับ thesis)
        data/processed/kaggle_tu_disagreements.jsonl (ให้คน/agent ตัดสินตาม ANNOTATION_GUIDELINE)
        data/processed/kaggle_tu_safe_candidates.jsonl (normal ที่ทั้งคู่ว่า safe → tier S candidate หลังคนกวาดตา)

รัน: python -m ml.kaggle_tu_report
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

IN_PATH = Path("data/processed/kaggle_tu_comparison.jsonl")
REPORT = Path("data/processed/kaggle_tu_report.md")
DISAGREE = Path("data/processed/kaggle_tu_disagreements.jsonl")
SAFE_CAND = Path("data/processed/kaggle_tu_safe_candidates.jsonl")

ORDER = ["safe", "caution", "danger"]
SEV = {"safe": 0, "caution": 1, "danger": 2}
REQUEST_DIMS = {"money_request", "credential_request", "link_action", "channel_shift", "borrowing_pretext"}


def reason_group(row: dict) -> str:
    """จัดกลุ่ม disagreement จากหลักฐานที่ระบบเห็น (ไม่ใช่จากคำตอบ Claude)"""
    dims = set(row.get("lexicon_dims") or [])
    k, o = row["kaggle_verdict"], row["our_verdict"]
    if o not in SEV:
        return "our_non_analysis"  # chat/off_topic/None
    kaggle_higher = SEV[k] > SEV[o]
    has_request = bool(dims & REQUEST_DIMS)
    if kaggle_higher and not dims:
        return "kaggle_stricter__no_lexicon_signal"
    if kaggle_higher and not has_request:
        return "kaggle_stricter__signal_but_no_request"   # เช่น urgency/reward/authority อย่างเดียว
    if kaggle_higher and has_request:
        return "kaggle_stricter__request_present"          # ระบบเห็นการขอแต่ยังให้ต่ำกว่า — ต้องดู
    if not kaggle_higher and has_request:
        return "ours_stricter__request_present"
    return "ours_stricter__no_request"


def main() -> int:
    import argparse
    global REPORT, DISAGREE, SAFE_CAND
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="in_path", default=str(IN_PATH), help="comparison jsonl (เช่น *_prefix.jsonl)")
    ap.add_argument("--suffix", default="", help="ต่อท้ายชื่อไฟล์ output เช่น _postfix")
    args = ap.parse_args()
    if args.suffix:
        REPORT = REPORT.with_name(REPORT.stem + args.suffix + REPORT.suffix)
        DISAGREE = DISAGREE.with_name(DISAGREE.stem + args.suffix + DISAGREE.suffix)
        SAFE_CAND = SAFE_CAND.with_name(SAFE_CAND.stem + args.suffix + SAFE_CAND.suffix)
    rows = [json.loads(l) for l in Path(args.in_path).read_text(encoding="utf-8").splitlines() if l.strip()]
    ok = [r for r in rows if r.get("ok") and r.get("our_verdict") in SEV]
    off_topic = [r for r in rows if r.get("ok") and r.get("our_verdict") in ("off_topic", "chat")]
    failed = [r for r in rows if not r.get("ok")]
    print(f"rows {len(rows)} | analysable {len(ok)} | off_topic/chat {len(off_topic)} | api error {len(failed)}")

    matrix = Counter((r["kaggle_verdict"], r["our_verdict"]) for r in ok)
    agree = sum(matrix[(v, v)] for v in ORDER)
    off_by_one = sum(n for (k, o), n in matrix.items() if abs(SEV[k] - SEV[o]) == 1)
    off_by_two = sum(n for (k, o), n in matrix.items() if abs(SEV[k] - SEV[o]) == 2)

    dis = [r for r in ok if r["kaggle_verdict"] != r["our_verdict"]]
    for r in dis:
        r["reason_group"] = reason_group(r)
    groups = defaultdict(list)
    for r in dis:
        groups[r["reason_group"]].append(r)

    safe_cands = [r for r in ok if r["kaggle_verdict"] == "safe" and r["our_verdict"] == "safe"]

    lines = [
        "# Kaggle TU dataset × ระบบเรา — External comparison (2026-08-29)",
        "",
        "**คำเตือน:** Kaggle label เป็น rule-label (threshold ของ risk score จาก keyword) ไม่ใช่ ground truth — ตารางนี้วัด *ความต่างของวิธีคิด* ไม่ใช่ accuracy ของฝ่ายใด",
        "",
        f"- template ทั้งหมด (dedupe จาก 2,999 แถว): {len(rows)} (จาก 341 ใน corpus — ที่เหลือยังไม่ได้รัน/API error)",
        f"- วิเคราะห์ได้: {len(ok)} | ระบบตอบ off_topic/chat: {len(off_topic)} "
        f"(Kaggle label: {dict(Counter(r['kaggle_verdict'] for r in off_topic))} — ข้อความที่เป็น 'คำขอถึงบอท' เช่น 'ขอแนวข้อสอบ' "
        f"ไม่ใช่ข้อความให้ตรวจ; ใน production = ไม่มีบริบท scam) | API error: {len(failed)}",
        f"- ตรงกัน: **{agree}/{len(ok)} = {agree / len(ok):.1%}** | ต่าง 1 ระดับ: {off_by_one} | ต่าง 2 ระดับ (safe↔danger): {off_by_two}",
        "",
        "## Agreement matrix (แถว = Kaggle rule-label, คอลัมน์ = ระบบเรา)",
        "",
        "| Kaggle \\ เรา | safe | caution | danger | รวม |",
        "|---|---|---|---|---|",
    ]
    for k in ORDER:
        tot = sum(matrix[(k, o)] for o in ORDER)
        lines.append(f"| **{k}** | " + " | ".join(
            f"**{matrix[(k, o)]}**" if k == o else str(matrix[(k, o)]) for o in ORDER) + f" | {tot} |")
    lines += ["", "## Disagreement ตามกลุ่มหลักฐาน", "", "| กลุ่ม | n | ความหมาย |", "|---|---|---|"]
    meaning = {
        "kaggle_stricter__no_lexicon_signal": "Kaggle ให้สูงกว่า ทั้งที่ lexicon ไม่พบสัญญาณเลย",
        "kaggle_stricter__signal_but_no_request": "Kaggle ให้สูงกว่า; พบแค่ urgency/reward/authority ไม่มี 'การขอ' (จุดต่างหลักของหลักการ)",
        "kaggle_stricter__request_present": "Kaggle ให้สูงกว่า ทั้งที่ระบบเห็นการขอ — ต้องดูว่าเราให้ต่ำไปไหม",
        "ours_stricter__request_present": "เราให้สูงกว่า และมีการขอ — น่าจะเราถูก",
        "ours_stricter__no_request": "เราให้สูงกว่า โดยไม่มีการขอ — ต้องดูว่าเรา over-flag ไหม",
        "our_non_analysis": "ระบบตอบ chat/off_topic",
    }
    for g, items in sorted(groups.items(), key=lambda x: -len(x[1])):
        lines.append(f"| `{g}` | {len(items)} | {meaning.get(g, '')} |")
    lines += ["", "## ตัวอย่างต่อกลุ่ม (สูงสุด 5)", ""]
    for g, items in sorted(groups.items(), key=lambda x: -len(x[1])):
        lines.append(f"### {g} ({len(items)})")
        for r in items[:5]:
            lines.append(f"- Kaggle **{r['kaggle_verdict']}** / เรา **{r['our_verdict']}** — `{r['text'][:90]}`  ")
            lines.append(f"  lexicon: {', '.join(r.get('lexicon_dims') or []) or '—'} | เรา: {(r.get('our_summary') or '')[:140]}")
        lines.append("")
    lines += [
        "## Safe candidates (tier S หลังคนกวาดตา)",
        "",
        f"- Kaggle normal ∧ เรา safe: **{len(safe_cands)}** template → `{SAFE_CAND}`",
        "",
        "## วิธีอ่านผลใน thesis",
        "",
        "- กลุ่ม `kaggle_stricter__signal_but_no_request` คือความต่างเชิงหลักการที่ตั้งใจ: rule นับ keyword, ระบบเราตัดสินจาก 'การขอ' (ANNOTATION_GUIDELINE §0)",
        "- กลุ่ม `*__request_present` และ `ours_stricter__no_request` ต้องมีคนตัดสินตาม guideline — เป็นชุด calibration ให้ annotator",
    ]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    with DISAGREE.open("w", encoding="utf-8") as f:
        for r in dis:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    with SAFE_CAND.open("w", encoding="utf-8") as f:
        for r in safe_cands:
            f.write(json.dumps({"id": r["id"], "text": r["text"], "kaggle_notes": r.get("kaggle_notes")}, ensure_ascii=False) + "\n")
    print("\n".join(lines[:30]))
    print(f"\nreport → {REPORT} | disagreements {len(dis)} → {DISAGREE} | safe candidates {len(safe_cands)} → {SAFE_CAND}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
