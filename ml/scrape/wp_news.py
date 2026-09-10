"""
WP News Scraper — ดึงบทความเตือนภัยจากเว็บหน่วยงานรัฐ (WordPress REST API) เป็น tier N (narrative)

แหล่ง (CLAUDE.md 10.6):
- AFNC  ศูนย์ต่อต้านข่าวปลอม — หมวด "อาชญากรรมออนไลน์" (category 8466, ~1,150 บทความ)
- ThaiCERT — หมวด "ข่าวสารภัยคุกคามทางไซเบอร์" (category 10, ~2,150 บทความ, กรองเฉพาะที่เกี่ยว scam)

ทั้งคู่ robots.txt อนุญาต (เช็ค 2026-08-29) และเปิด /wp-json/wp/v2/posts — ใช้ API แทน scrape HTML
→ ได้ content สะอาด + วันที่เผยแพร่ + link ถาวร

Provenance (CLAUDE.md 10.3):
- ทุก record มี source.url (link ถาวรของโพสต์) + snapshot_hash = sha256(content.rendered)
- raw JSON ของโพสต์เก็บที่ data/raw/snapshots/wp/{site}/{post_id}.json (gitignored)

Output:
- tier N records → append เข้า data/raw/scam_corpus.jsonl (ใช้กับ RAG เท่านั้น ห้าม train — is_usable_for)
- ข้อความใน “เครื่องหมายคำพูด” → data/raw/sources/wp_quote_candidates.jsonl
  (candidate tier A — **ต้องมีคนเปิด URL ยืนยัน** ก่อน append ตาม ANNOTATION_GUIDELINE ข้อ 4)
- image URL ในบทความ (screenshot SMS) → เก็บใน annotator_notes เพื่อทำ verbatim_ocr ภายหลัง

รัน:
  python -m ml.scrape.wp_news --site afnc --max-pages 2 --dry-run
  python -m ml.scrape.wp_news --site all --since 2024-01-01
"""

from __future__ import annotations

import argparse
import html
import json
import re
import time
from pathlib import Path

import requests

from ml.scrape.schema import (
    Annotation,
    AnnotationLabel,
    PiiInfo,
    ScamRecord,
    SourceAttribution,
    append_records,
    make_id,
    now_iso,
    snapshot_hash,
)


CORPUS_PATH = Path("data/raw/scam_corpus.jsonl")
QUOTES_PATH = Path("data/raw/sources/wp_quote_candidates.jsonl")
SNAPSHOT_DIR = Path("data/raw/snapshots/wp")
USER_AGENT = "scam-detection-thesis/0.1 (academic research; Thai scam corpus; +github repo)"
PAGE_SLEEP_SEC = 0.8
MAX_BODY_CHARS = 1500

SITES: dict[str, dict] = {
    "afnc": {
        "name": "Anti Fake News Center Thailand (DES Ministry)",
        "slug": "afnc",
        "base": "https://www.antifakenewscenter.com",
        "categories": [8466],  # อาชญากรรมออนไลน์
        "require_scam_keyword": False,  # หมวดนี้เป็น scam ทั้งหมดอยู่แล้ว
        # boilerplate ท้ายทุกโพสต์
        "strip_after": r"ช่องทางการติดตามและแจ้งเบาะแสข่าวปลอม",
    },
    "thaicert": {
        "name": "ThaiCERT (NCSA)",
        "slug": "thaicert",
        "base": "https://www.thaicert.or.th",
        "categories": [10],  # ข่าวสารภัยคุกคามทางไซเบอร์ — ปนข่าว vuln/malware ต้องกรอง
        "require_scam_keyword": True,
        "strip_after": None,
        # ข่าวเทคนิค (ช่องโหว่/มัลแวร์/แพตช์) ไม่ใช่ consumer scam → ตัดจาก title
        "exclude_title": re.compile(
            r"ช่องโหว่|CVE-|แพตช์|patch|ransomware|แรนซัมแวร์|มัลแวร์|malware|backdoor|"
            r"\bnpm\b|PyPI|GitHub|Linux|Windows|Cisco|Fortinet|VMware|zero-?day|exploit|DDoS|"
            r"\bAPT\b|botnet|บอตเน็ต|firmware|เฟิร์มแวร์|Chrome|Android|iOS\b|spyware|สปายแวร์|"
            r"เซิร์ฟเวอร์|server|plugin|ปลั๊กอิน|เราเตอร์|router",
            re.I,
        ),
    },
}

SCAM_KEYWORDS = re.compile(
    r"มิจฉาชีพ|มิจฯ|หลอก|ปลอม|แก๊ง|คอลเซ็นเตอร์|โกง|ฟิชชิ่ง|phishing|smishing|scam|"
    r"ตุ๋น|ลวง|แอบอ้าง|สวมรอย|เหยื่อ|ดูดเงิน|แอปดูดเงิน|ลิงก์ผี|บัญชีม้า",
    re.IGNORECASE,
)

# หมวดจาก keyword — ลำดับสำคัญ (แรกที่ match ชนะ) — โปร่งใส: resolved_by = keyword_rule
CATEGORY_RULES: list[tuple[str, re.Pattern]] = [
    ("investment_scam", re.compile(r"ลงทุน|หุ้น|คริปโต|เทรด|forex|ผลตอบแทน|งานออนไลน์|กดไลค์|รีวิวสินค้า", re.I)),
    ("loan_offer", re.compile(r"เงินกู้|สินเชื่อ|กู้เงิน|ปล่อยกู้", re.I)),
    ("romance_scam", re.compile(r"โรแมนซ์|romance|ความรัก|หลอกรัก|ทักผิด|ตีสนิท", re.I)),
    ("borrowing_scam", re.compile(r"ยืมเงิน|เปลี่ยนเบอร์|อ้างเป็นญาติ|อ้างเป็นเพื่อน|อ้างเป็นลูก|อ้างเป็นหลาน", re.I)),
    ("prize_scam", re.compile(r"รางวัล|ผู้โชคดี|เงินคืน|คืนเงิน|ของฟรี|ซิมฟรี|เงินเยียวยา|ลงทะเบียนรับ", re.I)),
    ("impersonation_authority", re.compile(r"อ้างเป็นเจ้าหน้าที่|แอบอ้างหน่วยงาน|ตำรวจ|DSI|สรรพากร|ปปง|ศาล|หมายจับ|คดี|กสทช|ไปรษณีย์|การไฟฟ้า|กรม|กระทรวง|call ?center|คอลเซ็นเตอร์", re.I)),
    ("phishing_link", re.compile(r"ลิงก์|link|SMS|เว็บปลอม|เว็บไซต์ปลอม|แอปปลอม|ดูดเงิน|OTP|กดลิงก์|ฟิชชิ่ง|phishing", re.I)),
    ("financial_fraud", re.compile(r"โอนเงิน|ซื้อของ|พรีออเดอร์|ขายของ|หลอกขาย|มัดจำ|บัญชีม้า|โอนผิด", re.I)),
]

# บทความที่ "มีที่มา" แต่ค่าต่ำสำหรับ RAG (วัด 2026-08-29):
# - AFNC "ตัดวงจร #อาชญากรรมออนไลน์" รายวัน = รายชื่อเพจปลอม + ลิงก์ ads library ไม่มีวิธีการหลอก (632 โพสต์)
# - ThaiCERT ข่าวต่างประเทศ/vendor (FBI, Microsoft 365, ...) ไม่เกี่ยวผู้ใช้ไทย (95 โพสต์)
LOW_VALUE_TITLE = re.compile(
    r"^ตัดวงจร|สหรัฐ|FBI|DOJ|CISA|ยุโรป|อังกฤษ|ออสเตรเลีย|สิงคโปร์|ญี่ปุ่น|เกาหลี|อินเดีย|"
    r"Europol|Interpol|Microsoft|Google|Meta\b|Apple|Salesforce|Cloud|AWS|Oracle|SAP\b|Wi-?Fi",
    re.I,
)


def is_low_value_narrative(record: dict) -> bool:
    """tier N ที่ไม่ควรเข้า RAG — ยังอยู่ใน corpus (provenance ครบ) แต่ setup_rag ข้าม"""
    if record.get("tier") != "N":
        return False
    title = (record.get("text") or "").split("\n", 1)[0]
    return bool(LOW_VALUE_TITLE.search(title))


QUOTE_RE = re.compile(r"[“\"]([^”\"]{20,300})[”\"]")
IMG_RE = re.compile(r'<img[^>]+src="([^"]+)"', re.I)
TAG_RE = re.compile(r"<[^>]+>")
WS_RE = re.compile(r"\s+")


def clean_html(raw_html: str, strip_after: str | None) -> str:
    text = TAG_RE.sub(" ", raw_html)
    text = html.unescape(text)
    text = WS_RE.sub(" ", text).strip()
    if strip_after:
        idx = text.find(strip_after)
        if idx > 0:
            text = text[:idx].strip()
    return text


def guess_category(text: str) -> str:
    for cat, pat in CATEGORY_RULES:
        if pat.search(text):
            return cat
    return "other"


def fetch_posts(site: dict, page: int, per_page: int, since: str | None) -> list[dict]:
    params = {
        "per_page": per_page,
        "page": page,
        "categories": ",".join(str(c) for c in site["categories"]),
        "_fields": "id,date,link,title,content,categories,tags",
        "orderby": "date",
        "order": "desc",
    }
    if since:
        params["after"] = f"{since}T00:00:00"
    url = f"{site['base']}/wp-json/wp/v2/posts"
    for attempt in range(3):
        try:
            r = requests.get(url, params=params, headers={"User-Agent": USER_AGENT}, timeout=30)
            if r.status_code == 400:  # page เกิน
                return []
            r.raise_for_status()
            return r.json()
        except requests.RequestException as e:
            print(f"    retry {attempt + 1}/3 page {page}: {e}")
            time.sleep(2 * (attempt + 1))
    return []


def post_to_record(site: dict, post: dict, retrieved_at: str) -> tuple[ScamRecord | None, list[dict]]:
    """คืน (tier N record หรือ None ถ้าไม่เกี่ยว scam, quote candidates)"""
    raw_html = post["content"]["rendered"] or ""
    title = clean_html(post["title"]["rendered"] or "", None)
    body = clean_html(raw_html, site["strip_after"])
    if len(body) < 80:
        return None, []

    full = f"{title} {body}"
    is_scam_topic = bool(SCAM_KEYWORDS.search(full))
    if site["require_scam_keyword"] and not is_scam_topic:
        return None, []
    exclude = site.get("exclude_title")
    if exclude and exclude.search(title):
        return None, []

    # snapshot ของ content ดิบ
    site_dir = SNAPSHOT_DIR / site["slug"]
    site_dir.mkdir(parents=True, exist_ok=True)
    (site_dir / f"{post['id']}.json").write_text(json.dumps(post, ensure_ascii=False), encoding="utf-8")
    h = snapshot_hash(raw_html.encode("utf-8"))

    images = IMG_RE.findall(raw_html)[:5]
    verdict = "danger" if is_scam_topic else "safe"
    category = guess_category(full) if verdict == "danger" else None
    text = f"{title}\n{body[:MAX_BODY_CHARS]}"

    record = ScamRecord(
        id=make_id(f"wp-{site['slug']}", post["link"]),
        text=text,
        verdict=verdict,
        category=category,
        tier="N",
        source=SourceAttribution(
            name=site["name"],
            url=post["link"],
            scraped_at=retrieved_at,
            extraction_method="verbatim_html",
            published_date=post.get("date"),
            license="fair_use_academic",
            license_note="fair use - academic research; public awareness article from Thai government agency; URL preserved",
            snapshot_hash=h,
        ),
        annotation=Annotation(
            labels=[AnnotationLabel(annotator="rule:keyword_category", verdict=verdict, category=category)],
            final={"verdict": verdict, "category": category, "resolved_by": "keyword_rule"},
            guideline_version=None,
        ),
        pii=PiiInfo(masked=False, masker_version=None, pii_found_count=0),  # mask ตอน ingest RAG
        annotator_notes=(f"wp_post_id={post['id']} | images=" + ",".join(images)) if images else f"wp_post_id={post['id']}",
    )

    quotes = [
        {
            "quote": q.strip(),
            "post_url": post["link"],
            "post_title": title,
            "site": site["slug"],
            "published_date": post.get("date"),
            "snapshot_hash": h,
            "status": "needs_human_verify",  # → tier A เมื่อคนยืนยันว่าเป็นข้อความ scam จริง ไม่ใช่คำพูดเจ้าหน้าที่
        }
        for q in QUOTE_RE.findall(body)
    ]
    return record, quotes


def scrape_site(site_key: str, max_pages: int, since: str | None, dry_run: bool, per_page: int = 100) -> None:
    site = SITES[site_key]
    retrieved_at = now_iso()
    records: list[ScamRecord] = []
    quotes: list[dict] = []
    skipped = 0

    print(f"\n=== {site['name']} ===")
    for page in range(1, max_pages + 1):
        posts = fetch_posts(site, page, per_page, since)
        if not posts:
            break
        for post in posts:
            rec, qs = post_to_record(site, post, retrieved_at)
            if rec is None:
                skipped += 1
                continue
            records.append(rec)
            quotes.extend(qs)
        print(f"  page {page}: {len(posts)} posts → kept {len(records)} so far, skipped {skipped}")
        if len(posts) < per_page:
            break
        time.sleep(PAGE_SLEEP_SEC)

    from collections import Counter
    print(f"  records: {len(records)} | quote candidates: {len(quotes)}")
    print("  category (keyword_rule):", dict(Counter(r.category for r in records)))

    if dry_run:
        for r in records[:3]:
            print("  --", r.text[:160].replace("\n", " | "))
        print("  (dry-run)")
        return

    added = append_records(records, CORPUS_PATH)
    print(f"  appended {added} new tier N records → {CORPUS_PATH}")
    if quotes:
        QUOTES_PATH.parent.mkdir(parents=True, exist_ok=True)
        existing = set()
        if QUOTES_PATH.exists():
            existing = {json.loads(l)["quote"] for l in QUOTES_PATH.read_text(encoding="utf-8").splitlines() if l.strip()}
        with QUOTES_PATH.open("a", encoding="utf-8") as f:
            n = 0
            for q in quotes:
                if q["quote"] in existing:
                    continue
                f.write(json.dumps(q, ensure_ascii=False) + "\n")
                existing.add(q["quote"])
                n += 1
        print(f"  wrote {n} new quote candidates → {QUOTES_PATH} (ต้องมีคน verify ก่อนเป็น tier A)")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", choices=[*SITES, "all"], default="all")
    ap.add_argument("--max-pages", type=int, default=3, help="หน้าละ 100 โพสต์")
    ap.add_argument("--since", default=None, help="YYYY-MM-DD — เอาเฉพาะโพสต์หลังวันนี้")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    sites = list(SITES) if args.site == "all" else [args.site]
    for s in sites:
        scrape_site(s, args.max_pages, args.since, args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
