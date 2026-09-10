"""
Feature extraction สำหรับ scam classifier

หลักการ (ดู CLAUDE.md Section 4.2 — Feature-Level Fusion):
- ทุก feature ถูกรวมเป็น vector เดียว ส่งให้ model ครั้งเดียว
- ห้าม cascade gate / decision tree ก่อน model
- Feature ประกอบด้วย:
  1. TF-IDF (char n-grams 2-4) — เหมาะกับ Thai เพราะ word boundary ยาก
  2. TF-IDF (word-level, ด้วย PyThaiNLP tokenizer)
  3. Metadata features (length, digit/URL/symbol counts, money patterns)

Feature pipeline เป็น sklearn-compatible — fit บน train เท่านั้น, transform val/test
"""

from __future__ import annotations

import re

import numpy as np
from pythainlp.tokenize import word_tokenize
from scipy import sparse
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.pipeline import FeatureUnion


URGENCY_WORDS = [
    "ด่วน", "ทันที", "ภายใน", "วันนี้", "เร่ง", "รีบ",
    "ก่อน", "หมดเขต", "ครั้งสุดท้าย", "เหลือ",
]
AUTHORITY_WORDS = [
    "ธนาคาร", "สรรพากร", "ตำรวจ", "DSI", "ปปง", "กฟภ", "MEA", "PEA",
    "ไปรษณีย์", "กรมสรรพากร", "ศาล", "อายัด", "คดี", "หมายเรียก",
]
PRIZE_WORDS = [
    "ยินดี", "โชคดี", "รางวัล", "ฟรี", "ได้รับ", "โครงการ",
    "iPhone", "iPad", "เงินคืน", "คืนภาษี",
]
LINK_WORDS = ["คลิก", "ลิงก์", "กดลิงก์", "เพิ่มเพื่อน", "LINE"]
MONEY_PATTERN = re.compile(r"(\d{1,3}(?:,\d{3})*|\d+)\s*(บาท|baht|usd|\$)", re.IGNORECASE)
URL_PATTERN = re.compile(r"https?://\S+|www\.\S+|<URL>")
PHONE_PATTERN = re.compile(r"(?<!\d)(?:\+66|0)\d{8,9}(?!\d)|<PHONE_NUMBER>")


def thai_tokenize(text: str) -> list[str]:
    """tokenize ด้วย PyThaiNLP (engine='newmm' default — เร็วและ accuracy ดี)"""
    return [t.strip() for t in word_tokenize(text, engine="newmm") if t.strip()]


class MetadataFeatures(BaseEstimator, TransformerMixin):
    """numeric features จาก text raw — length, digit count, keyword counts ฯลฯ"""

    feature_names = [
        "char_count",
        "word_count",
        "digit_count",
        "uppercase_count",
        "punctuation_count",
        "url_count",
        "phone_count",
        "money_mention_count",
        "urgency_word_count",
        "authority_word_count",
        "prize_word_count",
        "link_word_count",
        "has_thai_script",
        "has_english",
    ]

    def fit(self, X, y=None):
        self.n_features_ = len(self.feature_names)
        return self

    def transform(self, X) -> np.ndarray:
        features = np.zeros((len(X), len(self.feature_names)), dtype=np.float32)
        for i, text in enumerate(X):
            features[i] = self._extract(text)
        return features

    def _extract(self, text: str) -> np.ndarray:
        if not text:
            return np.zeros(len(self.feature_names), dtype=np.float32)
        digits = sum(c.isdigit() for c in text)
        uppers = sum(c.isupper() for c in text)
        puncts = sum(c in "!?.,;:" for c in text)
        urls = len(URL_PATTERN.findall(text))
        phones = len(PHONE_PATTERN.findall(text))
        moneys = len(MONEY_PATTERN.findall(text))
        urgency = sum(text.count(w) for w in URGENCY_WORDS)
        authority = sum(text.count(w) for w in AUTHORITY_WORDS)
        prize = sum(text.count(w) for w in PRIZE_WORDS)
        links = sum(text.count(w) for w in LINK_WORDS)
        has_thai = float(any("฀" <= ch <= "๿" for ch in text))
        has_english = float(any(ch.isascii() and ch.isalpha() for ch in text))
        words = len(text.split())

        return np.array([
            len(text), words, digits, uppers, puncts,
            urls, phones, moneys,
            urgency, authority, prize, links,
            has_thai, has_english,
        ], dtype=np.float32)


class DenseToSparse(BaseEstimator, TransformerMixin):
    """แปลง dense numpy array → sparse — เพื่อ stack กับ TF-IDF ได้"""

    def fit(self, X, y=None):
        self.is_fitted_ = True
        return self

    def transform(self, X) -> sparse.csr_matrix:
        return sparse.csr_matrix(X)


def build_feature_pipeline() -> FeatureUnion:
    """
    รวม 3 feature groups เข้าด้วยกัน:
    1. char n-gram TF-IDF (2-4) — robust ต่อ Thai tokenization, สะกดผิด
    2. word-level TF-IDF (PyThaiNLP tokenized)
    3. metadata features (dense → sparse)
    """
    return FeatureUnion([
        (
            "char_tfidf",
            TfidfVectorizer(
                analyzer="char_wb",
                ngram_range=(2, 4),
                min_df=2,
                max_df=0.95,
                max_features=5000,
                sublinear_tf=True,
            ),
        ),
        (
            "word_tfidf",
            TfidfVectorizer(
                tokenizer=thai_tokenize,
                token_pattern=None,
                ngram_range=(1, 2),
                min_df=2,
                max_df=0.95,
                max_features=3000,
                sublinear_tf=True,
            ),
        ),
        (
            "metadata",
            __make_metadata_pipeline(),
        ),
    ])


def __make_metadata_pipeline():
    from sklearn.pipeline import Pipeline
    return Pipeline([
        ("extract", MetadataFeatures()),
        ("to_sparse", DenseToSparse()),
    ])
