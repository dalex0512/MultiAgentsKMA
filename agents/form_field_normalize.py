"""
Chuẩn hóa giá trị trước khi ghi vào mẫu Word.
"""

from __future__ import annotations

import re
import unicodedata

_MSSV_RE = re.compile(r"\b((?:AT|CT|DT)\d{6})\b", re.I)
_PHONE_RE = re.compile(r"(0\d{9,10})")
_DATE_RE = re.compile(
    r"(\d{1,2})\s*[/\-\.]\s*(\d{1,2})\s*[/\-\.]\s*(\d{2,4})"
)


def _slug(text: str) -> str:
    t = unicodedata.normalize("NFD", text.lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def normalize_phone(raw: str) -> str:
    digits = re.sub(r"\D", "", raw)
    if digits.startswith("84") and len(digits) >= 11:
        digits = "0" + digits[2:]
    if len(digits) == 10 and digits.startswith("0"):
        return f"{digits[:4]} {digits[4:7]} {digits[7:]}"
    if len(digits) == 11 and digits.startswith("0"):
        return f"{digits[:4]} {digits[4:7]} {digits[7:]}"
    return raw.strip()


def normalize_mssv(raw: str) -> str:
    m = _MSSV_RE.search(raw.upper().replace(" ", ""))
    return m.group(1).upper() if m else raw.strip().upper()


def normalize_gender(raw: str) -> str:
    s = _slug(raw)
    if s in ("nam", "male", "m"):
        return "Nam"
    if s in ("nu", "nữ", "female", "f"):
        return "Nữ"
    return raw.strip()


def normalize_date(raw: str) -> str:
    m = _DATE_RE.search(raw.strip())
    if not m:
        return raw.strip()
    d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if y < 100:
        y += 2000 if y < 50 else 1900
    return f"{d:02d}/{mo:02d}/{y}"


def date_parts(raw: str) -> tuple[str, str, str] | None:
    m = _DATE_RE.search(raw.strip())
    if not m:
        return None
    d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if y < 100:
        y += 2000 if y < 50 else 1900
    return str(d), str(mo), str(y)[-2:] if y < 2100 else str(y)


def normalize_field_value(field_type: str, raw: str, *, max_len: int = 500) -> str:
    val = (raw or "").strip()
    if not val:
        return ""
    if len(val) > max_len:
        val = val[:max_len]

    ft = (field_type or "text").lower()
    if ft == "phone":
        return normalize_phone(val)
    if ft == "mssv":
        return normalize_mssv(val)
    if ft == "gender":
        return normalize_gender(val)
    if ft == "date":
        return normalize_date(val)
    if ft == "text_long":
        return re.sub(r"\s+", " ", val).strip()
    return val
