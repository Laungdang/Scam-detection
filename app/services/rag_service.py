from functools import lru_cache

import chromadb
from chromadb.utils import embedding_functions

from app.config.settings import Settings
from app.utils.logger import get_logger

logger = get_logger("rag_service")

CHROMA_PATH = "data/chroma_db"
COLLECTION_NAME = "scam_cases"
EMBED_MODEL = Settings.RAG_EMBED_MODEL  # ต้องตรงกับที่ scripts/setup_rag.py ใช้ตอน embed
TOP_K = 3
SIMILARITY_THRESHOLD = Settings.RAG_SIMILARITY_THRESHOLD  # ต่ำกว่านี้ถือว่าไม่เกี่ยวข้อง ไม่ส่งให้ Claude


@lru_cache(maxsize=1)
def get_collection():
    ef = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name=EMBED_MODEL
    )
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    collection = client.get_collection(name=COLLECTION_NAME, embedding_function=ef)
    built_with = (collection.metadata or {}).get("embed_model")
    if built_with and built_with != EMBED_MODEL:
        # embedding คนละ space → similarity ไม่มีความหมาย ต้อง rebuild ไม่ใช่ใช้ต่อเงียบๆ
        raise RuntimeError(
            f"chroma ถูกสร้างด้วย {built_with} แต่ RAG_EMBED_MODEL={EMBED_MODEL} — "
            f"รัน python -m scripts.setup_rag ใหม่"
        )
    return collection


def retrieve_similar_cases(query: str, top_k: int = TOP_K) -> list[dict]:
    try:
        collection = get_collection()
        results = collection.query(query_texts=[query], n_results=top_k)

        cases = []
        for i in range(len(results["ids"][0])):
            meta = results["metadatas"][0][i]
            distance = results["distances"][0][i]
            similarity = round(1 - distance, 3)
            if similarity < SIMILARITY_THRESHOLD:
                continue  # ตัดเคสที่ไม่เกี่ยวข้องออก ไม่ส่งให้ Claude
            cases.append({
                "input_text": results["documents"][0][i],
                "scam_category": meta.get("scam_category", ""),
                # Data v2 metadata (provenance) — ไม่มี result_status/matched_pattern อีกแล้ว
                "tier": meta.get("tier", ""),
                "source_name": meta.get("source_name", "") or meta.get("data_source", ""),
                "url": meta.get("url", ""),
                "published_date": meta.get("published_date", ""),
                "similarity": similarity,
            })
        return cases

    except Exception as e:
        logger.warning(f"RAG retrieve failed: {e}")
        return []


def build_rag_context(cases: list[dict]) -> str:
    if not cases:
        return ""
    lines = ["ตัวอย่างเคสที่คล้ายกันจากฐานข้อมูล:"]
    for i, c in enumerate(cases, 1):
        # ส่งเฉพาะข้อเท็จจริงของเคส (ข้อความ + หมวด + ความคล้าย)
        # ห้ามส่ง result_status / matched_pattern ของเคสเก่า — เป็น verdict จาก schema เดิม
        # ที่จะ anchor Claude (CLAUDE.md 5.2 Anti-Bias)
        src = c.get("source_name") or "ไม่ระบุแหล่ง"
        date = c.get("published_date") or ""
        src_line = f"- แหล่ง: {src}" + (f" ({date})" if date else "")
        lines.append(
            f"\nเคสที่ {i} (ความคล้าย {c['similarity']}):\n"
            f"- ข้อความ: {c['input_text'][:300]}\n"
            f"- หมวดที่บันทึกไว้: {c['scam_category'] or 'ไม่ระบุ'}\n"
            f"{src_line}"
        )
    return "\n".join(lines)
