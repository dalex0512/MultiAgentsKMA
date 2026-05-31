"""
Parent–Child chunking (ý tưởng 5): embed child nhỏ, LLM nhận parent đầy đủ.

- Parent ~1500 ký tự (ưu tiên cắt theo Điều/Mục/đoạn)
- Child ~200 ký tự (overlap nhỏ giữa các child cùng parent)
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from config import (
    PARENT_CHILD_AGENTS,
    PARENT_CHUNK_CHARS,
    PARENT_CHUNK_OVERLAP_CHARS,
    CHILD_CHUNK_CHARS,
    CHILD_CHUNK_OVERLAP_CHARS,
    USE_PARENT_CHILD_INGEST,
)

# Cắt theo cấu trúc văn bản pháp lý / học thuật tiếng Việt
_STRUCT_SPLITTERS: list[re.Pattern] = [
    re.compile(r"(?=\n\s*Điều\s+\d+)", re.IGNORECASE | re.UNICODE),
    re.compile(r"(?=\n\s*Mục\s+\d+)", re.IGNORECASE | re.UNICODE),
    re.compile(r"(?=\n\s*Chương\s+(?:[IVXLCDM]+|\d+))", re.IGNORECASE | re.UNICODE),
    re.compile(r"(?=\n\s*PHỤ LỤC)", re.IGNORECASE | re.UNICODE),
    re.compile(r"\n\n+"),
]

_SENTENCE_BREAKS = (". ", ".\n", "; ", ":\n", "\n", ", ", " ")


def uses_parent_child_ingest(agent_id: str) -> bool:
    return USE_PARENT_CHILD_INGEST and agent_id in PARENT_CHILD_AGENTS


def _normalize_text(text: str) -> str:
    t = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    t = re.sub(r"[ \t]+\n", "\n", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


def _split_by_char_window(text: str, max_chars: int, overlap: int) -> list[str]:
    """Cắt cửa sổ ký tự, ưu tiên ngắt tại ranh giới câu/đoạn."""
    text = text.strip()
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]

    chunks: list[str] = []
    start = 0
    n = len(text)
    while start < n:
        end = min(start + max_chars, n)
        if end < n:
            window = text[start:end]
            cut = -1
            for sep in _SENTENCE_BREAKS:
                idx = window.rfind(sep)
                if idx > int(max_chars * 0.45):
                    cut = idx + len(sep)
                    break
            if cut > 0:
                end = start + cut
        piece = text[start:end].strip()
        if piece:
            chunks.append(piece)
        if end >= n:
            break
        next_start = end - overlap
        start = next_start if next_start > start else end
    return chunks


def _structural_segments(text: str) -> list[str]:
    """Tách theo Điều/Mục/Chương hoặc đoạn đôi newline."""
    parts = [text]
    for pat in _STRUCT_SPLITTERS:
        nxt: list[str] = []
        for seg in parts:
            split = pat.split(seg)
            split = [s.strip() for s in split if s and s.strip()]
            nxt.extend(split if len(split) > 1 else [seg])
        parts = nxt
    return [p for p in parts if p.strip()]


def _merge_segments_to_parents(segments: list[str], max_chars: int) -> list[str]:
    """Gom đoạn nhỏ liền kề thành parent không vượt max_chars."""
    if not segments:
        return []
    merged: list[str] = []
    buf = ""
    for seg in segments:
        if not buf:
            buf = seg
            continue
        candidate = f"{buf}\n{seg}"
        if len(candidate) <= max_chars:
            buf = candidate
        else:
            merged.append(buf)
            buf = seg
    if buf:
        merged.append(buf)

    final: list[str] = []
    for seg in merged:
        if len(seg) <= max_chars:
            final.append(seg)
        else:
            final.extend(
                _split_by_char_window(seg, max_chars, PARENT_CHUNK_OVERLAP_CHARS)
            )
    return final


def split_parent_segments(
    text: str,
    max_chars: int | None = None,
    overlap: int | None = None,
) -> list[str]:
    max_chars = max_chars or PARENT_CHUNK_CHARS
    overlap = overlap or PARENT_CHUNK_OVERLAP_CHARS
    text = _normalize_text(text)
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]

    segments = _structural_segments(text)
    if not segments:
        segments = [text]
    parents = _merge_segments_to_parents(segments, max_chars)
    if not parents:
        return _split_by_char_window(text, max_chars, overlap)
    return parents


def split_child_segments(
    parent_text: str,
    max_chars: int | None = None,
    overlap: int | None = None,
) -> list[str]:
    max_chars = max_chars or CHILD_CHUNK_CHARS
    overlap = overlap or CHILD_CHUNK_OVERLAP_CHARS
    parent_text = parent_text.strip()
    if not parent_text:
        return []
    if len(parent_text) <= max_chars:
        return [parent_text]
    return _split_by_char_window(parent_text, max_chars, overlap)


@dataclass(frozen=True)
class ChildIngestRecord:
    """Một điểm vector (child) kèm metadata parent."""

    child_text: str
    parent_text: str
    parent_id: str
    child_index: int
    page: int


def build_page_child_records(
    page_text: str,
    page: int,
    source_key: str,
    parent_index_start: int = 0,
) -> tuple[list[ChildIngestRecord], int]:
    """
    Tạo toàn bộ child records cho một trang PDF.
    Trả (records, parent_index_next).
    """
    parents = split_parent_segments(page_text)
    records: list[ChildIngestRecord] = []
    p_idx = parent_index_start

    for parent in parents:
        parent_id = f"{source_key}::p{page}::parent{p_idx}"
        children = split_child_segments(parent)
        if not children and parent:
            children = [parent[:CHILD_CHUNK_CHARS]]

        for c_idx, child in enumerate(children):
            child = child.strip()
            if not child:
                continue
            records.append(
                ChildIngestRecord(
                    child_text=child,
                    parent_text=parent,
                    parent_id=parent_id,
                    child_index=c_idx,
                    page=page,
                )
            )
        p_idx += 1

    return records, p_idx


def build_document_child_records(
    pages: list[dict],
    source_key: str,
) -> list[ChildIngestRecord]:
    """Gom child records cho mọi trang {page, text}."""
    all_records: list[ChildIngestRecord] = []
    p_idx = 0
    for pg in pages:
        recs, p_idx = build_page_child_records(
            pg.get("text", ""),
            int(pg.get("page", 1)),
            source_key,
            parent_index_start=p_idx,
        )
        all_records.extend(recs)
    return all_records
