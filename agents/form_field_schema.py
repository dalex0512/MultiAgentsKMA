"""
Schema trường cố định theo từng biểu mẫu — ưu tiên hơn LLM extract.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from agents.student_profile import FormField
from config import DOCS_ROOT

log = logging.getLogger(__name__)

SCHEMA_PATH = Path(DOCS_ROOT) / "bieu_mau" / "field_schemas.json"

# Định nghĩa chung: key → labels, question, type
FIELD_CATALOG: dict[str, dict] = {
    "ho_ten": {
        "labels": ["Họ và tên sinh viên", "Em tên là", "Tên em là", "Sinh viên:", "Tên em là:"],
        "question": "Họ và tên đầy đủ của bạn?",
        "type": "text",
    },
    "sdt": {
        "labels": ["Số điện thoại", "Số ĐT"],
        "question": "Số điện thoại liên hệ?",
        "type": "phone",
    },
    "nganh": {
        "labels": ["Ngành"],
        "question": "Ngành học?",
        "type": "text",
    },
    "lop": {
        "labels": ["Lớp", "Là sinh viên lớp"],
        "question": "Lớp học?",
        "type": "text",
    },
    "mssv": {
        "labels": ["Mã sinh viên", "Mã SV", "Mã số SV"],
        "question": "Mã sinh viên (vd. AT060310)?",
        "type": "mssv",
    },
    "khoa": {
        "labels": ["Khóa"],
        "question": "Khóa học (vd. K20)?",
        "type": "text",
    },
    "ngay_sinh": {
        "labels": ["Ngày, tháng, năm sinh", "Ngày sinh", "(02). Ngày, tháng, năm sinh"],
        "question": "Ngày sinh (dd/mm/yyyy)?",
        "type": "date",
    },
    "gioi_tinh": {
        "labels": ["Giới tính", "(03). Giới tính"],
        "question": "Giới tính (Nam/Nữ)?",
        "type": "gender",
    },
    "cccd": {
        "labels": ["Số CCCD", "Số CCCD/CMND", "Số CMT", "(07). Số CMT"],
        "question": "Số CCCD/CMND?",
        "type": "text",
    },
    "ngay_cap_cccd": {
        "labels": ["Ngày cấp", "(07.1). Ngày cấp"],
        "question": "Ngày cấp CCCD (dd/mm/yyyy)?",
        "type": "date",
    },
    "noi_cap": {
        "labels": ["Nơi cấp"],
        "question": "Nơi cấp CCCD?",
        "type": "text",
    },
    "ho_khau": {
        "labels": ["Hộ khẩu thường trú", "(08). Thường trú /tạm trú (xã/huyện/tỉnh)"],
        "question": "Hộ khẩu thường trú?",
        "type": "text_long",
    },
    "noi_o": {
        "labels": ["Nơi ở hiện nay", "Nơi ở hiện nay của gia đình"],
        "question": "Nơi ở hiện tại?",
        "type": "text_long",
    },
    "que_quan": {
        "labels": ["Quê quán"],
        "question": "Quê quán?",
        "type": "text",
    },
    "he_dao_tao": {
        "labels": ["Loại hình đào tạo", "Hệ Đào tạo", "Diện đào tạo", "Hệ:"],
        "question": "Hệ / loại hình đào tạo (vd. Chính quy)?",
        "type": "text",
    },
    "hoc_ky": {
        "labels": ["Học kỳ"],
        "question": "Học kỳ?",
        "type": "text",
    },
    "nam_hoc": {
        "labels": ["Năm học"],
        "question": "Năm học (vd. 2024-2025)?",
        "type": "text",
    },
    "email": {
        "labels": ["Địa chỉ email"],
        "question": "Email?",
        "type": "text",
    },
    "ly_do": {
        "labels": [
            "Lý do nghỉ học",
            "Lý do không đăng ký online",
            "Lý do thay đổi lớp học phần",
            "Nội dung",
        ],
        "question": "Lý do / nội dung đơn?",
        "type": "text_long",
    },
    "giang_vien": {
        "labels": ["Giảng viên lớp học phần", "Giảng viên dạy môn"],
        "question": "Họ tên giảng viên (lớp học phần)?",
        "type": "text",
    },
    "tu_ngay": {
        "labels": ["nghỉ học từ ngày", "được nghỉ học từ ngày", "từ ngày"],
        "question": "Từ ngày (dd/mm/yyyy)?",
        "type": "date",
    },
    "den_ngay": {
        "labels": ["đến ngày", "đến ngày "],
        "question": "Đến ngày (dd/mm/yyyy)?",
        "type": "date",
    },
    "mon_thi": {
        "labels": ["Em đã tham gia thi môn", "thi môn"],
        "question": "Tên môn thi?",
        "type": "text",
    },
    "lan_thi": {
        "labels": ["Lần thi thứ"],
        "question": "Lần thi thứ mấy?",
        "type": "text",
    },
    "sbd": {
        "labels": ["Số báo danh"],
        "question": "Số báo danh?",
        "type": "text",
    },
    "phong_thi": {
        "labels": ["Phòng thi"],
        "question": "Phòng thi?",
        "type": "text",
    },
    "ngay_thi": {
        "labels": ["Ngày thi"],
        "question": "Ngày thi (dd/mm/yyyy)?",
        "type": "date",
    },
    "ca_thi": {
        "labels": ["Ca thi"],
        "question": "Ca thi?",
        "type": "text",
    },
    "ket_qua_thi": {
        "labels": ["Kết quả bài thi"],
        "question": "Kết quả bài thi?",
        "type": "text",
    },
    "noi_den": {
        "labels": ["Được cử đến", "Có nhiệm vụ"],
        "question": "Nơi/đơn vị được cử đến và nhiệm vụ?",
        "type": "text_long",
    },
    "giay_het_han": {
        "labels": ["có giá trị đến ngày"],
        "question": "Giấy có giá trị đến ngày (dd/mm/yyyy)?",
        "type": "date",
    },
    "dan_toc": {
        "labels": ["(04). Dân tộc"],
        "question": "Dân tộc?",
        "type": "text",
    },
    "noi_dk_kcb": {
        "labels": ["(12). Nơi đăng ký KCB ban đầu"],
        "question": "Nơi đăng ký KCB ban đầu?",
        "type": "text",
    },
    "don_vi_lop_khoa": {
        "labels": ["(10). Đơn vị quản lý (lớp/khóa)"],
        "question": "Lớp/khóa (đơn vị quản lý)?",
        "type": "text",
    },
    "noi_dung_trinh_bay": {
        "labels": ["Em xin trình bày việc như sau"],
        "question": "Nội dung trình bày?",
        "type": "text_long",
    },
    "hoc_phan_huy": {
        "labels": ["học phần xin huỷ", "học phần xin hủy"],
        "question": "Tên học phần xin huỷ?",
        "type": "text",
    },
    "hoc_phan_dang_ky": {
        "labels": ["Tên học phần"],
        "question": "Tên học phần đăng ký (dòng 1 trong bảng)?",
        "type": "text",
    },
}

# field keys theo từng file (filename trong catalog; .docx sau convert)
FORM_FIELD_KEYS: dict[str, list[str]] = {
    "01-Giay_xac_nhan_sinh_vien.docx": [
        "ho_ten", "sdt", "ngay_sinh", "gioi_tinh", "cccd", "ngay_cap_cccd", "noi_cap",
        "ho_khau", "noi_o", "he_dao_tao", "nganh", "lop", "mssv", "hoc_ky", "nam_hoc",
    ],
    "02-Giay_xac_nhan_thuong_binh_mau41.docx": [
        "ho_ten", "sdt", "nganh", "lop", "ngay_cap_cccd", "noi_cap", "hoc_ky", "nam_hoc",
    ],
    "03-Giay_xac_nhan_vay_von.docx": [
        "ho_ten", "ngay_sinh", "gioi_tinh", "cccd", "ngay_cap_cccd", "noi_cap",
        "he_dao_tao", "nganh", "lop", "mssv",
    ],
    "04-Don_dang_ky_hoc.docx": [
        "ho_ten", "sdt", "nganh", "lop", "mssv", "giang_vien",
        "ly_do", "hoc_phan_dang_ky",
    ],
    "05-Don_huy_hoc_phan.docx": [
        "ho_ten", "sdt", "nganh", "lop", "mssv", "hoc_phan_huy", "ly_do",
    ],
    "06-Don_cap_lai_the_sv.docx": [
        "ho_ten", "sdt", "ngay_sinh", "gioi_tinh", "cccd", "ngay_cap_cccd", "noi_cap",
        "ho_khau", "nganh", "lop", "mssv", "ly_do",
    ],
    "07-Don_giai_quyet_cong_viec.docx": [
        "ho_ten", "sdt", "ngay_sinh", "gioi_tinh", "cccd", "ngay_cap_cccd", "noi_cap",
        "nganh", "lop", "mssv", "ly_do",
    ],
    "08-Don_nghi_hoc_duoi_7_ngay.docx": [
        "ho_ten", "sdt", "nganh", "lop", "mssv", "ngay_sinh", "gioi_tinh",
        "cccd", "ngay_cap_cccd", "noi_cap", "tu_ngay", "den_ngay", "ly_do", "giang_vien",
    ],
    "09-Don_nghi_hoc_tren_7_ngay.docx": [
        "ho_ten", "sdt", "nganh", "lop", "mssv", "ngay_sinh", "gioi_tinh",
        "cccd", "ngay_cap_cccd", "noi_cap", "ho_khau", "tu_ngay", "den_ngay", "ly_do",
    ],
    "10-Don_bao_luu_ket_qua.docx": [
        "ho_ten", "sdt", "nganh", "lop", "mssv", "ngay_sinh", "gioi_tinh",
        "cccd", "ngay_cap_cccd", "noi_cap", "ho_khau", "hoc_ky", "nam_hoc", "tu_ngay", "ly_do",
    ],
    "11-Don_tiep_tuc_hoc.docx": [
        "ho_ten", "sdt", "nganh", "lop", "mssv", "ngay_sinh", "gioi_tinh",
        "cccd", "ngay_cap_cccd", "noi_cap", "ho_khau", "hoc_ky", "nam_hoc", "tu_ngay",
    ],
    "12-Don_thoi_hoc.docx": [
        "ho_ten", "sdt", "nganh", "lop", "mssv", "ngay_sinh", "gioi_tinh",
        "cccd", "ngay_cap_cccd", "noi_cap", "ho_khau", "tu_ngay", "ly_do",
    ],
    "13-2-Thanh_toan_ra_truong_tap_the.docx": ["lop", "mssv", "ngay_sinh", "gioi_tinh"],
    "13-Phieu_thanh_toan_ra_truong_ca_nhan.docx": [
        "ho_ten", "sdt", "nganh", "lop", "mssv",
    ],
    "14-Don_hoan_thi.docx": [
        "ho_ten", "sdt", "nganh", "lop", "mssv", "he_dao_tao", "ngay_thi", "ly_do",
    ],
    "15-Don_phuc_khao_bai_thi.docx": [
        "ho_ten", "sdt", "he_dao_tao", "nganh", "lop", "mssv", "mon_thi", "lan_thi",
        "hoc_ky", "nam_hoc", "sbd", "phong_thi", "ngay_thi", "ca_thi", "ket_qua_thi",
    ],
    "16-Don_cap_lai_the_BHYT.docx": [
        "ho_ten", "sdt", "ngay_sinh", "gioi_tinh", "lop", "mssv", "khoa", "nganh",
        "ho_khau", "que_quan", "ly_do",
    ],
    "17-Don_dang_ky_do_an_lan2.docx": [
        "ho_ten", "lop", "mssv", "sdt", "email", "ho_khau", "noi_dung_trinh_bay",
    ],
    "18-Giay_gioi_thieu_thuc_tap.docx": [
        "ho_ten", "he_dao_tao", "lop", "mssv", "noi_den", "giay_het_han",
    ],
    "19-Don_thanh_toan_bao_hiem_Mic.docx": ["ho_ten", "ngay_cap_cccd", "noi_cap", "ly_do"],
    "20-Giay_chung_nhan_suc_khoe.docx": [
        "ho_ten", "nganh", "lop", "gioi_tinh", "ngay_sinh",
    ],
    "21-Kham_SK_dien_tim.docx": ["ho_ten", "lop", "mssv", "gioi_tinh", "ngay_sinh"],
    "22-Phieu_xet_nghiem_sv.docx": ["ho_ten", "lop", "mssv", "ngay_sinh", "gioi_tinh"],
    "23-Danh_muc_kham_suc_khoe.docx": ["ho_ten", "lop", "mssv"],
    "24-Mau_khai_BHYT_sv_ATTT.docx": [
        "ho_ten", "ngay_sinh", "gioi_tinh", "dan_toc", "cccd", "ngay_cap_cccd",
        "ho_khau", "don_vi_lop_khoa", "noi_dk_kcb", "sdt",
    ],
    "25-Huong_dan_khai_BHYT.docx": [],
}

# Alias .doc (catalog cũ / chưa convert)
for _doc, _keys in list(FORM_FIELD_KEYS.items()):
    if _doc.endswith(".docx"):
        legacy = _doc[:-5] + ".doc"
        FORM_FIELD_KEYS.setdefault(legacy, _keys)

PDF_ONLY = {
    "PHIEU_SV_2024.pdf",
    "Thu_tuc_nhap_hoc_2024.pdf",
    "26-Dang_ky_TK_MBank.pdf",
    "27-HD_mo_TKTT_MBank.pdf",
}

_schemas_cache: dict | None = None


def _build_schema_entry(filename: str, keys: list[str]) -> dict:
    fields = []
    for key in keys:
        cat = FIELD_CATALOG.get(key)
        if not cat:
            continue
        labels = cat["labels"]
        fields.append({
            "key": key,
            "label": labels[0],
            "labels": labels,
            "question": cat["question"],
            "type": cat.get("type", "text"),
        })
    return {
        "fillable": bool(fields),
        "format": Path(filename).suffix.lower().lstrip("."),
        "fields": fields,
    }


def build_schemas_json() -> dict:
    out: dict = {"_version": 1, "pdf_only": sorted(PDF_ONLY)}
    for fname, keys in FORM_FIELD_KEYS.items():
        out[fname] = _build_schema_entry(fname, keys)
    for pdf in PDF_ONLY:
        out[pdf] = {"fillable": False, "format": "pdf", "fields": []}
    return out


def write_schemas_file(path: Path | None = None) -> Path:
    path = path or SCHEMA_PATH
    data = build_schemas_json()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_schemas() -> dict:
    global _schemas_cache
    if _schemas_cache is not None:
        return _schemas_cache
    if SCHEMA_PATH.is_file():
        _schemas_cache = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        return _schemas_cache
    _schemas_cache = build_schemas_json()
    return _schemas_cache


def is_fillable(filename: str) -> bool:
    sch = load_schemas().get(filename, {})
    if sch.get("fillable") is False:
        return False
    if filename.endswith(".pdf"):
        return False
    return bool(sch.get("fields")) or filename in FORM_FIELD_KEYS


def schema_fields_for(filename: str) -> list[FormField] | None:
    sch = load_schemas().get(resolve_schema_key(filename), {})
    if not sch or not sch.get("fillable"):
        return None
    items = sch.get("fields") or []
    if not items:
        return None
    out: list[FormField] = []
    for it in items:
        key = (it.get("key") or "").strip()
        label = (it.get("label") or "").strip()
        if not key or not label:
            continue
        out.append(FormField(
            key=key,
            label=label,
            question=(it.get("question") or f"Vui lòng cho biết {label.lower()}.").strip(),
        ))
    return out or None


def field_types_for(filename: str) -> dict[str, str]:
    sch = load_schemas().get(resolve_schema_key(filename), {})
    return {
        (it.get("key") or ""): (it.get("type") or "text")
        for it in (sch.get("fields") or [])
        if it.get("key")
    }


def all_labels_for(filename: str) -> dict[str, list[str]]:
    """key -> list of Word labels."""
    sch = load_schemas().get(resolve_schema_key(filename), {})
    result: dict[str, list[str]] = {}
    for it in sch.get("fields") or []:
        key = it.get("key", "")
        if not key:
            continue
        labels = list(it.get("labels") or [])
        primary = (it.get("label") or "").strip()
        if primary and primary not in labels:
            labels.insert(0, primary)
        cat = FIELD_CATALOG.get(key, {})
        for extra in cat.get("labels", []):
            if extra not in labels:
                labels.append(extra)
        result[key] = labels
    return result


def resolve_fill_template(filename: str) -> str:
    """Ưu tiên bản .docx nếu đã convert."""
    stem = Path(filename).stem
    docx_name = f"{stem}.docx"
    docx_path = Path(DOCS_ROOT) / "bieu_mau" / docx_name
    if docx_path.is_file():
        return docx_name
    return filename


def resolve_schema_key(filename: str) -> str:
    """Map filename catalog → key trong field_schemas."""
    schemas = load_schemas()
    if filename in schemas:
        return filename
    alt = resolve_fill_template(filename)
    if alt in schemas:
        return alt
    stem = Path(filename).stem
    for key in schemas:
        if key.startswith("_") or key.endswith(".pdf"):
            continue
        if Path(key).stem == stem:
            return key
    return filename
