"""
Schema metadata phẳng cho Qdrant (ý tưởng 7) — không lồng object metadata.
"""

from __future__ import annotations

import json
from typing import Any


def _headers_to_storage(headers: list[str]) -> str:
    clean = [str(h).strip() for h in headers if str(h).strip()]
    return json.dumps(clean, ensure_ascii=False) if clean else "[]"


def build_table_payload(
    base: dict[str, Any],
    *,
    text: str,
    table_headers: list[str],
    section: str = "",
    document_type: str = "table",
    row_count: int = 0,
    table_index: int = 0,
) -> dict[str, Any]:
    payload = dict(base)
    payload.update({
        "text":            text,
        "document_type":   document_type,
        "section":         (section or "")[:300],
        "table_headers":   _headers_to_storage(table_headers),
        "row_count":       int(row_count),
        "table_index":     int(table_index),
        "chunk_role":      "flat",
        "parent_id":       "",
        "parent_text":     "",
        "child_index":     -1,
    })
    return payload


def build_prose_payload(
    base: dict[str, Any],
    *,
    text: str,
    section: str = "",
    document_type: str = "prose",
) -> dict[str, Any]:
    payload = dict(base)
    payload.update({
        "text":            text,
        "document_type":   document_type,
        "section":         (section or "")[:300],
        "table_headers":   "[]",
        "row_count":       0,
        "table_index":     -1,
        "chunk_role":      "flat",
        "parent_id":       "",
        "parent_text":     "",
        "child_index":     -1,
    })
    return payload


def parse_table_headers(raw: str | list | None) -> list[str]:
    if isinstance(raw, list):
        return [str(x) for x in raw]
    if not raw:
        return []
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            return [str(x) for x in data]
    except (json.JSONDecodeError, TypeError):
        pass
    return [p.strip() for p in str(raw).split(",") if p.strip()]
