"""
Ingest metadata-rich (ý tưởng 7) — bảng + prose cho diem_thi / ma_tran.
"""

from __future__ import annotations

import logging
import uuid
from pathlib import Path

from config import (
    TABLE_INGEST_AGENTS,
    USE_TABLE_METADATA_INGEST,
    PARENT_CHILD_AGENTS,
    USE_PARENT_CHILD_INGEST,
)
from utils.ingest.metadata_schema import build_prose_payload, build_table_payload
from utils.ingest.table_extractor import PageExtract, extract_pdf_pages_rich
from utils.chunking.parent_child import (
    build_document_child_records,
    uses_parent_child_ingest,
)

log = logging.getLogger(__name__)


def _chunk_text_flat(text: str) -> list[str]:
    from config import CHUNK_SIZE, CHUNK_OVERLAP
    words = text.split()
    chunks, start = [], 0
    while start < len(words):
        end = min(start + CHUNK_SIZE, len(words))
        chunks.append(" ".join(words[start:end]))
        start += CHUNK_SIZE - CHUNK_OVERLAP
    return chunks


def uses_table_metadata_ingest(agent_id: str) -> bool:
    return USE_TABLE_METADATA_INGEST and agent_id in TABLE_INGEST_AGENTS


def make_table_point_id(source: str, page: int, table_index: int, part: int) -> str:
    key = f"{source}::p{page}::table{table_index}::part{part}"
    return str(uuid.uuid5(uuid.NAMESPACE_URL, key))


def make_prose_point_id(source: str, page: int, chunk_idx: int) -> str:
    key = f"{source}::p{page}::prose{chunk_idx}"
    return str(uuid.uuid5(uuid.NAMESPACE_URL, key))


def _document_type_for_agent(agent_id: str, is_table: bool) -> str:
    if not is_table:
        return "prose"
    if agent_id == "ma_tran":
        return "matrix"
    return "table"


def iter_ingest_records(
    path: Path,
    pages_plain: list[dict],
    source_key: str,
    agent_id: str,
) -> list[tuple[str, dict, int]]:
    """
    Trả list (embed_text, payload, page) cho upsert.
    """
    records: list[tuple[str, dict, int]] = []

    if path.suffix.lower() != ".pdf":
        for pg in pages_plain:
            text = pg.get("text", "")
            if not text.strip():
                continue
            records.append((
                text,
                build_prose_payload(
                    {},
                    text=text,
                    section="",
                    document_type="prose",
                ),
                int(pg.get("page", 1)),
            ))
        return records

    rich_pages = extract_pdf_pages_rich(path)
    if not rich_pages:
        rich_pages = [
            PageExtract(page=int(p.get("page", 1)), prose_text=p.get("text", ""))
            for p in pages_plain
        ]

    prose_global_idx = 0
    use_pc_prose = (
        USE_PARENT_CHILD_INGEST
        and agent_id in PARENT_CHILD_AGENTS
        and uses_parent_child_ingest(agent_id)
    )

    for pe in rich_pages:
        section = pe.section_hint or ""

        for tbl in pe.tables:
            doc_type = _document_type_for_agent(agent_id, True)
            payload = build_table_payload(
                {},
                text=tbl.markdown,
                table_headers=tbl.headers,
                section=tbl.section or section,
                document_type=doc_type,
                row_count=len(tbl.rows),
                table_index=tbl.table_index,
            )
            records.append((tbl.markdown, payload, pe.page))

        prose = (pe.prose_text or "").strip()
        if not prose:
            continue

        if use_pc_prose and len(prose) > 400:
            child_recs = build_document_child_records(
                [{"page": pe.page, "text": prose}],
                source_key,
            )
            for rec in child_recs:
                p = build_prose_payload(
                    {},
                    text=rec.child_text,
                    section=section,
                    document_type="prose",
                )
                p["parent_text"] = rec.parent_text
                p["parent_id"] = rec.parent_id
                p["child_index"] = rec.child_index
                p["chunk_role"] = "child"
                records.append((rec.child_text, p, pe.page))
        else:
            for chunk in _chunk_text_flat(prose):
                if not chunk.strip():
                    continue
                p = build_prose_payload(
                    {},
                    text=chunk,
                    section=section,
                    document_type="prose",
                )
                records.append((chunk, p, pe.page))
                prose_global_idx += 1

    if not records and pages_plain:
        log.warning("[rich_ingest] no table/prose records — fallback plain for %s", source_key)
        for pg in pages_plain:
            text = pg.get("text", "")
            if text.strip():
                records.append((
                    text[:8000],
                    build_prose_payload({}, text=text[:8000], document_type="prose"),
                    int(pg.get("page", 1)),
                ))

    log.info(
        "[rich_ingest] %s → %s points (tables=%s)",
        source_key,
        len(records),
        sum(1 for _, p, _ in records if p.get("document_type") in ("table", "matrix")),
    )
    return records
