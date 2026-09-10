"""
วัดผลหลังแก้ lexicon/prompt: 49 เคสที่เคยต่างจาก Kaggle → ตอนนี้ระบบให้ verdict ตรง "guideline verdict" (จาก LLM judge) กี่เคส

input:
- data/processed/kaggle_tu_comparison.jsonl (แถวที่ run_tag == post-fix-* คือผลใหม่)
- data/processed/kaggle_tu_adjudication_round{1,2}.json (guideline_verdict ต่อ id)
- data/processed/kaggle_tu_disagreements.jsonl (verdict เดิมของเราก่อนแก้)

รัน: python -m ml.kaggle_tu_postfix
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

CMP = Path("data/processed/kaggle_tu_comparison.jsonl")
DIS = Path("data/processed/kaggle_tu_disagreements.jsonl")
R1 = Path("data/processed/kaggle_tu_adjudication_round1.json")
R2 = Path("data/processed/kaggle_tu_adjudication_round2.json")
OUT = Path("data/processed/kaggle_tu_postfix_report.md")

SEV = {"safe": 0, "caution": 1, "danger": 2}


def main() -> int:
    judge = {}
    for p in (R1, R2):
        for x in json.loads(p.read_text(encoding="utf-8"))["judgeItems"]:
            judge[x["id"]] = x
    before = {json.loads(l)["id"]: json.loads(l) for l in DIS.read_text(encoding="utf-8").splitlines() if l.strip()}
    after = {}
    for l in CMP.read_text(encoding="utf-8").splitlines():
        if not l.strip():
            continue
        r = json.loads(l)
        if r["id"] in before:
            after[r["id"]] = r

    rows = []
    for i, b in before.items():
        j = judge.get(i)
        a = after.get(i)
        if not j or not a:
            continue
        rows.append({
            "id": i, "text": b["text"], "kaggle": b["kaggle_verdict"], "guideline": j["guideline_verdict"],
            "before": b["our_verdict"], "after": a.get("our_verdict"), "reason": j["reason_group"],
            "after_ok": a.get("ok"), "rag_before": b.get("rag_used"), "rag_after": a.get("rag_used"),
        })

    n = len(rows)
    match_before = sum(1 for r in rows if r["before"] == r["guideline"])
    match_after = sum(1 for r in rows if r["after"] == r["guideline"])
    kaggle_match = sum(1 for r in rows if r["kaggle"] == r["guideline"])
    now_agree_kaggle = sum(1 for r in rows if r["after"] == r["kaggle"])
    improved = [r for r in rows if r["before"] != r["guideline"] and r["after"] == r["guideline"]]
    regressed = [r for r in rows if r["before"] == r["guideline"] and r["after"] != r["guideline"]]
    still_wrong = [r for r in rows if r["after"] != r["guideline"]]
    non_analysis = [r for r in rows if r["after"] not in SEV]

    lines = [
        "# หลังแก้ lexicon/prompt (post-fix) — 49 เคสที่เคยต่างจาก Kaggle",
        "",
        "guideline verdict = คำตัดสินของ LLM judge ตาม ANNOTATION_GUIDELINE v1.0 (ไม่ใช่ ground truth; 14 เคสยังรอคนตัดสิน)",
        "",
        f"| | ตรง guideline | / {n} |",
        "|---|---|---|",
        f"| Kaggle rule-label | {kaggle_match} | {kaggle_match / n:.0%} |",
        f"| ระบบเรา **ก่อนแก้** | {match_before} | {match_before / n:.0%} |",
        f"| ระบบเรา **หลังแก้** | {match_after} | {match_after / n:.0%} |",
        "",
        f"- ดีขึ้น (ผิด→ถูก): **{len(improved)}** | แย่ลง (ถูก→ผิด): **{len(regressed)}** | ยังไม่ตรง guideline: {len(still_wrong)} | ตอบ off_topic/chat/error: {len(non_analysis)}",
        f"- หลังแก้ ตรงกับ Kaggle: {now_agree_kaggle}/{n} (เดิม 0 — ทั้ง 49 คือเคสที่ต่าง)",
        f"- RAG ถูกเปิด: ก่อน {sum(1 for r in rows if r['rag_before'])} → หลัง {sum(1 for r in rows if r['rag_after'])}",
        "",
        "## ยังไม่ตรง guideline หลังแก้",
        "",
        "| id | ข้อความ | Kaggle | guideline | ก่อน | หลัง | กลุ่ม |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in still_wrong:
        lines.append(f"| `{r['id']}` | {r['text'][:55]} | {r['kaggle']} | {r['guideline']} | {r['before']} | {r['after']} | {r['reason']} |")
    lines += ["", "## แย่ลง", ""]
    for r in regressed:
        lines.append(f"- `{r['id']}` {r['text'][:70]} — guideline {r['guideline']}, ก่อน {r['before']} → หลัง {r['after']}")
    lines += ["", "## ดีขึ้น", ""]
    for r in improved:
        lines.append(f"- `{r['id']}` {r['text'][:70]} — guideline {r['guideline']}, ก่อน {r['before']} → หลัง {r['after']}")
    lines += ["", "## กลุ่มที่ยังผิด (นับ)", "", str(dict(Counter(r["reason"] for r in still_wrong)))]
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines[:14]))
    print(f"\nreport → {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
