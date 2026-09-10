"""
Week 4 Error Analysis — auto-categorize misclassifications + stats

Load best model (XGBoost multi-class) → predict on test → analyze errors:
- Per (true, predicted) error matrix with sample texts
- Aggregate stats: length distribution, source bias, language mix
- Identify systematic failure modes
- Suggest fixes

วิธีใช้:
    python -m ml.error_analysis --version v0.4.0-xgb-multi
"""

from __future__ import annotations

import argparse
import json
import pickle
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np


PROCESSED_MULTI = Path("data/processed/multi")
MODELS_DIR = Path("models")
REPORTS_DIR = Path("models/error_analysis")


def load_split(name: str) -> list[dict]:
    records = []
    with (PROCESSED_MULTI / f"{name}.jsonl").open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def label_for_record(r: dict) -> str:
    if r["verdict"] == "safe":
        return "safe"
    return r.get("category") or "other"


def load_model(version: str):
    with (MODELS_DIR / version / "model.pkl").open("rb") as f:
        obj = pickle.load(f)
    if isinstance(obj, dict) and "pipeline" in obj:
        return obj["pipeline"], obj["label_encoder"]
    return obj, None


def predict_all(pipeline, encoder, texts: list[str]) -> tuple[list[str], np.ndarray]:
    raw = pipeline.predict(texts)
    if encoder is not None:
        preds = encoder.inverse_transform(raw).tolist()
    else:
        preds = raw.tolist()
    probs = pipeline.predict_proba(texts)
    return preds, probs


def has_thai_script(s: str) -> bool:
    return any("฀" <= c <= "๿" for c in s)


def has_english(s: str) -> bool:
    return any(c.isascii() and c.isalpha() for c in s)


def has_url_placeholder(s: str) -> bool:
    return "<URL>" in s or "http" in s.lower() or "bit.ly" in s.lower()


def has_question_marker(s: str) -> bool:
    markers = ["ทำยังไง", "ทำไง", "ช่วย", "ไหม", "มั้ย", "?", "?", "ดี"]
    return any(m in s for m in markers)


def char_count(s: str) -> int:
    return len(s)


def feature_summary(records: list[dict]) -> dict:
    if not records:
        return {}
    lens = [char_count(r["text"]) for r in records]
    return {
        "count": len(records),
        "avg_len": round(sum(lens) / len(lens), 1),
        "median_len": int(np.median(lens)),
        "thai_pct": round(sum(has_thai_script(r["text"]) for r in records) / len(records) * 100, 1),
        "english_pct": round(sum(has_english(r["text"]) for r in records) / len(records) * 100, 1),
        "with_url_pct": round(sum(has_url_placeholder(r["text"]) for r in records) / len(records) * 100, 1),
        "with_question_pct": round(sum(has_question_marker(r["text"]) for r in records) / len(records) * 100, 1),
        "sources": dict(Counter(r["source"]["name"][:30] for r in records).most_common(3)),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", default="v0.4.0-xgb-multi")
    parser.add_argument("--sample-per-error-cell", type=int, default=3,
                       help="แสดงตัวอย่างกี่อันต่อ error type")
    args = parser.parse_args()

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Loading model {args.version} ...")
    pipeline, encoder = load_model(args.version)
    classes = list(encoder.classes_) if encoder is not None else list(pipeline.classes_)
    print(f"Classes: {classes}")

    print("\nLoading test set ...")
    test = load_split("test")
    texts = [r["text"] for r in test]
    y_true = [label_for_record(r) for r in test]

    print("Predicting ...")
    y_pred, probs = predict_all(pipeline, encoder, texts)

    # build error list with metadata
    errors = []
    for r, true_lab, pred_lab, prob_row in zip(test, y_true, y_pred, probs):
        if true_lab == pred_lab:
            continue
        true_idx = classes.index(true_lab) if true_lab in classes else -1
        pred_idx = classes.index(pred_lab) if pred_lab in classes else -1
        errors.append({
            "id": r["id"],
            "text": r["text"],
            "true": true_lab,
            "pred": pred_lab,
            "pred_confidence": float(prob_row[pred_idx]) if pred_idx >= 0 else None,
            "true_class_prob": float(prob_row[true_idx]) if true_idx >= 0 else None,
            "source": r["source"]["name"][:40],
            "extraction_method": r["source"]["extraction_method"],
        })

    total = len(test)
    n_errors = len(errors)
    print(f"\n=== Error summary ===")
    print(f"Total test: {total}, Errors: {n_errors} ({n_errors/total*100:.1f}%)")

    # === Error matrix ===
    error_pairs = Counter((e["true"], e["pred"]) for e in errors)
    print(f"\n=== Error matrix (true → predicted, count) ===")
    for (t, p), c in error_pairs.most_common():
        true_total = sum(1 for tl in y_true if tl == t)
        print(f"  {t:>26s} → {p:<26s} : {c:>3d}  ({c/true_total*100:.0f}% of {true_total} {t} samples)")

    # === Per-error-class sample texts ===
    print(f"\n=== Sample misclassifications (up to {args.sample_per_error_cell} per error type) ===")
    by_pair = defaultdict(list)
    for e in errors:
        by_pair[(e["true"], e["pred"])].append(e)

    for (t, p), errs in sorted(by_pair.items(), key=lambda kv: -len(kv[1])):
        print(f"\n[true={t} → pred={p}] {len(errs)} errors")
        for e in errs[:args.sample_per_error_cell]:
            print(f"  conf={e['pred_confidence']:.2f} src={e['extraction_method'][:14]} | {e['text'][:120]}")

    # === Aggregate stats: correct vs error ===
    correct = [r for r, t, p in zip(test, y_true, y_pred) if t == p]
    errored = [r for r, t, p in zip(test, y_true, y_pred) if t != p]

    print(f"\n=== Aggregate: correct vs error ===")
    print(f"  Correct: {feature_summary(correct)}")
    print(f"  Errored: {feature_summary(errored)}")

    # === Errors by source ===
    print(f"\n=== Errors by extraction_method ===")
    err_by_src = Counter(e["extraction_method"] for e in errors)
    correct_by_src = Counter(r["source"]["extraction_method"] for r, t, p in zip(test, y_true, y_pred) if t == p)
    all_src = set(err_by_src) | set(correct_by_src)
    for src in sorted(all_src):
        n_err = err_by_src.get(src, 0)
        n_corr = correct_by_src.get(src, 0)
        total_src = n_err + n_corr
        if total_src > 0:
            err_rate = n_err / total_src * 100
            print(f"  {src:>20s}: {n_err:>3d} err / {total_src:>3d} total ({err_rate:.1f}% error rate)")

    # === "other" category analysis ===
    print(f"\n=== Special: 'other' category as error magnet ===")
    other_as_true = sum(1 for e in errors if e["true"] == "other")
    other_as_pred = sum(1 for e in errors if e["pred"] == "other")
    print(f"  Errors where true='other': {other_as_true}")
    print(f"  Errors where pred='other': {other_as_pred}")

    # === Save report ===
    report = {
        "model_version": args.version,
        "test_size": total,
        "n_errors": n_errors,
        "error_rate": round(n_errors / total, 4),
        "error_matrix": [{"true": t, "pred": p, "count": c} for (t, p), c in error_pairs.most_common()],
        "errors": errors,
        "summary_correct": feature_summary(correct),
        "summary_errored": feature_summary(errored),
        "errors_by_extraction_method": dict(err_by_src),
    }
    out = REPORTS_DIR / f"{args.version}_errors.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"\nSaved detailed report to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
