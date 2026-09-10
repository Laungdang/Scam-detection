"""
Train XGBoost classifier — comparison baseline

ใช้ feature pipeline เดิม (char TF-IDF + word TF-IDF + metadata)
เปลี่ยน estimator จาก LogReg → XGBoost
XGBoost ใช้สำหรับเปรียบเทียบ "shallow learning ที่ลึกกว่า LR แต่ไม่ใช่ neural"

วิธีใช้:
    python -m ml.train_xgboost --version v0.2.0-xgb
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pickle
import sys
import time
from pathlib import Path

from sklearn.metrics import (
    accuracy_score, classification_report, confusion_matrix, f1_score,
    precision_score, recall_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import LabelEncoder
from xgboost import XGBClassifier

from ml.features import build_feature_pipeline


PROCESSED_DIR = Path("data/processed")
MODELS_DIR = Path("models")


def label_for_task(record: dict, task: str) -> str:
    if task == "binary":
        return record["verdict"]
    if record["verdict"] == "safe":
        return "safe"
    return record.get("category") or "other"


def load_split(name: str, task: str = "binary") -> tuple[list[str], list[str], list[dict]]:
    base = PROCESSED_DIR / "multi" if task == "multi" else PROCESSED_DIR
    path = base / f"{name}.jsonl"
    texts, labels, records = [], [], []
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
    label_encoder: LabelEncoder,
    texts: list[str],
    labels: list[str],
    split_name: str,
) -> dict:
    preds_encoded = pipeline.predict(texts)
    preds = label_encoder.inverse_transform(preds_encoded).tolist()

    print(f"\n=== {split_name} performance ===")
    print(classification_report(labels, preds, digits=3, zero_division=0))
    print("Confusion matrix (rows=true, cols=pred):")
    classes = label_encoder.classes_.tolist()
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
    parser.add_argument("--version", default="v0.2.0-xgb")
    parser.add_argument("--task", choices=["binary", "multi"], default="binary")
    parser.add_argument("--n-estimators", type=int, default=300)
    parser.add_argument("--max-depth", type=int, default=6)
    parser.add_argument("--learning-rate", type=float, default=0.1)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    print(f"Training XGBoost classifier {args.version} (task={args.task}) ...")
    train_texts, train_labels, train_records = load_split("train", task=args.task)
    val_texts, val_labels, _ = load_split("val", task=args.task)
    print(f"Train: {len(train_texts)} | Val: {len(val_texts)}")

    label_encoder = LabelEncoder()
    y_train = label_encoder.fit_transform(train_labels)

    from collections import Counter
    counts = Counter(train_labels)
    classes = label_encoder.classes_.tolist()

    if args.task == "binary" and len(classes) == 2:
        scale_pos_weight = counts[classes[0]] / counts[classes[1]]
        objective = "binary:logistic"
        eval_metric = "logloss"
        print(f"  binary: classes={classes}, scale_pos_weight={scale_pos_weight:.3f}")
        extra_args = {"scale_pos_weight": scale_pos_weight}
    else:
        # multi-class: XGBoost ใช้ sample_weight แทน scale_pos_weight
        # คำนวณ inverse frequency weight per sample
        total = len(train_labels)
        n_classes = len(classes)
        class_weights = {c: total / (n_classes * counts[c]) for c in classes}
        sample_weight = [class_weights[lab] for lab in train_labels]
        objective = "multi:softprob"
        eval_metric = "mlogloss"
        print(f"  multi: {n_classes} classes={classes}")
        extra_args = {}

    pipeline = Pipeline([
        ("features", build_feature_pipeline()),
        ("classifier", XGBClassifier(
            n_estimators=args.n_estimators,
            max_depth=args.max_depth,
            learning_rate=args.learning_rate,
            objective=objective,
            eval_metric=eval_metric,
            random_state=args.seed,
            n_jobs=-1,
            tree_method="hist",
            **extra_args,
        )),
    ])

    start = time.time()
    if args.task == "multi":
        pipeline.fit(train_texts, y_train, classifier__sample_weight=sample_weight)
    else:
        pipeline.fit(train_texts, y_train)
    train_time = time.time() - start
    print(f"Trained in {train_time:.1f}s")

    train_metrics = evaluate_on_split(pipeline, label_encoder, train_texts, train_labels, "train")
    val_metrics = evaluate_on_split(pipeline, label_encoder, val_texts, val_labels, "val")

    model_dir = MODELS_DIR / args.version
    model_dir.mkdir(parents=True, exist_ok=True)
    with (model_dir / "model.pkl").open("wb") as f:
        pickle.dump({"pipeline": pipeline, "label_encoder": label_encoder}, f)

    train_hash = hashlib.sha256(
        ("\n".join(sorted(r["id"] for r in train_records))).encode("utf-8")
    ).hexdigest()[:16]

    metadata = {
        "version": args.version,
        "model_type": "xgboost",
        "task": args.task,
        "hyperparameters": {
            "n_estimators": args.n_estimators,
            "max_depth": args.max_depth,
            "learning_rate": args.learning_rate,
            "objective": objective,
            "tree_method": "hist",
            "random_seed": args.seed,
        },
        "feature_pipeline": [
            "char_tfidf (ngram 2-4, max 5000)",
            "word_tfidf (PyThaiNLP newmm, ngram 1-2, max 3000)",
            "metadata (14 numeric features)",
        ],
        "classes": classes,
        "train": {
            "size": len(train_texts),
            "data_hash": train_hash,
            "duration_sec": round(train_time, 2),
        },
    }
    (model_dir / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2))
    (model_dir / "metrics_train.json").write_text(json.dumps(train_metrics, ensure_ascii=False, indent=2))
    (model_dir / "metrics_val.json").write_text(json.dumps(val_metrics, ensure_ascii=False, indent=2))

    print(f"\nSaved to {model_dir}/")
    print(f"Val macro-F1: {val_metrics['f1_macro']:.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
