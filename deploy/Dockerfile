# HI-Scammer — Q&A-only (RAG + LLM) บน Hugging Face Space (Docker, CPU free tier)
# โครงตาม HF recommended pattern: non-root uid 1000, app_port 7860 (ดู README front-matter)
FROM python:3.12-slim

# opencv (ใน easyocr) ต้องการ libgl/libglib
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    HF_HOME=/home/user/.cache/huggingface \
    PYTHONUNBUFFERED=1
WORKDIR /home/user/app

COPY --chown=user requirements.txt .
# torch CPU-only ก่อน (เล็กกว่า CUDA build หลาย GB) แล้วค่อยลงที่เหลือ
RUN pip install --no-cache-dir --user torch --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir --user -r requirements.txt

# Bake model weights ลง image — cold start ไม่ต้องโหลด bge-m3 2.2GB / EasyOCR ~100MB ใหม่
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-m3')"
RUN python -c "import easyocr; easyocr.Reader(['th','en'], gpu=False, verbose=False)"

COPY --chown=user . .

EXPOSE 7860
CMD ["bash", "start.sh"]
