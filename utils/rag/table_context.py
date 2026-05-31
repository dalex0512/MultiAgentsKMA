"""
Persona / prompt bổ sung khi context có bảng (ý tưởng 7).
"""

from __future__ import annotations

TABLE_DOCUMENT_TYPES = frozenset({"table", "matrix"})


TABLE_PERSONA_SUFFIX = (
    "\nBạn đang đọc TÀI LIỆU DẠNG BẢNG (hàng/cột). "
    "Giữ đúng cấu trúc: mỗi hàng là một bản ghi; không gộp cột; "
    "không đảo MSSV, mã môn và điểm. "
    "Khi liệt kê, ưu tiên bảng markdown hoặc từng dòng rõ ràng."
)

MATRIX_PERSONA_SUFFIX = (
    "\nBạn đang đọc MA TRẬN ĐỀ THI (bảng cấu trúc). "
    "Chú ý mức độ Bloom, tỷ lệ %, nhóm nội dung theo đúng cột trong ma trận; "
    "không suy diễn phần không có trong bảng."
)

GRADER_TABLE_NOTE = (
    "Lưu ý: tài liệu là bảng có cột/hàng — chỉ YES nếu có dữ liệu trực tiếp "
    "(MSSV, điểm, % ma trận, môn học…) khớp câu hỏi."
)


def docs_contain_tables(docs: list[dict]) -> bool:
    return any((d.get("document_type") or "prose") in TABLE_DOCUMENT_TYPES for d in docs)


def docs_contain_matrix(docs: list[dict]) -> bool:
    return any((d.get("document_type") or "") == "matrix" for d in docs)


def persona_suffix_for_docs(docs: list[dict], agent_id: str | None = None) -> str:
    if not docs:
        if agent_id == "ma_tran":
            return MATRIX_PERSONA_SUFFIX
        if agent_id in ("diem_thi", "danh_sach_thi", "lich_thi"):
            return TABLE_PERSONA_SUFFIX
        return ""
    if docs_contain_matrix(docs):
        return MATRIX_PERSONA_SUFFIX
    if docs_contain_tables(docs):
        return TABLE_PERSONA_SUFFIX
    return ""


def persona_suffix_for_agent(agent_id: str | None) -> str:
    if agent_id == "ma_tran":
        return MATRIX_PERSONA_SUFFIX
    if agent_id in ("diem_thi", "danh_sach_thi", "lich_thi"):
        return TABLE_PERSONA_SUFFIX
    return ""


def build_context_header(docs: list[dict]) -> str:
    """Dòng hướng dẫn prepend vào context khi có metadata bảng."""
    headers = []
    for d in docs[:3]:
        dtype = d.get("document_type", "prose")
        if dtype not in TABLE_DOCUMENT_TYPES:
            continue
        sec = d.get("section") or ""
        th = d.get("table_headers") or "[]"
        headers.append(
            f"[{dtype}] section={sec!r} headers={th}"
        )
    if not headers:
        return ""
    return "Metadata tài liệu:\n" + "\n".join(headers) + "\n\n"
