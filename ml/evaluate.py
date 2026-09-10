"""
Evaluate trained model บน locked test set + เปรียบเทียบกับ baselines

หลักการ (ดู CLAUDE.md Section 4.6):
- Test set lock — ครั้งแรกที่ดู
- Bootstrap 95% CI สำหรับทุก metric
- เปรียบเทียบกับ 4 baselines:
  1. Majority class
  2. Random (stratified)
  3. Keyword-only (URL/ลิงก์/คลิก)
  4. Our trained model
- McNemar test เปรียบเทียบ pairwise

วิธีใช้:
    python -m ml.evaluate --version v0.1.0
"""

from __future__ import annotations

import argparse
import json
import pickle
import re
import sys
from pathlib import Path

import numpy as np
from scipy.stats import binomtest
from sklearn.dummy import DummyClassifier
from sklearn.metrics import (
    accuracy_score, classification_report, confusion_matrix, f1_score,
    precision_score, recall_score,
)


PROCESSED_DIR = Path("data/processed")
MODELS_DIR = Path("models")
BOOTSTRAP_ITERS = 1000
RNG_SEED = 42


def load_split(name: str) -> tuple[list[str], list[str]]:
    path = PROCESSED_DIR / f"{name}.jsonl"
    texts, labels = [], []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            texts.append(r["text"])
            labels.append(r["verdict"])
    return texts, labels


# ─────────────────────────────────────────────────────────────────
# Baselines
# ─────────────────────────────────────────────────────────────────

KEYWORD_RE = re.compile(
    r"(คลิก|ลิงก์|ลิ้ง|กดลิงก์|click|http|<URL>|line\.me|bit\.ly)",
    re.IGNORECASE,
)


def baseline_majority(train_labels: list[str], test_texts: list[str]) -> list[str]:
    """ทาย class ที่เยอะที่สุดเสมอ"""
    from collections import Counter
    majority = Counter(train_labels).most_common(1)[0][0]
    return [majority] * len(test_texts)


def baseline_random_stratified(train_labels: list[str], test_texts: list[str]) -> list[str]:
    """random ตามสัดส่วน class ใน train"""
    from collections import Counter
    total = len(train_labels)
    probs = {c: n / total for c, n in Counter(train_labels).items()}
    rng = np.random.default_rng(RNG_SEED)
    classes = list(probs.keys())
    weights = [probs[c] for c in classes]
    return [str(rng.choice(classes, p=weights)) for _ in test_texts]


def baseline_keyword(test_texts: list[str]) -> list[str]:
    """ทาย danger ถ้าเจอ keyword ที่ระบุ"""
    return ["danger" if KEYWORD_RE.search(t) else "safe" for t in test_texts]


# ─────────────────────────────────────────────────────────────────
# Bootstrap CI
# ─────────────────────────────────────────────────────────────────

def bootstrap_ci(
    y_true: list[str],
    y_pred: list[str],
    metric_fn,
    iters: int = BOOTSTRAP_ITERS,
    seed: int = RNG_SEED,
) -> tuple[float, float, float]:
    """returns (point_estimate, ci_low, ci_high) at 95%"""
    rng = np.random.default_rng(seed)
    n = len(y_true)
    point = metric_fn(y_true, y_pred)
    scores = []
    y_true_arr = np.array(y_true)
    y_pred_arr = np.array(y_pred)
    for _ in range(iters):
        idx = rng.integers(0, n, size=n)
        try:
            scores.append(metric_fn(y_true_arr[idx].tolist(), y_pred_arr[idx].tolist()))
        except Exception:
            continue
    low = float(np.percentile(scores, 2.5))
    high = float(np.percentile(scores, 97.5))
    return float(point), low, high


def macro_f1(y_true, y_pred) -> float:
    return f1_score(y_true, y_pred, average="macro", zero_division=0)


def accuracy(y_true, y_pred) -> float:
    return accuracy_score(y_true, y_pred)


# ─────────────────────────────────────────────────────────────────
# McNemar test (paired comparison)
# ─────────────────────────────────────────────────────────────────

def mcnemar_test(y_true: list[str], pred_a: list[str], pred_b: list[str]) -> dict:
    """compare 2 classifiers pairwise — return p-value

    McNemar's test ใช้สำหรับเปรียบเทียบ classifier 2 ตัวบน sample เดียวกัน
    (paired test) — เหมาะกว่า paired t-test สำหรับ binary classification accuracy
    """
    n_a_correct_b_wrong = 0  # A ถูก, B ผิด
    n_a_wrong_b_correct = 0  # A ผิด, B ถูก
    for true, a, b in zip(y_true, pred_a, pred_b):
        a_correct = (a == true)
        b_correct = (b == true)
        if a_correct and not b_correct:
            n_a_correct_b_wrong += 1
        elif not a_correct and b_correct:
            n_a_wrong_b_correct += 1

    n_disagree = n_a_correct_b_wrong + n_a_wrong_b_correct
    if n_disagree == 0:
        return {"p_value": 1.0, "n_disagree": 0, "verdict": "no_difference"}

    # binomial test (exact) — H0: P(A correct, B wrong) = P(A wrong, B correct)
    result = binomtest(n_a_correct_b_wrong, n_disagree, p=0.5)
    p = float(result.pvalue)
    return {
        "p_value": p,
        "n_disagree": n_disagree,
        "n_a_better": n_a_correct_b_wrong,
        "n_b_better": n_a_wrong_b_correct,
        "verdict": "significant" if p < 0.05 else "not_significant",
    }


# ─────────────────────────────────────────────────────────────────
# Main eval
# ─────────────────────────────────────────────────────────────────

def report_predictor(name: str, y_true: list[str], y_pred: list[str]) -> dict:
    acc, acc_low, acc_high = bootstrap_ci(y_true, y_pred, accuracy)
    f1, f1_low, f1_high = bootstrap_ci(y_true, y_pred, macro_f1)
    print(f"\n--- {name} ---")
    print(f"  accuracy   = {acc:.4f}  [95% CI {acc_low:.4f}, {acc_high:.4f}]")
    print(f"  macro-F1   = {f1:.4f}  [95% CI {f1_low:.4f}, {f1_high:.4f}]")
    print(classification_report(y_true, y_pred, digits=3, zero_division=0))
    return {
        "name": name,
        "accuracy": {"point": acc, "ci_low": acc_low, "ci_high": acc_high},
        "macro_f1": {"point": f1, "ci_low": f1_low, "ci_high": f1_high},
        "per_class": classification_report(y_true, y_pred, output_dict=True, zero_division=0),
        "confusion_matrix": confusion_matrix(y_true, y_pred, labels=sorted(set(y_true))).tolist(),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", default="v0.1.0")
    args = parser.parse_args()

    model_dir = MODELS_DIR / args.version
    print(f"Loading model {args.version} ...")
    with (model_dir / "model.pkl").open("rb") as f:
        model = pickle.load(f)

    print("Loading test + train (train needed for baselines) ...")
    train_texts, train_labels = load_split("train")
    test_texts, test_labels = load_split("test")
    print(f"Test size: {len(test_texts)}")

    print("\n" + "=" * 60)
    print(f"EVALUATING ON LOCKED TEST SET ({len(test_texts)} samples)")
    print("=" * 60)

    predictions = {
        "majority_baseline": baseline_majority(train_labels, test_texts),
        "random_baseline": baseline_random_stratified(train_labels, test_texts),
        "keyword_baseline": baseline_keyword(test_texts),
        "our_model": model.predict(test_texts).tolist(),
    }

    results = {}
    for name, preds in predictions.items():
        results[name] = report_predictor(name, test_labels, preds)

    print("\n" + "=" * 60)
    print("PAIRWISE McNEMAR TESTS (vs our model)")
    print("=" * 60)
    mcnemar_results = {}
    for name in ["majority_baseline", "random_baseline", "keyword_baseline"]:
        result = mcnemar_test(test_labels, predictions["our_model"], predictions[name])
        mcnemar_results[name] = result
        print(f"  our_model vs {name}:")
        print(f"    n_disagree={result['n_disagree']}, p-value={result['p_value']:.4f}")
        print(f"    verdict: {result['verdict']}")

    summary = {
        "test_size": len(test_texts),
        "n_classes": len(set(test_labels)),
        "predictors": results,
        "mcnemar_vs_our_model": mcnemar_results,
        "bootstrap_iters": BOOTSTRAP_ITERS,
        "seed": RNG_SEED,
    }
    out = model_dir / "metrics_test.json"
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"\nFull results saved to {out}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
