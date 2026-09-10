"""
Deploy Q&A-only app ขึ้น Hugging Face Space (Docker) ด้วยคำสั่งเดียว

    python scripts/deploy_hf.py --space <hf-username>/hi-scammer
    python scripts/deploy_hf.py --space <hf-username>/hi-scammer --dry-run   # แค่ประกอบไฟล์ ไม่อัพโหลด

ทำอะไรบ้าง:
1. ประกอบ staging dir (.deploy_hf/) — เฉพาะไฟล์ runtime: app/, alembic/, lexicon, chroma_db
   (ไม่รวม corpus/thesis/ml/ — Space เป็น public repo)
2. สร้าง Space ถ้ายังไม่มี (docker SDK) + อัพโหลดแบบ mirror (ไฟล์ที่หายไปถูกลบจาก Space)
3. ตั้ง secrets จาก .env: CLAUDE_API_KEY, DATABASE_URL, PII_SALT, APP_ACCESS_CODE
4. restart Space ให้ build ใหม่

Token: --token > env HF_TOKEN > HUGGINGFACE_API_TOKEN ใน .env > ถามทาง terminal
(ต้องเป็น token ชนิด write — สร้างที่ huggingface.co/settings/tokens)
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGING = ROOT / ".deploy_hf"

# (source ใน repo, ปลายทางใน Space) — Space เป็น public: ห้ามใส่ .env / corpus / thesis
COPY_DIRS = [
    ("app", "app"),
    ("alembic", "alembic"),
    ("data/lexicon", "data/lexicon"),
    ("data/chroma_db", "data/chroma_db"),
]
COPY_FILES = [
    ("alembic.ini", "alembic.ini"),
    ("deploy/Dockerfile", "Dockerfile"),
    ("deploy/requirements.txt", "requirements.txt"),
    ("deploy/start.sh", "start.sh"),
    ("deploy/README_space.md", "README.md"),
]
REQUIRED_SECRETS = ["CLAUDE_API_KEY", "DATABASE_URL", "PII_SALT", "APP_ACCESS_CODE"]
OPTIONAL_SECRETS = ["QA_RATE_LIMIT_PER_MINUTE", "QA_RATE_LIMIT_PER_DAY"]


def assemble_staging() -> None:
    if STAGING.exists():
        shutil.rmtree(STAGING)
    STAGING.mkdir()
    for src, dst in COPY_DIRS:
        shutil.copytree(
            ROOT / src,
            STAGING / dst,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".env"),
        )
    for src, dst in COPY_FILES:
        (STAGING / dst).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / src, STAGING / dst)
    # start.sh ต้องเป็น LF — เขียนซ้ำกันเหนียว (เผื่อ git บนเครื่องแปลงเป็น CRLF)
    sh = STAGING / "start.sh"
    sh.write_bytes(sh.read_bytes().replace(b"\r\n", b"\n"))


def staging_summary() -> tuple[int, float]:
    files = [p for p in STAGING.rglob("*") if p.is_file()]
    return len(files), sum(p.stat().st_size for p in files) / 1e6


def load_env() -> dict[str, str]:
    from dotenv import dotenv_values

    return {k: v for k, v in dotenv_values(ROOT / ".env").items() if v}


def resolve_token(arg_token: str | None, env: dict[str, str]) -> str:
    import os

    token = arg_token or os.getenv("HF_TOKEN") or env.get("HF_TOKEN") or env.get("HUGGINGFACE_API_TOKEN")
    if not token:
        import getpass

        token = getpass.getpass("Hugging Face token (write): ").strip()
    if not token:
        sys.exit("ต้องมี HF token — สร้างที่ https://huggingface.co/settings/tokens (ชนิด write)")
    return token


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--space", required=True, help="เช่น username/hi-scammer")
    parser.add_argument("--token", default=None)
    parser.add_argument("--dry-run", action="store_true", help="ประกอบ staging อย่างเดียว ไม่อัพโหลด")
    args = parser.parse_args()

    env = load_env()
    missing = [k for k in REQUIRED_SECRETS if not env.get(k)]
    if missing and not args.dry_run:
        sys.exit(
            f"ขาดค่าใน .env: {', '.join(missing)}\n"
            "- DATABASE_URL = connection string จาก Neon (ต้องมี ?sslmode=require)\n"
            "- APP_ACCESS_CODE = รหัสที่จะแจกผู้ทดลอง (บังคับ — Space เป็น public URL)"
        )

    print("[1/4] ประกอบ staging...")
    assemble_staging()
    n, mb = staging_summary()
    print(f"      {n} ไฟล์, {mb:.1f} MB -> {STAGING}")

    if args.dry_run:
        print("dry-run จบ — ตรวจไฟล์ใน .deploy_hf/ ได้เลย")
        return

    from huggingface_hub import HfApi

    api = HfApi(token=resolve_token(args.token, env))
    who = api.whoami()["name"]
    print(f"[2/4] เข้าสู่ระบบเป็น {who} — สร้าง/เช็ค Space {args.space}...")
    api.create_repo(args.space, repo_type="space", space_sdk="docker", exist_ok=True)

    print("[3/4] อัพโหลด (mirror)... chroma_db ~32MB อาจใช้เวลาสักพัก")
    api.upload_folder(
        folder_path=str(STAGING),
        repo_id=args.space,
        repo_type="space",
        commit_message="deploy Q&A-only pilot",
        delete_patterns=["**"],
    )

    print("[4/4] ตั้ง secrets + restart...")
    for key in REQUIRED_SECRETS + [k for k in OPTIONAL_SECRETS if env.get(k)]:
        api.add_space_secret(args.space, key, env[key])
    api.restart_space(args.space)

    owner, name = args.space.split("/", 1)
    sub = f"{owner}-{name}".lower().replace("_", "-").replace(".", "-")
    print(
        f"\nเสร็จ! ดู build log: https://huggingface.co/spaces/{args.space}\n"
        f"แอพจะอยู่ที่: https://{sub}.hf.space (build ครั้งแรก ~15-25 นาที เพราะอบ bge-m3 ลง image)"
    )


if __name__ == "__main__":
    main()
