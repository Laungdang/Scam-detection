"""
Human review tool — accept/reject synthetic records ก่อนเข้า corpus

วิธีใช้:
    python -m ml.scrape.typhoon_review

Controls:
    y / Enter  → accept (เข้า corpus)
    n          → reject (เก็บไว้ rejected.jsonl)
    e          → edit text ก่อน accept
    s          → skip ไปอันถัดไป (ไว้ตัดสินทีหลัง)
    q          → quit
    a          → accept all remaining (ถ้ามั่นใจคุณภาพ)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from ml.scrape.schema import ScamRecord, SourceAttribution, append_records, load_records


PENDING_PATH = Path("data/raw/sources/typhoon_pending.jsonl")
REJECTED_PATH = Path("data/raw/sources/typhoon_rejected.jsonl")
REVIEWED_PATH = Path("data/raw/sources/typhoon_reviewed.jsonl")  # ที่ review แล้ว (ยังไม่ accept ก็มีใน list นี้)
CORPUS_PATH = Path("data/raw/scam_corpus.jsonl")


def _to_record(d: dict, review_status: str | None = None) -> ScamRecord:
    """สร้าง record v2 — tier C เสมอ; review.status ตามผลการ review (approved/rejected)"""
    from ml.scrape.schema import Annotation, PiiInfo, Review, now_iso

    src = dict(d["source"])
    src.setdefault("license", "synthetic")
    review_raw = d.get("review") or {}
    status = review_status or review_raw.get("status") or "pending_review"
    return ScamRecord(
        id=d["id"],
        text=d["text"],
        verdict=d["verdict"],
        category=d.get("category"),
        source=SourceAttribution(**src),
        tier="C",
        annotation=Annotation(**d["annotation"]) if d.get("annotation") else Annotation(),
        review=Review(
            status=status,
            reviewer=review_raw.get("reviewer") or ("human" if review_status else None),
            reviewed_at=now_iso() if review_status else review_raw.get("reviewed_at"),
            notes=review_raw.get("notes"),
        ),
        pii=PiiInfo(**d["pii"]) if d.get("pii") else PiiInfo(),
        annotator_notes=d.get("annotator_notes"),
    )


def _update_corpus_review(ids: set[str], status: str) -> set[str]:
    """ตั้ง review.status ให้ record tier C ที่อยู่ใน corpus แล้ว — คืน ids ที่ update จริง"""
    from ml.scrape.schema import now_iso

    if not CORPUS_PATH.exists():
        return set()
    updated: set[str] = set()
    lines_out: list[str] = []
    for line in CORPUS_PATH.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        d = json.loads(line)
        if d.get("id") in ids and d.get("tier") == "C":
            d["review"] = {
                "status": status,
                "reviewer": "human",
                "reviewed_at": now_iso(),
                "notes": (d.get("review") or {}).get("notes"),
            }
            updated.add(d["id"])
        lines_out.append(json.dumps(d, ensure_ascii=False))
    if updated:
        CORPUS_PATH.write_text("\n".join(lines_out) + "\n", encoding="utf-8")
    return updated


def _print_record(r: dict, idx: int, total: int) -> None:
    print("\n" + "=" * 70)
    print(f"  Record {idx + 1} / {total}  |  Category: {r['category']}  |  ID: {r['id']}")
    print("=" * 70)
    print(f"\n  {r['text']}\n")


def _prompt(msg: str) -> str:
    try:
        return input(msg).strip().lower()
    except (EOFError, KeyboardInterrupt):
        return "q"


def _edit_text(original: str) -> str:
    print(f"\nCurrent text:\n  {original}")
    print("Enter new text (or press Enter to keep original):")
    new_text = input("> ").strip()
    return new_text if new_text else original


def main() -> int:
    if not PENDING_PATH.exists():
        print(f"ERROR: {PENDING_PATH} ไม่เจอ — run typhoon_synthetic ก่อน")
        return 1

    pending = load_records(PENDING_PATH)
    if not pending:
        print("Pending list ว่าง — ไม่มีอะไรให้ review")
        return 0

    # โหลด ids ที่ review แล้ว — ข้ามได้
    reviewed_ids: set[str] = set()
    if REVIEWED_PATH.exists():
        for r in load_records(REVIEWED_PATH):
            reviewed_ids.add(r["id"])

    todo = [r for r in pending if r["id"] not in reviewed_ids]
    print(f"\nTotal pending: {len(pending)} | already reviewed: {len(reviewed_ids)} | to review: {len(todo)}\n")

    accepted: list[dict] = []
    rejected: list[dict] = []
    accept_all = False

    for idx, r in enumerate(todo):
        if not accept_all:
            _print_record(r, idx, len(todo))
            choice = _prompt("  [y]=accept / [n]=reject / [e]=edit / [s]=skip / [a]=accept all / [q]=quit: ")
        else:
            choice = "y"

        if choice == "q":
            print("\nQuitting...")
            break
        elif choice == "s":
            continue
        elif choice == "a":
            accept_all = True
            choice = "y"

        if choice == "n":
            rejected.append(r)
            print(f"  → REJECTED")
        elif choice == "e":
            r["text"] = _edit_text(r["text"])
            # หลัง edit อาจ id ไม่ match แล้ว — แต่ keep id เดิม ระบุใน notes
            r["annotator_notes"] = (r.get("annotator_notes") or "") + " | edited_during_review=true"
            accepted.append(r)
            print(f"  → ACCEPTED (edited)")
        else:  # y or default
            accepted.append(r)
            print(f"  → ACCEPTED")

    # mark reviewed (accepted + rejected) — กัน re-review
    reviewed_records = [_to_record(r) for r in (accepted + rejected)]
    if reviewed_records:
        append_records(reviewed_records, REVIEWED_PATH)

    # Data v2: record tier C อยู่ใน corpus แล้ว (status=pending_review) → update review ในที่
    # record ใหม่ที่ยังไม่อยู่ใน corpus → append พร้อม status
    if accepted:
        accepted_records = [_to_record(r, "approved") for r in accepted]
        updated = _update_corpus_review({r.id for r in accepted_records}, "approved")
        added = append_records([r for r in accepted_records if r.id not in updated], CORPUS_PATH)
        print(f"\n✓ Accepted: {len(accepted)} records ({len(updated)} updated in corpus, {added} added)")

    if rejected:
        rejected_records = [_to_record(r, "rejected") for r in rejected]
        updated = _update_corpus_review({r.id for r in rejected_records}, "rejected")
        append_records(rejected_records, REJECTED_PATH)
        print(f"✗ Rejected: {len(rejected)} records ({len(updated)} marked rejected in corpus; saved to {REJECTED_PATH})")

    skipped = len(todo) - len(accepted) - len(rejected)
    if skipped:
        print(f"⊘ Skipped: {skipped} records (run again to review)")

    total = sum(1 for _ in CORPUS_PATH.open(encoding="utf-8")) if CORPUS_PATH.exists() else 0
    print(f"\nCorpus total: {total} records")
    return 0


if __name__ == "__main__":
    sys.exit(main())
