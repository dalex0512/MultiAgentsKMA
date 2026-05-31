"""
Mã khóa đào tạo trong lịch KTHP.

- Mã đầy đủ: AT17, CT6, DT5
- Mã ghép (môn chung nhiều khóa): A19C7D6 → AT19 + CT7 + DT6
  (A→AT, C→CT, D→DT + số khóa ngay sau mỗi chữ cái)
"""

from __future__ import annotations

import re

_PREFIX_MAP = {"A": "AT", "C": "CT", "D": "DT"}

_FULL_COHORT_RE = re.compile(r"(?:AT|CT|DT)\d{1,2}[A-Z0-9]*", re.IGNORECASE)
_COMBINED_SEG_RE = re.compile(r"([ACD])(\d{1,2})(?=[ACD]|$)", re.IGNORECASE)


def expand_khoa_cell(raw: str) -> list[str]:
    """
    Tách ô «Khóa đào tạo» thành danh sách mã khóa đầy đủ.
    Ví dụ: A19C7D6 → [AT19, CT7, DT6]; AT17 → [AT17]; Học lại → [Học lại]
    """
    text = (raw or "").strip()
    if not text:
        return []
    compact = re.sub(r"\s+", "", text).upper()

    if not re.search(r"[ACD]\d|AT|CT|DT", compact, re.I):
        return [text]

    full = [m.upper() for m in _FULL_COHORT_RE.findall(compact)]
    if full:
        return _unique_preserve(full)

    combined: list[str] = []
    for letter, num in _COMBINED_SEG_RE.findall(compact):
        pfx = _PREFIX_MAP.get(letter.upper())
        if pfx:
            combined.append(f"{pfx}{num}")
    if combined:
        return _unique_preserve(combined)

    parts = re.split(r"[,;/\n]+", text)
    return [p.strip() for p in parts if p.strip()]


def cohort_matches_filter(row_khoa: str, filter_cohort: str) -> bool:
    """Khớp khóa hỏi (CT5) với ô bảng (CT5, CT5D5, A19C7D6 chứa CT7…)."""
    if not filter_cohort:
        return True
    fc = filter_cohort.upper().strip()
    for code in expand_khoa_cell(row_khoa):
        cu = code.upper()
        if cu == fc:
            return True
        if len(fc) >= 3 and cu.startswith(fc):
            return True
    return False


def _unique_preserve(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for x in items:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out
