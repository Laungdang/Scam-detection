"""
Validate scam_corpus.jsonl — ตรวจ integrity + stats สำหรับ defendable thesis

ทำอะไรบ้าง:
- นับ records ทั้งหมด
- distribution by source / verdict / category / extraction_method
- check duplicate text (อาจมี id ต่าง แต่ text เหมือน)
- check missing required fields
- check text length distribution
- compute basic stats (avg/min/max length)
"""

from __future__ import annotations

import json
import statistics
import sys
from collections import Counter
from pathlib import Path

INPUT_PATH = Path("data/raw/scam_corpus.jsonl")


def validate() -> int:
    if not INPUT_PATH.exists():
        print(f"ERROR: {INPUT_PATH} not found")
        return 1

    records: list[dict] = []
    issues: list[str] = []

    with INPUT_PATH.open(encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
                records.append(r)
            except json.JSONDecodeError as e:
                issues.append(f"Line {line_num}: invalid JSON — {e}")
                continue

            for required in ["id", "text", "verdict", "source"]:
                if required not in r:
                    issues.append(f"Line {line_num} (id={r.get('id')}): missing {required}")
            source = r.get("source", {})
            for required_src in ["name", "url", "scraped_at", "extraction_method"]:
                if required_src not in source:
                    issues.append(f"Line {line_num} (id={r.get('id')}): source.{required_src} missing")

    print(f"=== Corpus: {INPUT_PATH} ===")
    print(f"Total records: {len(records)}")
    print()

    by_id = Counter(r["id"] for r in records)
    dup_ids = [i for i, c in by_id.items() if c > 1]
    if dup_ids:
        issues.append(f"Duplicate IDs: {len(dup_ids)}")

    text_to_ids: dict[str, list[str]] = {}
    for r in records:
        text_to_ids.setdefault(r["text"], []).append(r["id"])
    dup_texts = {t: ids for t, ids in text_to_ids.items() if len(ids) > 1}
    if dup_texts:
        issues.append(f"Duplicate text bodies (same text, different IDs): {len(dup_texts)}")

    # ── schema v2 (tier system) ──────────────────────────────
    from ml.scrape.schema import TIER_NAMES, is_usable_for, validate_record

    v2_problems: list[str] = []
    for r in records:
        v2_problems.extend(validate_record(r))
    issues.extend(v2_problems[:50])
    if len(v2_problems) > 50:
        issues.append(f"... และอีก {len(v2_problems) - 50} ปัญหา schema v2")

    print(f"=== By tier (CLAUDE.md 10.2) ===")
    tier_counts = Counter(r.get("tier", "(none)") for r in records)
    for k in list(TIER_NAMES) + ["(none)"]:
        if tier_counts.get(k):
            print(f"  {tier_counts[k]:4d}  {k}  {TIER_NAMES.get(k, 'MISSING — ต้อง migrate')}")
    print()

    print(f"=== tier × verdict ===")
    for (t, v), n in sorted(Counter((r.get("tier", "?"), r["verdict"]) for r in records).items()):
        print(f"  {n:4d}  {t} / {v}")
    print()

    print(f"=== Usable for (after tier + review rules) ===")
    for purpose in ("train", "val", "test", "rag"):
        n = sum(1 for r in records if is_usable_for(r, purpose))
        print(f"  {purpose:5}: {n}")
    pending = sum(1 for r in records if r.get("tier") == "C" and (r.get("review") or {}).get("status") == "pending_review")
    print(f"  (tier C pending_review, excluded everywhere: {pending})")
    unannotated = sum(1 for r in records if r.get("tier") in ("A", "S") and not (r.get("annotation") or {}).get("guideline_version"))
    print(f"  (tier A/S ยังไม่ annotate ตาม guideline v2: {unannotated})")
    print()

    print(f"=== By verdict ===")
    for k, v in Counter(r["verdict"] for r in records).most_common():
        print(f"  {v:4d}  {k}")
    print()

    print(f"=== By source ===")
    for k, v in Counter(r["source"]["name"] for r in records).most_common():
        print(f"  {v:4d}  {k}")
    print()

    print(f"=== By extraction_method ===")
    for k, v in Counter(r["source"]["extraction_method"] for r in records).most_common():
        print(f"  {v:4d}  {k}")
    print()

    print(f"=== By category (scam class only) ===")
    scam_records = [r for r in records if r["verdict"] != "safe"]
    for k, v in Counter(r.get("category") or "(none)" for r in scam_records).most_common():
        print(f"  {v:4d}  {k}")
    print()

    if records:
        lengths = [len(r["text"]) for r in records]
        print(f"=== Text length ===")
        print(f"  count: {len(lengths)}")
        print(f"  min:   {min(lengths)}")
        print(f"  avg:   {statistics.mean(lengths):.1f}")
        print(f"  med:   {statistics.median(lengths):.0f}")
        print(f"  max:   {max(lengths)}")
        print()

    print(f"=== Validation issues ===")
    if not issues:
        print("  None — corpus passes integrity checks")
        return 0
    for issue in issues:
        print(f"  - {issue}")
    return 1


if __name__ == "__main__":
    sys.exit(validate())
