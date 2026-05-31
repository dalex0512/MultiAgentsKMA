"""
Chuẩn hóa đầu vào (viết tắt KMA) và đầu ra boolean cho benchmark / QA.
"""

from __future__ import annotations

import json
import logging
import re
import unicodedata
from pathlib import Path

log = logging.getLogger(__name__)

_ABBREV_PATH = Path(__file__).with_name("kma_abbreviations.json")

_TRUE_PATTERN = (
    r"^(yes|y|true|đúng|dung|chính xác|chinh xac|chắc chắn|chac chan|"
    r"được|duoc|có|co|phải|phai|affirmative)\.?$"
)
_FALSE_PATTERN = r"^(no|n|false|sai|không|khong|ko|k|incorrect|negative)\.?$"
_STRIP_RE = re.compile(r"[^\w\sÀ-ỹ]", re.UNICODE)


def _load_abbrev_map() -> list[tuple[str, str]]:
    try:
        raw = json.loads(_ABBREV_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        log.warning("[text] abbreviations load failed: %s", e)
        return []
    pairs = [(k.strip().lower(), v.strip()) for k, v in raw.items() if k and v]
    pairs.sort(key=lambda x: len(x[0]), reverse=True)
    return pairs


_ABBREV_MAP: list[tuple[str, str]] | None = None


def _get_abbrev_map() -> list[tuple[str, str]]:
    global _ABBREV_MAP
    if _ABBREV_MAP is None:
        _ABBREV_MAP = _load_abbrev_map()
    return _ABBREV_MAP


def _normalize_key(s: str) -> str:
    s = unicodedata.normalize("NFC", (s or "").lower().strip())
    return s


def preprocess_student_query(text: str) -> str:
    """
    Ánh xạ viết tắt/lóng KMA → cụm chuẩn (theo PDF quy chế).
    Không đổi hoa/thường toàn câu — chỉ thay token khớp.
    """
    if not text or not text.strip():
        return text

    original = text
    low = _normalize_key(text)
    result = text

    for abbr, full in _get_abbrev_map():
        if len(abbr) < 2:
            continue
        pattern = re.compile(
            r"(?<![\wÀ-ỹ])" + re.escape(abbr) + r"(?![\wÀ-ỹ])",
            re.IGNORECASE | re.UNICODE,
        )
        if pattern.search(low):
            result = pattern.sub(full, result)

    if result != original:
        log.debug("[text] preprocessed: %r -> %r", original[:80], result[:80])
    return result


def _clean_for_bool(text: str) -> str:
    t = unicodedata.normalize("NFC", (text or "").strip().lower())
    t = _STRIP_RE.sub("", t)
    return t.strip()


def normalize_boolean_output(answer: str) -> str:
    """
    Nếu câu trả lời là boolean ngắn → 'True' / 'False'.
    Câu dài hoặc không khớp → giữ nguyên (sau khi strip nhẹ).
    """
    if not answer:
        return answer

    stripped = answer.strip()
    cleaned = _clean_for_bool(stripped)

    if len(cleaned) > 40 or " " in cleaned and len(cleaned.split()) > 4:
        return stripped

    if re.match(_TRUE_PATTERN, cleaned, re.IGNORECASE | re.UNICODE):
        return "True"
    if re.match(_FALSE_PATTERN, cleaned, re.IGNORECASE | re.UNICODE):
        return "False"

    return stripped


def looks_like_boolean_question(question: str) -> bool:
    """Heuristic: câu hỏi yes/no."""
    q = _normalize_key(question)
    markers = (
        " có phải ", " phải không ", " đúng không ", " có được ",
        " có hay không ", " yes or no ", " true or false ",
    )
    return q.endswith("?") and any(m in q for m in markers)
