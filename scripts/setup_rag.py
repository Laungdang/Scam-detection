"""
Setup RAG (Data v2): embed เคสจาก scam_corpus.jsonl ที่ **มี provenance** เข้า ChromaDB

CLAUDE.md 10.2 / 10.7:
- ใช้เฉพาะ record ที่ is_usable_for(r, "rag") → tier A (scam ไทยจริง), tier N (เคสเล่าเรื่องจากหน่วยงาน มี URL),
  tier S เฉพาะที่ไม่ใช่ Wisesight (social chat ไม่ช่วยตอบเรื่อง scam)
- ห้าม tier B/C (translated/synthetic) — และชุด xlsx เดิม (LLM-generated, fabricated attribution) ถูกถอดออกแล้ว
- metadata ต่อเคส: tier, category, source_name, url, published_date → Claude cite แหล่งจริงได้
- ข้อความผ่าน pii_masker strict ก่อน embed (tier N ยังไม่ mask ตอน scrape)

รัน: python -m scripts.setup_rag [--dry-run]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = open(sys.stdout.fileno(), mode="w", encoding="utf-8", buffering=1)

os.environ.setdefault("PII_SALT", "rag-setup-local")

import chromadb  # noqa: E402
from chromadb.utils import embedding_functions  # noqa: E402

from app.config.settings import Settings  # noqa: E402
from app.services.pii_masker import mask_pii  # noqa: E402
from ml.scrape.schema import is_usable_for  # noqa: E402
from ml.scrape.wp_news import is_low_value_narrative  # noqa: E402

CORPUS_PATH = Path("data/raw/scam_corpus.jsonl")
CHROMA_PATH = "data/chroma_db"
COLLECTION_NAME = "scam_cases"
EMBED_MODEL = Settings.RAG_EMBED_MODEL  # เดียวกับ app/services/rag_service.py
MAX_DOC_CHARS = 1200


def select_rag_records(records: list[dict]) -> tuple[list[dict], dict]:
    out, skipped = [], {"tier_rule": 0, "wisesight": 0, "low_value_narrative": 0}
    for r in records:
        if not is_usable_for(r, "rag"):
            skipped["tier_rule"] += 1
            continue
        if r["tier"] == "S" and "wisesight" in (r["source"].get("name") or "").lower():
            skipped["wisesight"] += 1
            continue
        if is_low_value_narrative(r):
            skipped["low_value_narrative"] += 1
            continue
        out.append(r)
    return out, skipped


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    records = [json.loads(l) for l in CORPUS_PATH.read_text(encoding="utf-8").splitlines() if l.strip()]
    selected, skipped = select_rag_records(records)
    print(f"corpus {len(records)} → RAG-eligible {len(selected)} (skipped: {skipped})")
    print(f"  embed model: {EMBED_MODEL}")
    print("  by tier:", dict(Counter(r["tier"] for r in selected)))
    print("  by source:", dict(Counter(r["source"]["name"][:40] for r in selected).most_common(8)))
    if args.dry_run:
        return 0

    client = chromadb.PersistentClient(path=CHROMA_PATH)
    ef = embedding_functions.SentenceTransformerEmbeddingFunction(model_name=EMBED_MODEL)
    try:
        client.delete_collection(COLLECTION_NAME)
        print("  ลบ collection เก่า (v1 xlsx cases) แล้ว")
    except Exception:
        pass
    collection = client.create_collection(
        name=COLLECTION_NAME,
        embedding_function=ef,
        metadata={"hnsw:space": "cosine", "embed_model": EMBED_MODEL, "data_version": "v2"},
    )

    ids, docs, metas = [], [], []
    for r in selected:
        doc = mask_pii(r["text"], mode="strict").masked[:MAX_DOC_CHARS]
        ids.append(r["id"])
        docs.append(doc)
        metas.append({
            "tier": r["tier"],
            "verdict": r["verdict"],
            "scam_category": r.get("category") or "",
            "source_name": r["source"].get("name") or "",
            "url": r["source"].get("url") or "",
            "published_date": (r["source"].get("published_date") or "")[:10],
            "snapshot_hash": r["source"].get("snapshot_hash") or "",
        })

    batch = 50
    for i in range(0, len(ids), batch):
        collection.add(ids=ids[i:i + batch], documents=docs[i:i + batch], metadatas=metas[i:i + batch])
        print(f"  embedded {min(i + batch, len(ids))}/{len(ids)}")

    print(f"\n✓ collection '{COLLECTION_NAME}' = {collection.count()} cases (ทุกเคสมี URL/provenance)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
