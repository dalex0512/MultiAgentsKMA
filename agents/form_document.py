"""
Đọc / điền file Word (.docx, .doc) — luôn ghi ra bản sao, không sửa file gốc trong docs/.
"""

import logging
import re
import shutil
import subprocess
from pathlib import Path

log = logging.getLogger(__name__)


def extract_docx_text(path: Path) -> str:
    from docx import Document

    doc = Document(str(path))
    parts: list[str] = []
    for para in doc.paragraphs:
        t = para.text.strip()
        if t:
            parts.append(t)
    for table in doc.tables:
        for row in table.rows:
            row_text = "\t".join(c.text.strip() for c in row.cells if c.text.strip())
            if row_text.strip():
                parts.append(row_text)
    return "\n".join(parts)


def extract_doc_text(path: Path) -> str:
    try:
        result = subprocess.run(
            ["antiword", str(path)],
            capture_output=True,
            text=True,
            timeout=30,
            encoding="utf-8",
            errors="ignore",
        )
        text = (result.stdout or "").strip()
        if len(text) > 40:
            return text
    except Exception as e:
        log.debug(f"antiword unavailable for {path.name}: {e}")

    try:
        import win32com.client  # type: ignore

        word = win32com.client.Dispatch("Word.Application")
        word.Visible = False
        doc = word.Documents.Open(str(path.resolve()))
        text = doc.Content.Text.replace("\r", "\n")
        doc.Close(False)
        word.Quit()
        return text.strip()
    except Exception as e:
        log.warning(f"win32com extract failed {path.name}: {e}")

    raw = path.read_bytes()
    text = raw.decode("utf-16-le", errors="ignore")
    lines = [
        ln.strip()
        for ln in text.split("\n")
        if 4 < len(ln.strip()) < 220 and re.search(r"[A-Za-zÀ-ỹ]", ln)
    ]
    return "\n".join(lines[:120])


def extract_form_text(path: Path) -> str:
    ext = path.suffix.lower()
    if ext == ".docx":
        return extract_docx_text(path)
    if ext == ".doc":
        return extract_doc_text(path)
    raise ValueError(f"Unsupported form format: {ext}")


def _slot_is_empty(text: str, label: str) -> bool:
    """Ô trống nếu sau nhãn chỉ có tab/khoảng trắng hoặc nhãn trường kế tiếp."""
    for sep in (":", "："):
        needle = label + sep
        if needle not in text:
            continue
        idx = text.index(needle) + len(needle)
        rest = text[idx:]
        for part in rest.split("\t"):
            chunk = part.strip()
            if not chunk:
                continue
            if chunk.endswith(":") or chunk.endswith("："):
                return True
            if re.fullmatch(r"[_…\.\s]+", chunk):
                continue
            return len(chunk) < 2
        return True
    return False


def _fill_label_in_text(text: str, label: str, value: str) -> str:
    """Chèn giá trị sau nhãn (hỗ trợ nhiều trường trên cùng một dòng Word)."""
    if not value or label not in text:
        return text
    if not _slot_is_empty(text, label):
        return text

    for sep in (":", "："):
        needle = label + sep
        if needle not in text:
            continue
        idx = text.index(needle) + len(needle)
        rest = text[idx:]
        return text[:idx] + "\t" + value + rest

    return text.replace(label, f"{label}: {value}", 1)


# Nhãn thay thế khi LLM/key khác với chữ trên mẫu Word
LABEL_ALIASES: dict[str, list[str]] = {
    "ho_ten": ["Em tên là", "Họ và tên sinh viên", "Họ và tên", "Xác nhận sinh viên"],
    "so_dien_thoai": ["Số điện thoại"],
    "sdt": ["Số điện thoại"],
    "nganh": ["Ngành"],
    "lop": ["Lớp"],
    "mssv": ["Mã sinh viên"],
    "ma_sinh_vien": ["Mã sinh viên"],
    "ngay_sinh": ["Ngày, tháng, năm sinh", "Ngày sinh"],
    "gioi_tinh": ["Giới tính"],
    "cccd": ["Số CCCD", "Số CCCD/CMND"],
    "so_cccd": ["Số CCCD"],
    "ngay_cap": ["Ngày cấp"],
    "ngay_cap_cccd": ["Ngày cấp"],
    "noi_cap": ["Nơi cấp"],
    "ho_khau": ["Hộ khẩu thường trú"],
    "ho_khau_thuong_tru": ["Hộ khẩu thường trú"],
    "ly_do": ["Lý do"],
}


def _labels_for_field(key: str, primary_label: str) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []

    def add(lbl: str) -> None:
        lbl = lbl.strip()
        if lbl and lbl not in seen:
            seen.add(lbl)
            out.append(lbl)

    add(primary_label)
    for alias in LABEL_ALIASES.get(key, []):
        add(alias)
    return out


def _fill_paragraph_text(text: str, field_labels: dict[str, str], answers: dict[str, str]) -> str:
    """Điền theo thứ tự nhãn dài trước (tránh khớp nhầm trên dòng nhiều trường)."""
    jobs: list[tuple[int, str, str]] = []
    for key, primary in field_labels.items():
        val = (answers.get(key) or "").strip()
        if not val:
            continue
        for label in _labels_for_field(key, primary):
            pos = text.find(label)
            if pos >= 0:
                jobs.append((pos, label, val))
                break

    jobs.sort(key=lambda x: (-len(x[1]), x[0]))
    new_t = text
    for _, label, val in jobs:
        new_t = _fill_label_in_text(new_t, label, val)
    return new_t


def fill_docx(template: Path, output: Path, field_labels: dict[str, str], answers: dict[str, str]) -> None:
    from docx import Document

    shutil.copy2(template, output)
    doc = Document(str(output))

    for para in doc.paragraphs:
        new_t = _fill_paragraph_text(para.text, field_labels, answers)
        if new_t != para.text:
            para.text = new_t

    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for para in cell.paragraphs:
                    new_t = _fill_paragraph_text(para.text, field_labels, answers)
                    if new_t != para.text:
                        para.text = new_t

    doc.save(str(output))


def fill_doc_win32(template: Path, output: Path, field_labels: dict[str, str], answers: dict[str, str]) -> None:
    import win32com.client  # type: ignore

    shutil.copy2(template, output)
    word = win32com.client.Dispatch("Word.Application")
    word.Visible = False
    doc = word.Documents.Open(str(output.resolve()))

    for key, primary in field_labels.items():
        value = (answers.get(key) or "").strip()
        if not value:
            continue
        for label in _labels_for_field(key, primary):
            for find_text in (f"{label}:", f"{label}：", label):
                rng = doc.Content
                f = rng.Find
                f.ClearFormatting()
                f.Text = find_text
                f.Forward = True
                f.Wrap = 0  # wdFindStop
                if f.Execute():
                    rng.SetRange(rng.End, rng.End)
                    rng.InsertAfter(f"\t{value}")
                    break
            else:
                continue
            break

    doc.Save()
    doc.Close(False)
    word.Quit()


def fill_form_copy(
    template: Path,
    output: Path,
    field_labels: dict[str, str],
    answers: dict[str, str],
) -> None:
    """Điền bản sao; template trong docs/ không bị đổi."""
    output.parent.mkdir(parents=True, exist_ok=True)
    ext = template.suffix.lower()
    if ext == ".docx":
        fill_docx(template, output, field_labels, answers)
    elif ext == ".doc":
        fill_doc_win32(template, output, field_labels, answers)
    else:
        raise ValueError(f"Unsupported: {ext}")
