"""Tests cho luồng điền biểu mẫu (schema + fill docx)."""

import tempfile
from pathlib import Path

import pytest

from agents.form_field_normalize import normalize_field_value, normalize_mssv, normalize_phone
from agents.form_field_schema import is_fillable, schema_fields_for, write_schemas_file
from agents.form_document import fill_form_copy, resolve_template_path
from agents.form_filler import FormFillService, FormFillState, _extract_fields_for_form
from config import DOCS_ROOT


BIEU_MAU = Path(DOCS_ROOT) / "bieu_mau"


def test_normalize_mssv_phone():
    assert normalize_mssv(" mã sv: at060310 ") == "AT060310"
    assert "0912" in normalize_phone("0912345678")


def test_schema_fields_giay_xac_nhan():
    fields = schema_fields_for("01-Giay_xac_nhan_sinh_vien.docx")
    assert fields
    keys = {f.key for f in fields}
    assert "ho_ten" in keys and "mssv" in keys


def test_pdf_not_fillable():
    assert not is_fillable("Thu_tuc_nhap_hoc_2024.pdf")


def test_fill_docx_08_nghi_hoc():
    fn = "08-Don_nghi_hoc_duoi_7_ngay.docx"
    if not (BIEU_MAU / fn).is_file():
        pytest.skip("template missing")
    fields = schema_fields_for(fn)
    labels = {f.key: f.label for f in fields}
    answers = {
        "ho_ten": "Nguyễn Văn A",
        "sdt": "0912345678",
        "nganh": "CNTT",
        "lop": "AT06",
        "mssv": "AT060310",
        "tu_ngay": "01/03/2026",
        "den_ngay": "05/03/2026",
        "ly_do": "Ốm",
    }
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "filled.docx"
        unfilled = fill_form_copy(
            resolve_template_path(BIEU_MAU, fn),
            out,
            labels,
            answers,
            catalog_filename=fn,
        )
        from docx import Document

        text = "\n".join(p.text for p in Document(str(out)).paragraphs)
        assert "Nguyễn Văn A" in text or "Nguyen" in text
        assert "AT060310" in text
        assert "tu_ngay" in unfilled or "01/03" in text


def test_form_fill_service_wants_fill():
    svc = FormFillService()
    assert svc.wants_fill("Điền giúp tôi giấy xác nhận sinh viên", None)
    assert svc.wants_fill("hủy", FormFillState(status="collecting"))


def test_schemas_file_exists():
    write_schemas_file()
    assert (BIEU_MAU / "field_schemas.json").is_file()
