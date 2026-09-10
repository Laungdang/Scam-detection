"""
Train baseline scam classifier — TF-IDF + Logistic Regression

หลักการ (ดู CLAUDE.md Section 4.4-4.6):
- Baseline = TF-IDF + LR ทำหน้าที่เป็น "lower bound" ใน thesis
- Fit feature pipeline บน train เท่านั้น (no val/test leakage)
- class_weight='balanced' เพื่อจัดการ imbalance (664 scam / 500 safe)
- Save model + pipeline + metadata เป็น versioned artifact

วิธีใช้:
    python -m ml.train --version v0.1.0
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pickle
import sys
import time
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score, classification_report, confusion_matrix, f1_score,
    precision_score, recall_score,
)
from sklearn.pipeline import Pipeline

from ml.features import build_feature_pipeline


PROCESSED_DIR = Path("data/processed")
MODELS_DIR = Path("models")


def label_for_task(record: dict, task: str) -> str:
    if task == "binary":
        return record["verdict"]
    if record["verdict"] == "safe":
        return "safe"
    return record.get("category") or "other"


def load_split(name: str, task: str = "binary", base_dir: Path | None = None) -> tuple[list[str], list[str], list[dict]]:
    base = base_dir if base_dir is not None else (PROCESSED_DIR / "multi" if task == "multi" else PROCESSED_DIR)
    path = base / f"{name}.jsonl"
    texts: list[str] = []
    labels: list[str] = []
    records: list[dict] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            texts.append(r["text"])
            labels.append(label_for_task(r, task))
            records.append(r)
    return texts, labels, records


def evaluate_on_split(
    pipeline: Pipeline,
    texts: list[str],
    labels: list[str],
    split_name: str,
) -> dict:
    preds = pipeline.predict(texts)
    proba = pipeline.predict_proba(texts) if hasattr(pipeline, "predict_proba") else None

    print(f"\n=== {split_name} performance ===")
    print(classification_report(labels, preds, digits=3, zero_division=0))
    print("Confusion matrix (rows=true, cols=pred):")
    classes = pipeline.classes_.tolist()
    cm = confusion_matrix(labels, preds, labels=classes)
    print(f"  classes: {classes}")
    print(cm)

    return {
        "split": split_name,
        "size": len(texts),
        "accuracy": float(accuracy_score(labels, preds)),
        "f1_macro": float(f1_score(labels, preds, average="macro", zero_division=0)),
        "precision_macro": float(precision_score(labels, preds, average="macro", zero_division=0)),
        "recall_macro": float(recall_score(labels, preds, average="macro", zero_division=0)),
        "per_class": classification_report(
            labels, preds, digits=4, zero_division=0, output_dict=True
        ),
        "confusion_matrix": cm.tolist(),
        "classes": classes,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", default="v0.1.0", help="model version (semver)")
    parser.add_argument("--task", choices=["binary", "multi"], default="binary")
    parser.add_argument("--C", type=float, default=1.0, help="LogReg regularization (inverse)")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    print(f"Training baseline classifier {args.version} (task={args.task}) ...")
    train_texts, train_labels, train_records = load_split("train", task=args.task)
    val_texts, val_labels, _ = load_split("val", task=args.task)
    print(f"Train: {len(train_texts)} | Val: {len(val_texts)}")
    print(f"Classes: {sorted(set(train_labels))}")

    # multi-class ใช้ lbfgs (liblinear ไม่ support multinomial); binary ใช้ liblinear (เร็วกว่า)
    solver = "lbfgs" if args.task == "multi" else "liblinear"
    pipeline = Pipeline([
        ("features", build_feature_pipeline()),
        ("classifier", LogisticRegression(
            C=args.C,
            class_weight="balanced",
            max_iter=2000,
            random_state=args.seed,
            solver=solver,
        )),
    ])

    start = time.time()
    pipeline.fit(train_texts, train_labels)
    train_time = time.time() - start
    print(f"Trained in {train_time:.1f}s")

    train_metrics = evaluate_on_split(pipeline, train_texts, train_labels, "train")
    val_metrics = evaluate_on_split(pipeline, val_texts, val_labels, "val")

    model_dir = MODELS_DIR / args.version
    model_dir.mkdir(parents=True, exist_ok=True)
    with (model_dir / "model.pkl").open("wb") as f:
        pickle.dump(pipeline, f)

    train_hash = hashlib.sha256(
        ("\n".join(sorted(r["id"] for r in train_records))).encode("utf-8")
    ).hexdigest()[:16]

    metadata = {
        "version": args.version,
        "model_type": "tfidf_logreg_baseline",
        "task": args.task,
        "hyperparameters": {
            "C": args.C,
            "class_weight": "balanced",
            "solver": solver,
            "max_iter": 2000,
            "random_seed": args.seed,
        },
        "feature_pipeline": [
            "char_tfidf (ngram 2-4, max 5000 feats)",
            "word_tfidf (PyThaiNLP newmm, ngram 1-2, max 3000 feats)",
            "metadata (14 numeric features)",
        ],
        "classes": pipeline.classes_.tolist(),
        "train": {
            "size": len(train_texts),
            "data_hash": train_hash,
            "duration_sec": round(train_time, 2),
        },
    }
    (model_dir / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2))
    (model_dir / "metrics_train.json").write_text(json.dumps(train_metrics, ensure_ascii=False, indent=2))
    (model_dir / "metrics_val.json").write_text(json.dumps(val_metrics, ensure_ascii=False, indent=2))

    print(f"\nSaved model to {model_dir}/")
    print(f"  metadata.json, model.pkl, metrics_train.json, metrics_val.json")
    print(f"\nVal macro-F1: {val_metrics['f1_macro']:.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
