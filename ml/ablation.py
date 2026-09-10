"""
Week 3 Ablation Study — quantify contribution of each data source

Question: ปริมาณข้อมูลแต่ละ set (A/B/C) มีผลต่อ generalization บน real Thai scam แค่ไหน?

Setup:
- **Test set ตั้งคงที่ (fixed seed)** = 50% of Set A scam + matched safe sample
  ทดสอบ generalization "real Thai" — เป็น gold standard
- **Train scenarios (binary task — scam vs safe):**
  - A only        — เฉพาะ verbatim Thai (small but real)
  - A + B         — + translated English (cross-lingual)
  - A + B + C     — + synthetic Typhoon (full)
  - C only        — synthetic เท่านั้น (no real Thai)
- Safe class: shared across scenarios — Wisesight train pool (fixed)
- Model: Logistic Regression (เร็ว, defendable baseline)

วิธีใช้:
    python -m ml.ablation
"""

from __future__ import annotations

import hashlib
import json
import sys
import time
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
from scipy.stats import binomtest
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score, classification_report, confusion_matrix, f1_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

from ml.features import build_feature_pipeline


CORPUS_PATH = Path("data/raw/scam_corpus.jsonl")
REPORTS_DIR = Path("models/ablation")
RANDOM_SEED = 42
BOOTSTRAP_ITERS = 1000

# Source group definitions
SOURCE_SETS = {
    "A_thai_verbatim": [
        "Police Region 9",
        "Ngern Tid Lor",
        "Anti Fake News Center",
        "Bangkok Biznews",
        "IMC 2025 Smishing Dataset (Fishing for Smishing)",
    ],
    "B_translated": ["IMC 2025 Smishing Dataset (English-translated to Thai)"],
    "C_synthetic": ["Typhoon Synthetic (SCB 10X, few-shot from Set A)"],
    "safe_baseline": ["PyThaiNLP Wisesight Sentiment (CC0)"],
}


@dataclass
class ScenarioResult:
    name: str
    train_size: int
    train_composition: dict
    test_size: int
    accuracy: float
    accuracy_ci: tuple[float, float]
    macro_f1: float
    macro_f1_ci: tuple[float, float]
    per_class: dict
    confusion_matrix: list
    predictions: list[str]


def _source_group(source_name: str) -> str | None:
    for group, names in SOURCE_SETS.items():
        if any(prefix in source_name for prefix in names):
            return group
    return None


def load_corpus() -> list[dict]:
    records = []
    with CORPUS_PATH.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                r = json.loads(line)
                r["_group"] = _source_group(r["source"]["name"])
                records.append(r)
    return records


def split_test_holdout(records: list[dict], seed: int = RANDOM_SEED):
    """แยก test set (real Thai held-out) — fixed across all scenarios

    Test = 50% ของ Set A scam + matched safe sample
    Train pool = อีก 50% ของ A + ทุก B/C + ส่วนที่เหลือของ safe
    """
    set_a = [r for r in records if r["_group"] == "A_thai_verbatim"]
    safe = [r for r in records if r["_group"] == "safe_baseline"]

    a_train, a_test = train_test_split(set_a, test_size=0.5, random_state=seed)

    n_safe_test = min(len(a_test) * 2, len(safe) // 5)
    safe_pool, safe_test = train_test_split(safe, test_size=n_safe_test, random_state=seed)

    return {
        "a_train_pool": a_train,
        "a_test": a_test,
        "safe_pool": safe_pool,
        "safe_test": safe_test,
    }


def make_train_scenario(name: str, parts: dict, all_records: list[dict]) -> list[dict]:
    """build train data ตาม scenario"""
    train = []
    if "A" in name:
        train.extend(parts["a_train_pool"])
    if "B" in name:
        train.extend([r for r in all_records if r["_group"] == "B_translated"])
    if "C" in name:
        train.extend([r for r in all_records if r["_group"] == "C_synthetic"])
    # safe class: always shared (else can't do binary)
    train.extend(parts["safe_pool"])
    return train


def bootstrap_ci(y_true, y_pred, metric_fn, iters=BOOTSTRAP_ITERS, seed=RANDOM_SEED):
    rng = np.random.default_rng(seed)
    n = len(y_true)
    a, b = np.array(y_true), np.array(y_pred)
    scores = []
    for _ in range(iters):
        idx = rng.integers(0, n, size=n)
        try:
            scores.append(metric_fn(a[idx].tolist(), b[idx].tolist()))
        except Exception:
            continue
    return (
        float(metric_fn(y_true, y_pred)),
        float(np.percentile(scores, 2.5)),
        float(np.percentile(scores, 97.5)),
    )


def macro_f1(y_true, y_pred):
    return f1_score(y_true, y_pred, average="macro", zero_division=0)


def train_eval_scenario(
    name: str,
    train_records: list[dict],
    test_records: list[dict],
    seed: int = RANDOM_SEED,
) -> ScenarioResult:
    train_texts = [r["text"] for r in train_records]
    train_labels = [r["verdict"] for r in train_records]
    test_texts = [r["text"] for r in test_records]
    test_labels = [r["verdict"] for r in test_records]

    composition = Counter(r["_group"] for r in train_records)
    print(f"\n=== Scenario: {name} ===")
    print(f"  Train size: {len(train_texts)} | composition: {dict(composition)}")
    print(f"  Test size:  {len(test_texts)} | verdicts: {dict(Counter(test_labels))}")

    if len(set(train_labels)) < 2:
        print(f"  SKIP: only one class in train ({set(train_labels)})")
        return None

    pipeline = Pipeline([
        ("features", build_feature_pipeline()),
        ("classifier", LogisticRegression(
            C=1.0, class_weight="balanced", max_iter=2000,
            solver="liblinear", random_state=seed,
        )),
    ])

    start = time.time()
    pipeline.fit(train_texts, train_labels)
    train_time = time.time() - start

    preds = pipeline.predict(test_texts).tolist()
    acc, acc_low, acc_high = bootstrap_ci(test_labels, preds, accuracy_score)
    f1, f1_low, f1_high = bootstrap_ci(test_labels, preds, macro_f1)

    print(f"  Trained in {train_time:.1f}s")
    print(f"  Accuracy   = {acc:.4f}  [95% CI {acc_low:.4f}, {acc_high:.4f}]")
    print(f"  Macro-F1   = {f1:.4f}  [95% CI {f1_low:.4f}, {f1_high:.4f}]")
    print(classification_report(test_labels, preds, digits=3, zero_division=0))

    return ScenarioResult(
        name=name,
        train_size=len(train_texts),
        train_composition=dict(composition),
        test_size=len(test_texts),
        accuracy=acc,
        accuracy_ci=(acc_low, acc_high),
        macro_f1=f1,
        macro_f1_ci=(f1_low, f1_high),
        per_class=classification_report(test_labels, preds, output_dict=True, zero_division=0),
        confusion_matrix=confusion_matrix(test_labels, preds, labels=sorted(set(test_labels))).tolist(),
        predictions=preds,
    )


def mcnemar(y_true, a, b) -> dict:
    n_a, n_b = 0, 0
    for t, ap, bp in zip(y_true, a, b):
        if ap == t and bp != t: n_a += 1
        elif bp == t and ap != t: n_b += 1
    n = n_a + n_b
    if n == 0:
        return {"p_value": 1.0, "n_a_better": 0, "n_b_better": 0}
    p = float(binomtest(n_a, n, p=0.5).pvalue)
    return {"p_value": p, "n_a_better": n_a, "n_b_better": n_b}


def main() -> int:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    print("Loading corpus ...")
    records = load_corpus()
    print(f"Total: {len(records)} records")
    print(f"By source group: {dict(Counter(r['_group'] for r in records))}")

    parts = split_test_holdout(records)
    test_set = parts["a_test"] + parts["safe_test"]
    print(f"\nHeld-out test (real Thai + matched safe):")
    print(f"  A scam (Thai verbatim): {len(parts['a_test'])}")
    print(f"  Safe:                    {len(parts['safe_test'])}")
    print(f"  Total:                   {len(test_set)}")

    scenarios = {
        "A_only":   ["A"],
        "A_plus_B": ["A", "B"],
        "A_plus_B_plus_C": ["A", "B", "C"],
        "C_only":   ["C"],
    }

    results = {}
    for name, parts_used in scenarios.items():
        train = make_train_scenario("".join(parts_used), parts, records)
        result = train_eval_scenario(name, train, test_set)
        if result:
            results[name] = result

    print("\n" + "=" * 70)
    print("ABLATION LEADERBOARD (test = real Thai held-out, n={})".format(len(test_set)))
    print("=" * 70)
    print(f"{'scenario':22s}  {'train':>7s}  {'macro-F1':>10s}  {'95% CI':>22s}")
    for name, r in sorted(results.items(), key=lambda kv: -kv[1].macro_f1):
        ci = f"[{r.macro_f1_ci[0]:.3f}, {r.macro_f1_ci[1]:.3f}]"
        print(f"  {name:20s}  {r.train_size:>7d}  {r.macro_f1:>10.4f}  {ci:>22s}")

    print("\n" + "=" * 70)
    print("PAIRWISE McNEMAR")
    print("=" * 70)
    test_labels = [r["verdict"] for r in test_set]
    pairs = {}
    names = list(results.keys())
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            na, nb = names[i], names[j]
            mc = mcnemar(test_labels, results[na].predictions, results[nb].predictions)
            pairs[f"{na} vs {nb}"] = mc
            sig = "*" if mc["p_value"] < 0.05 else " "
            print(f"  {na:20s} vs {nb:20s}: p={mc['p_value']:.4f}  "
                  f"({na}_better={mc['n_a_better']}, {nb}_better={mc['n_b_better']}) {sig}")

    out = {
        "test_size": len(test_set),
        "test_composition": {
            "thai_scam_verbatim": len(parts["a_test"]),
            "safe": len(parts["safe_test"]),
        },
        "scenarios": {
            n: {**asdict(r), "predictions": None}  # strip predictions
            for n, r in results.items()
        },
        "pairwise_mcnemar": pairs,
        "bootstrap_iters": BOOTSTRAP_ITERS,
        "seed": RANDOM_SEED,
    }
    report_path = REPORTS_DIR / "ablation_report.json"
    report_path.write_text(json.dumps(out, ensure_ascii=False, indent=2))
    print(f"\nSaved to {report_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
