"""
Hồ sơ sinh viên tạm theo phiên chat — tái sử dụng khi điền nhiều đơn liên tiếp.
Ưu tiên khớp theo quy tắc (nhãn/key chuẩn), không đoán mò.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field


def _slug(text: str) -> str:
    t = unicodedata.normalize("NFD", text.lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


@dataclass
class FormField:
    key:      str
    label:    str
    question: str


# key chuẩn → cụm từ nhận diện trong label/key (không dấu, lowercase)
CANONICAL_PATTERNS: dict[str, tuple[str, ...]] = {
    "ho_ten": (
        "ho va ten sinh vien", "ho va ten", "ho ten", "xac nhan sinh vien",
        "ten sinh vien", "họ và tên",
    ),
    "mssv": ("ma sinh vien", "mssv", "ma sv"),
    "ngay_sinh": ("ngay thang nam sinh", "ngay sinh", "nam sinh"),
    "gioi_tinh": ("gioi tinh",),
    "cccd": ("so cccd", "cccd", "cmnd", "so cmnd"),
    "ngay_cap_cccd": ("ngay cap",),
    "noi_cap": ("noi cap",),
    "ho_khau": ("ho khau", "thuong tru"),
    "noi_o": ("noi o hien nay", "dia chi", "cho o"),
    "sdt": ("so dien thoai", "dien thoai", "sdt"),
    "lop": ("lop", "lop hoc"),
    "nganh": ("nganh", "nganh hoc"),
    "he_dao_tao": ("he dao tao", "loai hinh dao tao", "hinh thuc dao tao"),
    "khoa": ("khoa hoc",),
    "hoc_ky": ("hoc ky",),
    "nam_hoc": ("nam hoc",),
    "email": ("email", "thu dien tu"),
}

# Nhãn hiển thị khi xác nhận với sinh viên
CANONICAL_LABELS: dict[str, str] = {
    "ho_ten": "Họ và tên",
    "mssv": "Mã sinh viên",
    "ngay_sinh": "Ngày sinh",
    "gioi_tinh": "Giới tính",
    "cccd": "Số CCCD/CMND",
    "ngay_cap_cccd": "Ngày cấp CCCD",
    "noi_cap": "Nơi cấp",
    "ho_khau": "Hộ khẩu thường trú",
    "noi_o": "Nơi ở hiện tại",
    "sdt": "Số điện thoại",
    "lop": "Lớp",
    "nganh": "Ngành",
    "he_dao_tao": "Hệ / loại hình đào tạo",
    "khoa": "Khóa học",
    "hoc_ky": "Học kỳ",
    "nam_hoc": "Năm học",
    "email": "Email",
}


@dataclass
class StudentProfile:
    """Giá trị theo key chuẩn + alias theo nhãn mẫu đơn trước."""
    values: dict[str, str] = field(default_factory=dict)
    label_aliases: dict[str, str] = field(default_factory=dict)  # slug(label) -> value
    forms_filled: int = 0

    def is_empty(self) -> bool:
        return not self.values and not self.label_aliases


def canonical_key_for_field(field: FormField) -> str | None:
    blob = f"{_slug(field.key)} {_slug(field.label)}"
    blob = re.sub(r"_+", " ", blob).strip()

    best: tuple[int, str] | None = None
    for canon, patterns in CANONICAL_PATTERNS.items():
        for pat in patterns:
            pat_s = pat.replace(" ", "")
            blob_s = blob.replace(" ", "")
            if pat in blob or pat_s in blob_s:
                score = len(pat)
                if best is None or score > best[0]:
                    best = (score, canon)
    return best[1] if best else None


def lookup_value(profile: StudentProfile, field: FormField) -> str | None:
    if profile.is_empty():
        return None

    canon = canonical_key_for_field(field)
    if canon:
        v = profile.values.get(canon, "").strip()
        if v:
            return v

    label_key = _slug(field.label)
    v = profile.label_aliases.get(label_key, "").strip()
    if v:
        return v

    v = profile.values.get(field.key, "").strip()
    return v or None


def apply_profile_to_fields(
    profile: StudentProfile,
    fields: list[FormField],
) -> tuple[dict[str, str], list[FormField]]:
    """
    Trả về (answers_prefill, fields_still_need_ask).
    Chỉ điền khi khớp chắc chắn; trường không khớp vẫn hỏi.
    """
    answers: dict[str, str] = {}
    need_ask: list[FormField] = []

    for f in fields:
        val = lookup_value(profile, f)
        if val and len(val) >= 1:
            answers[f.key] = val
        else:
            need_ask.append(f)

    return answers, need_ask


def merge_answers_into_profile(
    profile: StudentProfile,
    fields: list[FormField],
    answers: dict[str, str],
) -> None:
    for f in fields:
        val = (answers.get(f.key) or "").strip()
        if not val or len(val) > 500:
            continue

        canon = canonical_key_for_field(f)
        if canon:
            profile.values[canon] = val

        profile.label_aliases[_slug(f.label)] = val
        profile.values[f.key] = val

    profile.forms_filled += 1


def format_profile_confirm_block(
    prefilled: list[tuple[str, str, str]],
) -> str:
    """prefilled: (field_key, display_label, value)"""
    lines = []
    for _, disp, val in prefilled:
        lines.append(f"- **{disp}**: {val}")
    return "\n".join(lines)


def parse_correction(text: str) -> tuple[str, str] | None:
    """Parse «họ tên: Nguyễn Văn B» → (canonical_or_label_fragment, value)."""
    m = re.match(r"^(.{2,50}?)\s*[:=]\s*(.+)$", text.strip())
    if not m:
        return None
    left, right = m.group(1).strip(), m.group(2).strip()
    if not right:
        return None
    return left, right


def resolve_correction_key(fragment: str) -> str | None:
    frag = _slug(fragment)
    frag_sp = frag.replace("_", " ")
    for canon, patterns in CANONICAL_PATTERNS.items():
        for pat in patterns:
            if pat in frag_sp or frag_sp in pat:
                return canon
    for canon, label in CANONICAL_LABELS.items():
        if _slug(label) in frag or frag in _slug(label):
            return canon
    return None
