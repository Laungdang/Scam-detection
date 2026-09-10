# data/archive — Data v1 artifacts (2026-08-29)

เก็บไว้เพื่อ reproducibility ของผล v1 ใน thesis — **ห้ามใช้ train/eval v2**

| ไฟล์ | คืออะไร |
|---|---|
| scam_corpus.v1.jsonl | corpus ก่อน migrate เป็น tier schema |
| scam_corpus.before_relabel.jsonl | backup ก่อน Week 4 relabel experiment |
| relabel_proposals.jsonl | audit trail ของ LLM relabel (rollback แล้ว) |
| v1_rag_llm_generated__*.xlsx | RAG cases ชุดแรก — LLM (Claude) generate โดยอ้างชื่อสำนักข่าว ไม่มี URL, text/source ไม่ตรงกัน → จัดเป็น tier C, ถอดออกจาก chroma (CLAUDE.md 10.7) |
