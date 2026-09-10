"""
Compare all trained models บน **locked test set**

โหลด model หลายตัว → eval ทุกตัวบน test set เดียวกัน → ตารางเปรียบเทียบ
+ McNemar test pairwise — เปรียบเทียบ statistical significance

ทำให้ thesis chapter "Model Comparison" defendable

วิธีใช้:
    python -m ml.compare_models --models v0.1.0 v0.2.0-xgb v0.3.0-bert
"""

from __future__ import annotations

import argparse
import json
import pickle
import sys
import time
from pathlib import Path

import numpy as np
from scipy.stats import binomtest
from sklearn.metrics import (
    accuracy_score, classification_report, confusion_matrix, f1_score,
)


PROCESSED_DIR = Path("data/processed")
MODELS_DIR = Path("models")
BOOTSTRAP_ITERS = 1000
RNG_SEED = 42


def load_test() -> tuple[list[str], list[str]]:
    texts, labels = [], []
    with (PROCESSED_DIR / "test.jsonl").open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            texts.append(r["text"])
            labels.append(r["verdict"])
    return texts, labels


def predict_sklearn(model_dir: Path, texts: list[str]) -> list[str]:
    """LogReg + XGBoost — sklearn pipeline"""
    with (model_dir / "model.pkl").open("rb") as f:
        obj = pickle.load(f)
    if isinstance(obj, dict) and "pipeline" in obj:
        # XGBoost: {pipeline, label_encoder}
        pipe = obj["pipeline"]
        encoder = obj["label_encoder"]
        preds_encoded = pipe.predict(texts)
        return encoder.inverse_transform(preds_encoded).tolist()
    # LogReg: bare sklearn pipeline
    return obj.predict(texts).tolist()


def predict_bert(model_dir: Path, texts: list[str]) -> list[str]:
    """WangchanBERTa — HF model"""
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    model_path = model_dir / "model"
    tok = AutoTokenizer.from_pretrained(str(model_path))
    model = AutoModelForSequenceClassification.from_pretrained(str(model_path))
    model.eval()

    id2label = model.config.id2label
    preds: list[str] = []
    batch_size = 16
    with torch.no_grad():
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            enc = tok(batch, truncation=True, padding=True, max_length=256, return_tensors="pt")
            out = model(**enc)
            ids = out.logits.argmax(dim=-1).tolist()
            preds.extend(id2label[i] for i in ids)
    return preds


def predict_model(version: str, texts: list[str]) -> list[str]:
    model_dir = MODELS_DIR / version
    metadata_path = model_dir / "metadata.json"
    if not metadata_path.exists():
        raise FileNotFoundError(f"{metadata_path} not found — train model first")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    model_type = metadata.get("model_type", "")
    if "bert" in model_type.lower() or "wangchan" in model_type.lower():
        return predict_bert(model_dir, texts)
    return predict_sklearn(model_dir, texts)


def bootstrap_ci(y_true: list[str], y_pred: list[str], metric_fn,
                 iters: int = BOOTSTRAP_ITERS, seed: int = RNG_SEED) -> tuple[float, float, float]:
    rng = np.random.default_rng(seed)
    n = len(y_true)
    point = metric_fn(y_true, y_pred)
    scores = []
    a, b = np.array(y_true), np.array(y_pred)
    for _ in range(iters):
        idx = rng.integers(0, n, size=n)
        try:
            scores.append(metric_fn(a[idx].tolist(), b[idx].tolist()))
        except Exception:
            continue
    return float(point), float(np.percentile(scores, 2.5)), float(np.percentile(scores, 97.5))


def macro_f1(y_true, y_pred) -> float:
    return f1_score(y_true, y_pred, average="macro", zero_division=0)


def mcnemar_pvalue(y_true: list[str], a: list[str], b: list[str]) -> dict:
    n_a, n_b = 0, 0
    for t, ap, bp in zip(y_true, a, b):
        a_ok = ap == t
        b_ok = bp == t
        if a_ok and not b_ok:
            n_a += 1
        elif not a_ok and b_ok:
            n_b += 1
    n = n_a + n_b
    if n == 0:
        return {"p_value": 1.0, "n_a_better": 0, "n_b_better": 0, "verdict": "tie"}
    p = float(binomtest(n_a, n, p=0.5).pvalue)
    return {
        "p_value": p,
        "n_a_better": n_a,
        "n_b_better": n_b,
        "verdict": "significant" if p < 0.05 else "not_significant",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", nargs="+", required=True,
                       help="model versions to compare, e.g. v0.1.0 v0.2.0-xgb v0.3.0-bert")
    parser.add_argument("--output", default="models/comparison_report.json")
    args = parser.parse_args()

    print(f"Loading test set ...")
    texts, labels = load_test()
    print(f"Test size: {len(texts)} (classes: {sorted(set(labels))})")

    results: dict[str, dict] = {}
    for ver in args.models:
        print(f"\n=== Predicting with {ver} ===")
        start = time.time()
        try:
            preds = predict_model(ver, texts)
        except FileNotFoundError as e:
            print(f"  SKIP: {e}")
            continue
        latency = time.time() - start

        acc, acc_low, acc_high = bootstrap_ci(labels, preds, accuracy_score)
        f1, f1_low, f1_high = bootstrap_ci(labels, preds, macro_f1)
        cm = confusion_matrix(labels, preds, labels=sorted(set(labels)))
        print(f"  acc      = {acc:.4f} [{acc_low:.4f}, {acc_high:.4f}]")
        print(f"  macro-F1 = {f1:.4f} [{f1_low:.4f}, {f1_high:.4f}]")
        print(f"  inference latency: {latency:.2f}s ({latency*1000/len(texts):.1f}ms/sample)")
        print(classification_report(labels, preds, digits=3, zero_division=0))
        results[ver] = {
            "predictions": preds,
            "accuracy": {"point": acc, "ci_low": acc_low, "ci_high": acc_high},
            "macro_f1": {"point": f1, "ci_low": f1_low, "ci_high": f1_high},
            "confusion_matrix": cm.tolist(),
            "per_class": classification_report(labels, preds, output_dict=True, zero_division=0),
            "inference_latency_total_sec": round(latency, 3),
            "inference_latency_ms_per_sample": round(latency * 1000 / len(texts), 2),
        }

    # pairwise McNemar
    print("\n" + "=" * 60)
    print("PAIRWISE McNEMAR (significance of differences)")
    print("=" * 60)
    pairs = {}
    versions = list(results.keys())
    for i in range(len(versions)):
        for j in range(i + 1, len(versions)):
            va, vb = versions[i], versions[j]
            mc = mcnemar_pvalue(labels, results[va]["predictions"], results[vb]["predictions"])
            pairs[f"{va} vs {vb}"] = mc
            print(f"  {va} vs {vb}: p={mc['p_value']:.4f} "
                  f"({va}_better={mc['n_a_better']}, {vb}_better={mc['n_b_better']}) "
                  f"→ {mc['verdict']}")

    # leaderboard
    print("\n" + "=" * 60)
    print("LEADERBOARD (sorted by macro-F1)")
    print("=" * 60)
    ranked = sorted(results.items(), key=lambda kv: -kv[1]["macro_f1"]["point"])
    print(f"  {'rank':4s} {'version':18s} {'macro-F1':10s} {'95% CI':22s} {'latency':12s}")
    for rank, (ver, r) in enumerate(ranked, 1):
        f1 = r["macro_f1"]
        lat = r["inference_latency_ms_per_sample"]
        print(f"  {rank:4d} {ver:18s} {f1['point']:.4f}     [{f1['ci_low']:.3f}, {f1['ci_high']:.3f}]   {lat:.1f}ms/req")

    # strip predictions before saving (large array)
    output_data = {
        "test_size": len(texts),
        "models": {
            v: {k: val for k, val in r.items() if k != "predictions"}
            for v, r in results.items()
        },
        "pairwise_mcnemar": pairs,
        "bootstrap_iters": BOOTSTRAP_ITERS,
        "seed": RNG_SEED,
    }
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(output_data, ensure_ascii=False, indent=2))
    print(f"\nSaved to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
