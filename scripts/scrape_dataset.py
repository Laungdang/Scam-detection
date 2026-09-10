"""
Scrape ข้อมูลมิจฉาชีพจาก 3 แหล่ง แล้ว append เข้า Excel dataset
แหล่ง:
  1. thaipoliceonline.com  — CCIB News API (ของจริงจากตำรวจ)
  2. Google News RSS        — รวมข่าวจากหลายสำนักข่าว (Thairath, เดลินิวส์, Thai PBS ฯลฯ)
  3. แนวหน้า (naewna.com)  — ข่าวมิจฉาชีพ category page

รัน:
  python -m scripts.scrape_dataset                        # ทุกแหล่ง
  python -m scripts.scrape_dataset --source thaipoliceonline
  python -m scripts.scrape_dataset --source googlenews
  python -m scripts.scrape_dataset --source naewna
  python -m scripts.scrape_dataset --dry-run              # แสดงตัวอย่างโดยไม่บันทึก

หลังรันเสร็จให้รัน:
  python -m scripts.setup_rag   เพื่อ rebuild ChromaDB
"""

import argparse
import os
import re
import sys
import time
import warnings

import anthropic
import pandas as pd
import requests
from bs4 import BeautifulSoup

from app.config.settings import Settings

# รองรับ UTF-8 บน Windows terminal
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = open(sys.stdout.fileno(), mode="w", encoding="utf-8", buffering=1)

warnings.filterwarnings("ignore")  # suppress InsecureRequestWarning

XLSX_PATH = os.getenv("RAG_XLSX_PATH", "C:/Users/laung/Downloads/scam_dataset_v3_fixed.xlsx")

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
SESSION.verify = False


# ── helpers ───────────────────────────────────────────────────────────────────

def strip_html(html: str) -> str:
    text = BeautifulSoup(html, "lxml").get_text(separator=" ")
    return re.sub(r"\s+", " ", text).strip()


SCAM_CATEGORIES = {
    "investment_fraud": ["Deepfake / ปลอมบุคคลมีชื่อเสียง / AI Trading ปลอม", "Pump-and-Dump crypto / ชักชวนผ่าน Telegram", "ปลอมใบอนุญาต ก.ล.ต. / ชื่อบัญชีเป็นบุคคลธรรมดา", "เพจ Social Media ปลอม / ผลตอบแทนสูงผิดปกติ", "รับประกันผลตอบแทนสูงผิดปกติ / Forex ปลอม"],
    "romance_pig_butcher": ["Pig Butchering / Romance+Investment combo", "Romance Scam / ตัวตนปลอม / ขอเงินฉุกเฉิน", "Fake Trading Platform / Pig Butchering", "Pig Butchering Scam / Romance+Investment"],
    "employment_scam": ["งาน Part-time ปลอม / ต้องจ่ายเงินก่อน", "งานต่างประเทศปลอม / Scam Center เมียนมา", "บริษัทจัดหางานปลอม / ภารกิจออนไลน์ / โอนก่อน", "ประกาศงานปลอม / ขอข้อมูลส่วนตัว / ขอ PIN"],
    "loan_scam": ["สินเชื่อด่วนปลอม / ค่าธรรมเนียมก่อนได้เงิน", "LINE OA ปลอมธนาคาร / ค่าธรรมเนียมก่อนได้เงิน"],
    "shopping_scam": ["ขายบัตรคอนเสิร์ตปลอม / โอนมัดจำแล้วหนี", "สินค้าแบรนด์เนมปลอม / โอนก่อนแล้วหนี", "รีวิวปลอม / สินค้าไม่ตรงปก / ร้านใหม่", "ร้านออนไลน์ใหม่ / ราคาถูกผิดปกติ / โอนก่อน", "เพจปลอมเลียนแบบแบรนด์ / โอนก่อนได้ของ"],
    "call_center": ["อ้างเป็น INTERPOL / ขอเงินประกันตัว", "อ้างเป็น DSI / ขู่จับ / บัญชีม้า", "อ้างเป็น กสทช. / เร่งรัดด้วยการขู่ระงับเบอร์", "อ้างเป็นกรมสรรพากร / เร่งรัดชำระภาษีปลอม", "อ้างเป็นตำรวจไซเบอร์ / ส่งลิงก์ติดตั้งแอปดูดเงิน", "อ้างเป็นตำรวจ / ขู่ให้โอนเงินหลบคดี", "อ้างเป็นพนักงานธนาคาร / ขอ OTP", "ปลอมนโยบายรัฐ Digital Wallet / แอปดูดเงิน", "ปลอมหน่วยงานรัฐ / Phishing ขอข้อมูลบัญชี"],
    "sms_phishing": ["SMS Spoofing / ลิงก์ปลอมเลียนแบบธนาคาร", "SMS Spoofing เข้ากล่อง SMS จริง / Phishing", "SMS ปลอมจากบริษัทขนส่ง / Smishing", "SMS ปลอมจากบริษัทขนส่ง / แอปดูดเงิน", "URL ปลอมธนาคารออมสิน / Phishing", "แอปปลอม / ขอข้อมูล Internet Banking", "Domain ปลอมเลียนแบบธนาคาร / Phishing"],
}

_CLASSIFY_SYSTEM = (
    "จำแนกข่าวมิจฉาชีพ ตอบเฉพาะ JSON: "
    + '{"scam_category": "...", "matched_pattern": "..."}'
    + "\nscam_category: " + ", ".join(SCAM_CATEGORIES.keys())
    + "\nmatched_pattern ตาม category:\n"
    + "\n".join(f"{c}: " + " | ".join(pats) for c, pats in SCAM_CATEGORIES.items())
)


def _parse_json(raw: str) -> dict:
    """Parse JSON จาก response ที่อาจมี ```json ... ``` ครอบ"""
    text = raw.strip()
    if "```" in text:
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    start, end = text.find("{"), text.rfind("}") + 1
    return __import__("json").loads(text[start:end]) if start != -1 else {}


def classify_with_claude(texts: list[str]) -> list[tuple[str, str]]:
    """ใช้ Claude Haiku classify คืน list of (category, pattern)"""
    if not Settings.CLAUDE_API_KEY:
        return [classify_scam(t) for t in texts]

    client = anthropic.Anthropic(api_key=Settings.CLAUDE_API_KEY)
    results = []
    for text in texts:
        try:
            msg = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=100,
                system=_CLASSIFY_SYSTEM,
                messages=[{"role": "user", "content": text[:400]}],
            )
            data = _parse_json(msg.content[0].text)
            cat = data.get("scam_category", "sms_phishing")
            pat = data.get("matched_pattern", "")
            if cat not in SCAM_CATEGORIES:
                cat = "sms_phishing"
            valid_pats = SCAM_CATEGORIES.get(cat, [])
            if pat not in valid_pats:
                pat = valid_pats[0] if valid_pats else ""
            results.append((cat, pat))
        except Exception:
            results.append(classify_scam(text))
    return results


def classify_scam(text: str) -> tuple[str, str]:
    """คืน (scam_category, matched_pattern)"""
    t = text.lower()

    # investment_fraud
    if any(k in t for k in ["ลงทุน", "forex", "crypto", "คริปโต", "หุ้น", "กำไร", "ผลตอบแทน", "เทรด", "ปั่นหุ้น"]):
        if any(k in t for k in ["deepfake", "ai trading", "ปลอมบุคคล"]):
            return "investment_fraud", "Deepfake / ปลอมบุคคลมีชื่อเสียง / AI Trading ปลอม"
        if any(k in t for k in ["telegram", "pump", "dump"]):
            return "investment_fraud", "Pump-and-Dump crypto / ชักชวนผ่าน Telegram"
        if any(k in t for k in ["ก.ล.ต", "ใบอนุญาต"]):
            return "investment_fraud", "ปลอมใบอนุญาต ก.ล.ต. / ชื่อบัญชีเป็นบุคคลธรรมดา"
        if any(k in t for k in ["facebook", "instagram", "social", "เพจ"]):
            return "investment_fraud", "เพจ Social Media ปลอม / ผลตอบแทนสูงผิดปกติ"
        return "investment_fraud", "รับประกันผลตอบแทนสูงผิดปกติ / Forex ปลอม"

    # romance_pig_butcher
    if any(k in t for k in ["pig butcher", "romance", "หลอกรัก", "แฟนปลอม", "ความรัก", "คู่รัก"]):
        if any(k in t for k in ["ลงทุน", "platform", "เทรด"]):
            return "romance_pig_butcher", "Pig Butchering / Romance+Investment combo"
        return "romance_pig_butcher", "Romance Scam / ตัวตนปลอม / ขอเงินฉุกเฉิน"

    # employment_scam
    if any(k in t for k in ["สมัครงาน", "งานออนไลน์", "รายได้วันละ", "part-time", "พาร์ทไทม์", "รับงาน", "งานต่างประเทศ"]):
        if any(k in t for k in ["เมียนมา", "กัมพูชา", "ลาว", "scam center"]):
            return "employment_scam", "งานต่างประเทศปลอม / Scam Center เมียนมา"
        if any(k in t for k in ["จัดหางาน", "ภารกิจ"]):
            return "employment_scam", "บริษัทจัดหางานปลอม / ภารกิจออนไลน์ / โอนก่อน"
        return "employment_scam", "งาน Part-time ปลอม / ต้องจ่ายเงินก่อน"

    # loan_scam
    if any(k in t for k in ["กู้เงิน", "สินเชื่อ", "ดอกเบี้ย", "เงินกู้", "สินเชื่อด่วน"]):
        return "loan_scam", "สินเชื่อด่วนปลอม / ค่าธรรมเนียมก่อนได้เงิน"

    # shopping_scam
    if any(k in t for k in ["ช้อปปิ้ง", "ร้านค้าปลอม", "สั่งซื้อ", "คอนเสิร์ต", "บัตรคอนเสิร์ต", "สินค้าแบรนด์"]):
        if any(k in t for k in ["คอนเสิร์ต", "บัตร"]):
            return "shopping_scam", "ขายบัตรคอนเสิร์ตปลอม / โอนมัดจำแล้วหนี"
        if any(k in t for k in ["แบรนด์", "เนม"]):
            return "shopping_scam", "สินค้าแบรนด์เนมปลอม / โอนก่อนแล้วหนี"
        if any(k in t for k in ["รีวิว", "ไม่ตรงปก"]):
            return "shopping_scam", "รีวิวปลอม / สินค้าไม่ตรงปก / ร้านใหม่"
        return "shopping_scam", "ร้านออนไลน์ใหม่ / ราคาถูกผิดปกติ / โอนก่อน"

    # call_center
    if any(k in t for k in ["call center", "แก๊ง", "โทรหลอก", "dsi", "ยาเสพติด", "อายัด", "interpol", "ตำรวจปลอม"]):
        if any(k in t for k in ["interpol", "นานาชาติ"]):
            return "call_center", "อ้างเป็น INTERPOL / ขอเงินประกันตัว"
        if any(k in t for k in ["dsi", "ยาเสพติด"]):
            return "call_center", "อ้างเป็น DSI / ขู่จับ / บัญชีม้า"
        if any(k in t for k in ["กสทช", "ระงับเบอร์"]):
            return "call_center", "อ้างเป็น กสทช. / เร่งรัดด้วยการขู่ระงับเบอร์"
        if any(k in t for k in ["สรรพากร", "ภาษี"]):
            return "call_center", "อ้างเป็นกรมสรรพากร / เร่งรัดชำระภาษีปลอม"
        if any(k in t for k in ["ไซเบอร์", "แอป", "ติดตั้ง"]):
            return "call_center", "อ้างเป็นตำรวจไซเบอร์ / ส่งลิงก์ติดตั้งแอปดูดเงิน"
        return "call_center", "อ้างเป็นตำรวจ / ขู่ให้โอนเงินหลบคดี"

    # sms_phishing
    if any(k in t for k in ["sms", "ลิงก์", "link", "คลิก", "พัสดุ", "otp", "phishing", "smishing"]):
        if any(k in t for k in ["ธนาคาร", "bank"]):
            if any(k in t for k in ["ออมสิน"]):
                return "sms_phishing", "URL ปลอมธนาคารออมสิน / Phishing"
            return "sms_phishing", "SMS Spoofing / ลิงก์ปลอมเลียนแบบธนาคาร"
        if any(k in t for k in ["พัสดุ", "ขนส่ง", "flash"]):
            return "sms_phishing", "SMS ปลอมจากบริษัทขนส่ง / Smishing"
        if any(k in t for k in ["แอป", "ดูดเงิน", "ติดตั้ง"]):
            return "sms_phishing", "แอปปลอม / ขอข้อมูล Internet Banking"
        return "sms_phishing", "SMS Spoofing เข้ากล่อง SMS จริง / Phishing"

    if any(k in t for k in ["แอปปลอม", "แอปธนาคาร", "otp", "internet banking"]):
        return "sms_phishing", "แอปปลอม / ขอข้อมูล Internet Banking"

    if any(k in t for k in ["หน่วยงานรัฐ", "รัฐบาลปลอม", "digital wallet", "ดิจิทัลวอลเล็ต", "คนละครึ่ง"]):
        return "call_center", "ปลอมนโยบายรัฐ Digital Wallet / แอปดูดเงิน"

    return "sms_phishing", "SMS ปลอมจากบริษัทขนส่ง / Smishing"  # default scam


def load_existing(path: str) -> pd.DataFrame:
    if os.path.exists(path):
        df = pd.read_excel(path)
        return df
    return pd.DataFrame(columns=["sample_id", "input_text", "scam_category",
                                  "input_type", "result_status", "matched_pattern", "data_source"])


def save_and_report(new_rows: list[dict], path: str, dry_run: bool, source_name: str) -> int:
    if not new_rows:
        print(f"  [{source_name}] ไม่มีข้อมูลใหม่")
        return 0

    df_existing = load_existing(path)
    existing_texts = set(df_existing["input_text"].dropna().str.strip().tolist())
    deduped = [r for r in new_rows if r["input_text"].strip() not in existing_texts]

    print(f"  [{source_name}] ดึงได้ {len(new_rows)} | ใหม่ {len(deduped)} | ซ้ำ {len(new_rows) - len(deduped)} (ข้าม)")

    if not deduped:
        return 0

    # classify ด้วย Claude (batch ละ 20 เพื่อไม่ให้ rate limit)
    if not dry_run and Settings.CLAUDE_API_KEY:
        print(f"  กำลัง classify {len(deduped)} rows ด้วย Claude Haiku...")
        batch_size = 20
        for i in range(0, len(deduped), batch_size):
            batch = deduped[i:i + batch_size]
            texts = [r["input_text"] for r in batch]
            labels = classify_with_claude(texts)
            for row, (cat, pat) in zip(batch, labels):
                row["scam_category"] = cat
                row["matched_pattern"] = pat
            print(f"    classified {min(i + batch_size, len(deduped))}/{len(deduped)}")
            time.sleep(0.5)

    if dry_run:
        print(f"  [DRY RUN] ตัวอย่าง 3 รายการแรก:")
        for r in deduped[:3]:
            print(f"    · {r['input_text'][:90]!r}")
        return len(deduped)

    # หา max sample_id
    try:
        max_id = int(df_existing["sample_id"].dropna().astype(str)
                     .str.extract(r"(\d+)")[0].dropna().astype(int).max())
    except Exception:
        max_id = len(df_existing)

    df_new = pd.DataFrame(deduped)
    df_new["sample_id"] = [f"scraped_{max_id + i + 1}" for i in range(len(df_new))]
    df_new["input_type"] = "text"
    df_new["result_status"] = "suspicious"
    df_new["matched_pattern"] = df_new["matched_pattern"].fillna("") if "matched_pattern" in df_new else ""

    df_out = pd.concat([df_existing, df_new], ignore_index=True)
    df_out.to_excel(path, index=False)
    print(f"  บันทึกแล้ว → {path}  (รวม {len(df_out)} rows)")
    return len(deduped)


# ── Source 1: thaipoliceonline CCIB News API ──────────────────────────────────

def scrape_thaipoliceonline() -> list[dict]:
    BASE = "https://officer.thaipoliceonline.go.th/api/ccib/v1.0"
    rows = []
    page = 1
    while True:
        try:
            resp = SESSION.get(f"{BASE}/CCPNews/Newslist?page={page}&pagesize=50", timeout=10)
            data = resp.json()
            items = data.get("Value", {}).get("Data", [])
            if not items:
                break
            for item in items:
                title = (item.get("NewsTitle") or "").strip()
                content = strip_html(item.get("NewsContent") or item.get("NewsDescription") or "")
                text = f"{title} {content}".strip()
                if len(text) < 30:
                    continue
                cat, pattern = classify_scam(text)
                rows.append({
                    "input_text": text[:600],
                    "scam_category": cat,
                    "matched_pattern": pattern,
                    "data_source": f"thaipoliceonline.com — {item.get('CategoryName', 'เตือนภัยไซเบอร์')}",
                })
            total = data.get("Value", {}).get("TotalCount", 0)
            if page * 50 >= (total or 0):
                break
            page += 1
            time.sleep(0.5)
        except Exception as e:
            print(f"  thaipoliceonline ERROR page {page}: {e}")
            break
    return rows


# ── Source 2: Google News RSS ─────────────────────────────────────────────────

GOOGLE_NEWS_KEYWORDS = [
    "มิจฉาชีพ",
    "หลอกลวงออนไลน์",
    "โกงออนไลน์",
    "แก๊ง call center",
    "หลอกลงทุน",
    "แอปปลอม ธนาคาร",
    "งานออนไลน์ หลอก",
    "สมัครงาน โกง",
    "กู้เงิน หลอก",
    "romance scam ไทย",
]

def _fetch_article_text(url: str) -> str:
    """ดึงเนื้อหาบทความจาก URL (best-effort)"""
    try:
        r = SESSION.get(url, timeout=8, allow_redirects=True)
        soup = BeautifulSoup(r.text, "lxml")
        for tag in soup.select("nav, header, footer, script, style, .sidebar, .ads, .related, .comment"):
            tag.decompose()
        # ลอง selector ทั่วไป
        body = soup.select_one(
            "article, .entry-content, .article-content, .post-content, "
            ".story-body, .article-body, [class*=content]"
        )
        if body:
            text = body.get_text(separator=" ", strip=True)
        else:
            ps = [p.get_text(strip=True) for p in soup.find_all("p") if len(p.get_text(strip=True)) > 40]
            text = " ".join(ps)
        return re.sub(r"\s+", " ", text).strip()[:800]
    except Exception:
        return ""


def scrape_googlenews() -> list[dict]:
    import urllib.parse
    rows = []
    seen_titles: set[str] = set()

    for keyword in GOOGLE_NEWS_KEYWORDS:
        encoded = urllib.parse.quote(keyword)
        rss_url = f"https://news.google.com/rss/search?q={encoded}&hl=th&gl=TH&ceid=TH:th"
        try:
            r = SESSION.get(rss_url, timeout=10)
            soup = BeautifulSoup(r.text, "xml")
            items = soup.find_all("item")

            for item in items:
                title_tag = item.find("title")
                link_tag = item.find("link") or item.find("url")
                desc_tag = item.find("description")
                source_tag = item.find("source")

                title = title_tag.get_text(strip=True) if title_tag else ""
                link = link_tag.get_text(strip=True) if link_tag else ""
                desc = strip_html(desc_tag.get_text() if desc_tag else "")
                source = source_tag.get_text(strip=True) if source_tag else "Google News"

                if not title or title in seen_titles:
                    continue
                seen_titles.add(title)

                # กรองเฉพาะข่าวที่เกี่ยวกับมิจฉาชีพจริงๆ
                if not any(k in title + desc for k in
                           ["มิจฉาชีพ", "หลอก", "โกง", "ฉ้อโกง", "ภัยไซเบอร์", "scam", "phishing"]):
                    continue

                # ใช้ title + description จาก RSS เลย ไม่ดึงบทความเพิ่ม (เร็วกว่ามาก)
                text = f"{title} {desc}".strip()
                text = re.sub(r"\s+", " ", text)[:800]

                cat, pattern = classify_scam(text)
                rows.append({
                    "input_text": text,
                    "scam_category": cat,
                    "matched_pattern": pattern,
                    "data_source": f"Google News — {source}",
                })

            time.sleep(0.5)
        except Exception as e:
            print(f"  Google News ERROR keyword={keyword!r}: {e}")

    return rows


# ── Source 3: แนวหน้า (naewna.com) ───────────────────────────────────────────

NAEWNA_CATEGORY_PAGES = [
    "https://www.naewna.com/local",
    "https://www.naewna.com/politic",
]
SCAM_KEYWORDS = ["มิจฉาชีพ", "หลอก", "โกง", "ภัย", "ฉ้อโกง", "แฮก", "scam"]


def _naewna_get_article_text(url: str) -> str:
    try:
        r = SESSION.get(url, timeout=10)
        soup = BeautifulSoup(r.text, "lxml")
        for tag in soup.select("nav, header, footer, script, style, .sidebar, .ads, .related"):
            tag.decompose()
        ps = [p.get_text(strip=True) for p in soup.find_all("p") if len(p.get_text(strip=True)) > 40]
        return " ".join(ps)[:700]
    except Exception:
        return ""


def scrape_naewna(max_pages: int = 10) -> list[dict]:
    rows = []
    seen_urls: set[str] = set()

    for base_url in NAEWNA_CATEGORY_PAGES:
        for page in range(1, max_pages + 1):
            url = base_url if page == 1 else f"{base_url}/page/{page}"
            try:
                r = SESSION.get(url, timeout=10)
                if r.status_code == 404:
                    break
                soup = BeautifulSoup(r.text, "lxml")
                links = soup.select("h2 a[href], h3 a[href]")
                if not links:
                    break

                new_found = False
                for a in links:
                    href = a.get("href", "")
                    if not href.startswith("http"):
                        href = "https://www.naewna.com" + href
                    if href in seen_urls:
                        continue
                    seen_urls.add(href)
                    new_found = True

                    title = a.get_text(strip=True)
                    if not any(k in title for k in SCAM_KEYWORDS):
                        continue

                    content = _naewna_get_article_text(href)
                    text = f"{title} {content}".strip()
                    if len(text) < 50:
                        text = title

                    cat, pattern = classify_scam(text)
                    rows.append({
                        "input_text": text[:700],
                        "scam_category": cat,
                        "matched_pattern": pattern,
                        "data_source": f"แนวหน้า (naewna.com) — {href}",
                    })
                    time.sleep(0.3)

                if not new_found:
                    break
                time.sleep(0.5)
            except Exception as e:
                print(f"  naewna ERROR page={page}: {e}")
                break

    return rows


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Scrape Thai scam news → Excel dataset")
    parser.add_argument("--source", choices=["thaipoliceonline", "googlenews", "naewna", "all"],
                        default="all")
    parser.add_argument("--dry-run", action="store_true",
                        help="แสดงตัวอย่างโดยไม่บันทึกลง Excel")
    parser.add_argument("--pages", type=int, default=10,
                        help="จำนวนหน้าต่อ keyword สำหรับ naewna/khaosod (default: 10)")
    args = parser.parse_args()

    label = "[DRY RUN] " if args.dry_run else ""
    print(f"{label}Target: {XLSX_PATH}")
    print("-" * 60)

    total_added = 0

    if args.source in ("thaipoliceonline", "all"):
        print("\n[แหล่ง 1] thaipoliceonline.com — CCIB News API")
        rows = scrape_thaipoliceonline()
        total_added += save_and_report(rows, XLSX_PATH, args.dry_run, "thaipoliceonline")

    if args.source in ("googlenews", "all"):
        print(f"\n[แหล่ง 2] Google News RSS — {len(GOOGLE_NEWS_KEYWORDS)} keywords")
        rows = scrape_googlenews()
        total_added += save_and_report(rows, XLSX_PATH, args.dry_run, "googlenews")

    if args.source in ("naewna", "all"):
        print(f"\n[แหล่ง 3] แนวหน้า (naewna.com) — {len(NAEWNA_CATEGORY_PAGES)} categories × {args.pages} หน้า")
        rows = scrape_naewna(max_pages=args.pages)
        total_added += save_and_report(rows, XLSX_PATH, args.dry_run, "naewna")

    print("\n" + "=" * 60)
    if args.dry_run:
        print(f"[DRY RUN] จะเพิ่มได้ {total_added} rows (ไม่ได้บันทึก)")
    else:
        print(f"เสร็จสิ้น เพิ่มแล้ว {total_added} rows")
        if total_added > 0:
            print("\nขั้นตอนต่อไป — rebuild ChromaDB:")
            print("  python -m scripts.setup_rag")


if __name__ == "__main__":
    main()
