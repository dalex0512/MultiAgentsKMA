"""
Trích xuất bảng từ PDF (pdfplumber) — giữ hàng/cột cho ingest metadata-rich.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

from config import TABLE_MAX_ROWS_PER_CHUNK

log = logging.getLogger(__name__)

_SECTION_RE = re.compile(
    r"^(phụ lục|phu luc|ma trận|ma tran|bảng điểm|bang diem|mục\s+\d|điều\s+\d|"
    r"chương\s+[ivxlcdm\d]+|phần\s+\d)",
    re.IGNORECASE | re.UNICODE,
)


@dataclass
class TableBlock:
    headers: list[str]
    rows: list[list[str]]
    markdown: str
    section: str = ""
    table_index: int = 0


@dataclass
class PageExtract:
    page: int
    section_hint: str = ""
    tables: list[TableBlock] = field(default_factory=list)
    prose_text: str = ""


def detect_section_hint(page_text: str) -> str:
    for line in (page_text or "").split("\n")[:20]:
        line = line.strip()
        if len(line) < 4:
            continue
        if _SECTION_RE.match(line):
            return line[:300]
    return ""


def _cell_str(v) -> str:
    if v is None:
        return ""
    return str(v).strip().replace("\n", " ")


def _normalize_row(row: list) -> list[str]:
    return [_cell_str(c) for c in row]


def _infer_headers(first_row: list[str], second_row: list[str] | None) -> tuple[list[str], list[list[str]]]:
    """
    Hàng đầu là header nếu không giống MSSV/điểm số thuần.
    """
    if not first_row or not any(first_row):
        return [], []

    header_like = sum(
        1 for c in first_row
        if re.search(r"mssv|mã|mon|điểm|diem|stt|họ tên|ho ten|tên", c, re.I)
    )
    if header_like >= 1 or (second_row and not re.search(r"\b(?:AT|CT)\d{6}\b", first_row[0] or "", re.I)):
        headers = first_row
        data_rows = [second_row] if second_row else []
        return headers, data_rows
    return ["Cột " + str(i + 1) for i in range(len(first_row))], [first_row]


def table_to_markdown(headers: list[str], rows: list[list[str]]) -> str:
    if not headers and not rows:
        return ""
    if not headers and rows:
        width = max(len(r) for r in rows) if rows else 1
        headers = [f"C{i+1}" for i in range(width)]
    cols = len(headers)
    norm_rows = []
    for r in rows:
        cells = (r + [""] * cols)[:cols]
        norm_rows.append(cells)

    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for r in norm_rows:
        lines.append("| " + " | ".join(r) + " |")
    return "\n".join(lines)


def _split_table_chunks(
    block: TableBlock,
    max_rows: int,
) -> list[TableBlock]:
    if len(block.rows) <= max_rows:
        return [block]
    chunks: list[TableBlock] = []
    for i in range(0, len(block.rows), max_rows):
        part_rows = block.rows[i:i + max_rows]
        md = table_to_markdown(block.headers, part_rows)
        chunks.append(
            TableBlock(
                headers=block.headers,
                rows=part_rows,
                markdown=md,
                section=block.section,
                table_index=block.table_index,
            )
        )
    return chunks


def extract_tables_from_pdf_page(pdf_path: Path, page_num: int) -> list[TableBlock]:
    """page_num: 1-based."""
    try:
        import pdfplumber
    except ImportError:
        log.warning("[table] pdfplumber not installed — pip install pdfplumber")
        return []

    tables: list[TableBlock] = []
    try:
        with pdfplumber.open(str(pdf_path)) as pdf:
            if page_num < 1 or page_num > len(pdf.pages):
                return []
            page = pdf.pages[page_num - 1]
            raw_tables = page.extract_tables() or []
            page_text = page.extract_text() or ""
            section = detect_section_hint(page_text)

            for t_idx, raw in enumerate(raw_tables):
                if not raw:
                    continue
                rows = [_normalize_row(r) for r in raw if any(_normalize_row(r))]
                if not rows:
                    continue
                headers, data_rows = _infer_headers(rows[0], rows[1] if len(rows) > 1 else None)
                if headers == rows[0]:
                    data_rows = rows[1:]
                elif not headers:
                    headers, data_rows = _infer_headers(rows[0], None)
                    data_rows = rows if not data_rows else data_rows

                md = table_to_markdown(headers, data_rows)
                if len(md) < 20:
                    continue

                block = TableBlock(
                    headers=headers,
                    rows=data_rows,
                    markdown=md,
                    section=section,
                    table_index=t_idx,
                )
                tables.extend(_split_table_chunks(block, TABLE_MAX_ROWS_PER_CHUNK))

    except Exception as e:
        log.warning("[table] extract failed %s p%s: %s", pdf_path.name, page_num, e)

    return tables


def extract_pdf_pages_rich(pdf_path: Path) -> list[PageExtract]:
    """
    Mỗi trang: bảng (pdfplumber) + phần chữ còn lại (pypdf fallback cho prose).
    """
    from pypdf import PdfReader

    reader = PdfReader(str(pdf_path))
    results: list[PageExtract] = []

    for i, page in enumerate(reader.pages):
        page_num = i + 1
        prose = (page.extract_text() or "").strip()
        section = detect_section_hint(prose)
        tables = extract_tables_from_pdf_page(pdf_path, page_num)

        # Prose: bỏ các dòng trùng header bảng (heuristic nhẹ)
        prose_clean = prose
        if tables and len(prose) > 500:
            prose_clean = prose  # vẫn giữ để không mất chú thích quanh bảng

        results.append(
            PageExtract(
                page=page_num,
                section_hint=section,
                tables=tables,
                prose_text=prose_clean,
            )
        )

    return results
