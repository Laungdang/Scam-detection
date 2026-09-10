"""
Fine-tune WangchanBERTa สำหรับ scam binary classifier

Model: airesearch/wangchanberta-base-att-spm-uncased
Pretrained บนข้อความไทยขนาดใหญ่ → adapt ดีกับ scam SMS ไทย

หมายเหตุ CPU: ใช้เวลา ~20-30 นาทีต่อ run (3 epochs, batch 8, 814 samples)
GPU จะลดเหลือ 3-5 นาที

วิธีใช้:
    python -m ml.train_bert --version v0.3.0-bert --epochs 3
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np
import torch
from sklearn.metrics import (
    accuracy_score, classification_report, confusion_matrix, f1_score,
    precision_score, recall_score,
)
from torch.utils.data import Dataset
from transformers import (
    AutoModelForSequenceClassification, AutoTokenizer,
    Trainer, TrainingArguments,
)


PROCESSED_DIR = Path("data/processed")
MODELS_DIR = Path("models")
DEFAULT_MODEL_NAME = "airesearch/wangchanberta-base-att-spm-uncased"


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


class ScamDataset(Dataset):
    def __init__(self, encodings: dict, labels: list[int]):
        self.encodings = encodings
        self.labels = labels

    def __len__(self):
        return len(self.labels)

    def __getitem__(self, idx):
        item = {k: torch.tensor(v[idx]) for k, v in self.encodings.items()}
        item["labels"] = torch.tensor(self.labels[idx])
        return item


def compute_metrics(eval_pred) -> dict:
    logits, labels = eval_pred
    preds = np.argmax(logits, axis=-1)
    return {
        "accuracy": accuracy_score(labels, preds),
        "f1_macro": f1_score(labels, preds, average="macro", zero_division=0),
        "precision_macro": precision_score(labels, preds, average="macro", zero_division=0),
        "recall_macro": recall_score(labels, preds, average="macro", zero_division=0),
    }


def eval_full(model, tokenizer, texts: list[str], labels: list[str],
              label_to_id: dict, id_to_label: dict, batch_size: int = 16) -> dict:
    """eval แบบมี classification_report + confusion matrix"""
    model.eval()
    all_preds = []
    with torch.no_grad():
        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i : i + batch_size]
            enc = tokenizer(batch_texts, truncation=True, padding=True,
                           max_length=256, return_tensors="pt")
            outputs = model(**enc)
            pred_ids = outputs.logits.argmax(dim=-1).tolist()
            all_preds.extend(pred_ids)

    pred_labels = [id_to_label[p] for p in all_preds]
    classes = sorted(label_to_id.keys())

    print(classification_report(labels, pred_labels, digits=3, zero_division=0))
    cm = confusion_matrix(labels, pred_labels, labels=classes)
    print(f"Confusion matrix (classes={classes}):\n{cm}")

    return {
        "size": len(texts),
        "accuracy": float(accuracy_score(labels, pred_labels)),
        "f1_macro": float(f1_score(labels, pred_labels, average="macro", zero_division=0)),
        "precision_macro": float(precision_score(labels, pred_labels, average="macro", zero_division=0)),
        "recall_macro": float(recall_score(labels, pred_labels, average="macro", zero_division=0)),
        "per_class": classification_report(labels, pred_labels, digits=4,
                                            zero_division=0, output_dict=True),
        "confusion_matrix": cm.tolist(),
        "classes": classes,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", default="v0.3.0-bert")
    parser.add_argument("--task", choices=["binary", "multi"], default="binary")
    parser.add_argument("--model-name", default=DEFAULT_MODEL_NAME)
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--lr", type=float, default=2e-5)
    parser.add_argument("--max-length", type=int, default=256)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    print(f"=== Fine-tune {args.model_name} ===")
    print(f"version={args.version} epochs={args.epochs} batch={args.batch_size} lr={args.lr}")
    print(f"device: {'cuda' if torch.cuda.is_available() else 'cpu'}")

    torch.manual_seed(args.seed)
    np.random.seed(args.seed)

    # load data
    train_texts, train_labels_str, train_records = load_split("train", task=args.task)
    val_texts, val_labels_str, _ = load_split("val", task=args.task)

    label_to_id = {lab: i for i, lab in enumerate(sorted(set(train_labels_str)))}
    id_to_label = {i: lab for lab, i in label_to_id.items()}
    train_labels = [label_to_id[l] for l in train_labels_str]
    val_labels = [label_to_id[l] for l in val_labels_str]
    print(f"classes: {label_to_id}")
    print(f"train: {len(train_texts)}, val: {len(val_texts)}")

    # tokenize
    print("Tokenizing ...")
    tokenizer = AutoTokenizer.from_pretrained(args.model_name)
    train_enc = tokenizer(train_texts, truncation=True, padding=True,
                          max_length=args.max_length)
    val_enc = tokenizer(val_texts, truncation=True, padding=True,
                        max_length=args.max_length)
    train_ds = ScamDataset(train_enc, train_labels)
    val_ds = ScamDataset(val_enc, val_labels)

    # model
    print(f"Loading model {args.model_name} ...")
    model = AutoModelForSequenceClassification.from_pretrained(
        args.model_name,
        num_labels=len(label_to_id),
        id2label=id_to_label,
        label2id=label_to_id,
    )

    output_dir = MODELS_DIR / args.version
    output_dir.mkdir(parents=True, exist_ok=True)

    training_args = TrainingArguments(
        output_dir=str(output_dir / "checkpoints"),
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size,
        per_device_eval_batch_size=args.batch_size * 2,
        learning_rate=args.lr,
        warmup_ratio=0.1,
        weight_decay=0.01,
        eval_strategy="epoch",
        save_strategy="epoch",
        load_best_model_at_end=True,
        metric_for_best_model="f1_macro",
        greater_is_better=True,
        logging_steps=20,
        seed=args.seed,
        report_to="none",
        save_total_limit=1,
        disable_tqdm=False,
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_ds,
        eval_dataset=val_ds,
        compute_metrics=compute_metrics,
    )

    start = time.time()
    trainer.train()
    train_time = time.time() - start
    print(f"\nTrained in {train_time:.0f}s ({train_time/60:.1f} min)")

    # save final model
    model_path = output_dir / "model"
    model.save_pretrained(str(model_path))
    tokenizer.save_pretrained(str(model_path))

    # full eval on train + val
    print("\n=== Final train metrics ===")
    train_metrics = eval_full(model, tokenizer, train_texts, train_labels_str,
                              label_to_id, id_to_label)
    print("\n=== Final val metrics ===")
    val_metrics = eval_full(model, tokenizer, val_texts, val_labels_str,
                            label_to_id, id_to_label)

    train_hash = hashlib.sha256(
        ("\n".join(sorted(r["id"] for r in train_records))).encode("utf-8")
    ).hexdigest()[:16]

    metadata = {
        "version": args.version,
        "model_type": "wangchanberta_finetuned",
        "task": args.task,
        "base_model": args.model_name,
        "hyperparameters": {
            "epochs": args.epochs,
            "batch_size": args.batch_size,
            "learning_rate": args.lr,
            "max_length": args.max_length,
            "random_seed": args.seed,
        },
        "label_to_id": label_to_id,
        "train": {
            "size": len(train_texts),
            "data_hash": train_hash,
            "duration_sec": round(train_time, 2),
        },
    }
    (output_dir / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2))
    (output_dir / "metrics_train.json").write_text(json.dumps(train_metrics, ensure_ascii=False, indent=2))
    (output_dir / "metrics_val.json").write_text(json.dumps(val_metrics, ensure_ascii=False, indent=2))

    print(f"\nSaved to {output_dir}/")
    print(f"  model/: HF model artifact (load with AutoModelForSequenceClassification.from_pretrained)")
    print(f"  metadata.json, metrics_*.json")
    print(f"\nVal macro-F1: {val_metrics['f1_macro']:.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
