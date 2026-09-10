"""
Preprocess (Data v2) — scam_corpus.jsonl → train/val/test ตาม tier rules + test lock

หลักการ (CLAUDE.md 10.2, 10.5):
- test set มาจาก tier A ∪ S **เท่านั้น** (ข้อมูลไทยจริง) — tier B/C/N ห้ามอยู่ใน test
- val = ส่วนที่เหลือของ A∪S (15%) + tier B ส่วนหนึ่ง (15%)
- train = A∪S ที่เหลือ + B ที่เหลือ + tier C ที่ review.status == approved
- tier N (narrative) ไม่เข้า ML เลย (RAG only)
- **Test lock:** ครั้งแรกที่รัน --lock-test จะเขียน data/processed/TEST_LOCK.json (ids + hash)
  รันครั้งต่อไป test = ids ที่ lock ไว้เสมอ; record ใหม่เข้า train/val เท่านั้น
  ห้าม re-stratify (บทเรียน Week 4) — เปลี่ยน lock ได้เฉพาะ --relock และต้องประกาศเป็น test_v{N}
- Deterministic seed (RANDOM_SEED)

รัน:
  python -m ml.preprocess --task multi            # ใช้ lock เดิม (ถ้ามี) ไม่งั้นสร้าง split แต่ไม่ lock
  python -m ml.preprocess --task multi --lock-test  # สร้าง + lock test ครั้งแรก
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from sklearn.model_selection import train_test_split

from ml.scrape.schema import is_usable_for


RANDOM_SEED = 42
CORPUS_PATH = Path("data/raw/scam_corpus.jsonl")
OUTPUT_DIR = Path("data/processed")
MULTI_CLASS_OUTPUT_DIR = Path("data/processed/multi")
TEST_LOCK_PATH = Path("data/processed/TEST_LOCK.json")

# สัดส่วนของ tier A∪S (ข้อมูลจริง) — test ใหญ่กว่า v1 (15%) โดยตั้งใจ เพราะ pool เล็ก (10.5)
REAL_TEST_RATIO = 0.30
REAL_VAL_RATIO = 0.15
FOREIGN_VAL_RATIO = 0.15


def label_for_task(record: dict, task: str) -> str:
    """task='binary' → verdict (safe/danger), task='multi' → 'safe' or category"""
    if task == "binary":
        return record["verdict"]
    if record["verdict"] == "safe":
        return "safe"
    return record.get("category") or "other"


def load_corpus() -> list[dict]:
    if not CORPUS_PATH.exists():
        raise FileNotFoundError(f"Corpus not found: {CORPUS_PATH} — run ml/scrape/* first")
    records = []
    with CORPUS_PATH.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    missing_tier = [r["id"] for r in records if "tier" not in r]
    if missing_tier:
        raise ValueError(
            f"{len(missing_tier)} records ไม่มี tier — รัน `python -m ml.scrape.migrate_v2` ก่อน"
        )
    return records


def _safe_stratified_split(records: list[dict], labels: list[str], test_size: float, seed: int):
    """train_test_split ที่ fallback เป็น non-stratified ถ้า class ใดมีน้อยกว่า 2"""
    counts = Counter(labels)
    stratify = labels if all(c >= 2 for c in counts.values()) else None
    if stratify is None:
        print("  WARNING: บาง class มี < 2 records — split แบบไม่ stratify")
    return train_test_split(records, labels, test_size=test_size, random_state=seed, stratify=stratify)


def split_by_tier(
    records: list[dict],
    task: str,
    locked_test_ids: set[str] | None,
    seed: int = RANDOM_SEED,
) -> tuple[list[dict], list[dict], list[dict]]:
    real = [r for r in records if is_usable_for(r, "test")]           # tier A, S
    foreign = [r for r in records if r.get("tier") == "B"]
    synthetic_ok = [r for r in records if r.get("tier") == "C" and is_usable_for(r, "train")]

    # ── test (จาก real เท่านั้น) ──
    if locked_test_ids is not None:
        test = [r for r in real if r["id"] in locked_test_ids]
        real_rest = [r for r in real if r["id"] not in locked_test_ids]
        missing = locked_test_ids - {r["id"] for r in test}
        if missing:
            raise ValueError(
                f"TEST_LOCK อ้างถึง {len(missing)} ids ที่หายไปจาก corpus (หรือ tier เปลี่ยน) — "
                f"ห้ามแก้ record ใน test เงียบๆ: {sorted(missing)[:5]}"
            )
    else:
        labels = [label_for_task(r, task) for r in real]
        real_rest, test, _, _ = _safe_stratified_split(real, labels, REAL_TEST_RATIO, seed)

    # ── val / train จาก real ที่เหลือ ──
    labels_rest = [label_for_task(r, task) for r in real_rest]
    val_frac = REAL_VAL_RATIO / (1 - REAL_TEST_RATIO)
    real_train, real_val, _, _ = _safe_stratified_split(real_rest, labels_rest, val_frac, seed)

    # ── tier B: train/val ──
    foreign_train, foreign_val = foreign, []
    if len(foreign) >= 10:
        labels_f = [label_for_task(r, task) for r in foreign]
        foreign_train, foreign_val, _, _ = _safe_stratified_split(foreign, labels_f, FOREIGN_VAL_RATIO, seed)

    train = real_train + foreign_train + synthetic_ok
    val = real_val + foreign_val
    return train, val, test


def save_split(records: list[dict], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def split_hash(records: list[dict]) -> str:
    ids = sorted(r["id"] for r in records)
    return hashlib.sha256("\n".join(ids).encode("utf-8")).hexdigest()[:16]


def report(name: str, records: list[dict], task: str) -> None:
    labels = Counter(label_for_task(r, task) for r in records)
    tiers = Counter(r.get("tier") for r in records)
    print(f"\n=== {name} ({len(records)} records, hash={split_hash(records)}) ===")
    print(f"  tiers: {dict(sorted(tiers.items()))}")
    print(f"  {task} labels:")
    for lab, c in labels.most_common():
        print(f"    {c:4d}  {lab}")


def load_lock() -> dict | None:
    if TEST_LOCK_PATH.exists():
        return json.loads(TEST_LOCK_PATH.read_text(encoding="utf-8"))
    return None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", choices=["binary", "multi"], default="binary")
    parser.add_argument("--lock-test", action="store_true", help="สร้างและ lock test set (ครั้งแรก)")
    parser.add_argument("--relock", action="store_true", help="เขียน lock ใหม่ทับ (ต้องประกาศ test_v{N} ใน thesis)")
    args = parser.parse_args()

    output_dir = MULTI_CLASS_OUTPUT_DIR if args.task == "multi" else OUTPUT_DIR

    print(f"Loading corpus from {CORPUS_PATH} (task={args.task}) ...")
    records = load_corpus()
    print(f"Loaded {len(records)} records; tiers = {dict(sorted(Counter(r['tier'] for r in records).items()))}")

    lock = load_lock()
    if lock and not args.relock:
        print(f"Using TEST_LOCK v{lock['version']} ({len(lock['ids'])} ids, hash={lock['hash']}, locked {lock['locked_at']})")
        locked_ids: set[str] | None = set(lock["ids"])
    else:
        locked_ids = None

    train, val, test = split_by_tier(records, args.task, locked_ids)

    if locked_ids is not None and split_hash(test) != lock["hash"]:
        raise ValueError("test hash ไม่ตรงกับ TEST_LOCK — corpus ถูกแก้ในส่วน test")

    save_split(train, output_dir / "train.jsonl")
    save_split(val, output_dir / "val.jsonl")
    save_split(test, output_dir / "test.jsonl")

    report("train", train, args.task)
    report("val", val, args.task)
    report("test", test, args.task)

    if args.lock_test or args.relock:
        from datetime import datetime, timezone
        version = (lock["version"] + 1) if (lock and args.relock) else 1
        TEST_LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
        TEST_LOCK_PATH.write_text(json.dumps({
            "version": version,
            "locked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "hash": split_hash(test),
            "size": len(test),
            "tiers": dict(Counter(r["tier"] for r in test)),
            "ids": sorted(r["id"] for r in test),
            "note": "test set = tier A ∪ S เท่านั้น; ห้ามแก้ — commit ไฟล์นี้ (CLAUDE.md 10.5)",
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nTEST LOCKED → {TEST_LOCK_PATH} (v{version}, {len(test)} ids) — commit ไฟล์นี้")
    elif locked_ids is None:
        print("\n(test ยังไม่ lock — รัน --lock-test เมื่อ tier A ถึงเป้าหรือก่อน train v2 ครั้งแรก)")

    metadata = {
        "schema": "v2",
        "task": args.task,
        "random_seed": RANDOM_SEED,
        "corpus_size": len(records),
        "tier_rules": "test=A∪S only; val=A∪S rest 15% + B 15%; train=rest + C(approved); N excluded",
        "test_locked": bool(args.lock_test or args.relock or locked_ids is not None),
        "splits": {
            "train": {"size": len(train), "hash": split_hash(train), "tiers": dict(Counter(r["tier"] for r in train))},
            "val": {"size": len(val), "hash": split_hash(val), "tiers": dict(Counter(r["tier"] for r in val))},
            "test": {"size": len(test), "hash": split_hash(test), "tiers": dict(Counter(r["tier"] for r in test))},
        },
        "stratify_by": "verdict" if args.task == "binary" else "category_or_safe",
    }
    (output_dir / "split_metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\nSplits written to {output_dir}/ (metadata: split_metadata.json)")


if __name__ == "__main__":
    main()
