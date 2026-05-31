"""
Ingest toàn bộ docs/ theo domain agents → Qdrant (metadata agent_id).

Parent–Child (tuyen_sinh, khao_thi, ma_tran): embed child ~200 chars, payload parent_text.
Table metadata (diem_thi, ma_tran, danh_sach_thi, lich_thi): chunk bảng có metadata cột/hàng.
Flat (bieu_mau): chunk theo từ như trước.

Usage:
  python ingest_all.py              # ingest tất cả
  python ingest_all.py --domain khao_thi
"""

import sys
import uuid
import time
import json
import logging
import subprocess
import argparse
from pathlib import Path

from pypdf import PdfReader
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance, VectorParams, PointStruct,
    Filter, FieldCondition, MatchValue,
    PayloadSchemaType, TextIndexParams, TokenizerType,
)

from config import (
    QDRANT_URL, QDRANT_API_KEY,
    COLLECTION_NAME, EMBED_MODEL, CHUNK_SIZE, CHUNK_OVERLAP,
    DOCS_ROOT, AGENTS,
    USE_PARENT_CHILD_INGEST, PARENT_CHILD_AGENTS,
    embed_client,
)
from utils.chunking.parent_child import (
    build_document_child_records,
    uses_parent_child_ingest,
)
from utils.ingest.rich_ingest import (
    iter_ingest_records,
    make_table_point_id,
    make_prose_point_id,
    uses_table_metadata_ingest,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

EMBED_DIM = 1536

openai_client = embed_client()
qdrant_client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)


def make_flat_point_id(source: str, page: int, chunk_idx: int) -> str:
    key = f"{source}::page{page}::chunk{chunk_idx}"
    return str(uuid.uuid5(uuid.NAMESPACE_URL, key))


def make_child_point_id(source: str, parent_id: str, child_index: int) -> str:
    key = f"{source}::{parent_id}::child{child_index}"
    return str(uuid.uuid5(uuid.NAMESPACE_URL, key))


def chunk_text_flat(text: str) -> list[str]:
    """Chunk phẳng theo từ (legacy — diem_thi, bieu_mau)."""
    words = text.split()
    chunks, start = [], 0
    while start < len(words):
        end = min(start + CHUNK_SIZE, len(words))
        chunks.append(" ".join(words[start:end]))
        start += CHUNK_SIZE - CHUNK_OVERLAP
    return chunks


def embed_batch(texts: list[str]) -> list[list[float]]:
    resp = openai_client.embeddings.create(input=texts, model=EMBED_MODEL)
    return [item.embedding for item in resp.data]


def extract_pdf(path: Path) -> list[dict]:
    reader = PdfReader(str(path))
    pages = []
    for i, page in enumerate(reader.pages):
        text = (page.extract_text() or "").strip()
        if text:
            pages.append({"page": i + 1, "text": text})
    return pages


def extract_docx(path: Path) -> list[dict]:
    from docx import Document
    doc = Document(str(path))
    text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    return [{"page": 1, "text": text}] if text.strip() else []


def extract_doc(path: Path) -> list[dict]:
    try:
        result = subprocess.run(
            ["antiword", str(path)],
            capture_output=True, text=True, timeout=30,
            encoding="utf-8", errors="ignore",
        )
        text = result.stdout.strip()
        return [{"page": 1, "text": text}] if text else []
    except Exception as e:
        log.warning(f"antiword failed {path.name}: {e}")
        return []


def extract_file(path: Path) -> list[dict]:
    ext = path.suffix.lower()
    if ext == ".pdf":
        return extract_pdf(path)
    if ext == ".docx":
        return extract_docx(path)
    if ext == ".doc":
        return extract_doc(path)
    return []


def ensure_collection():
    existing = [c.name for c in qdrant_client.get_collections().collections]
    if COLLECTION_NAME not in existing:
        qdrant_client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=EMBED_DIM, distance=Distance.COSINE),
        )
        log.info(f"Created collection: {COLLECTION_NAME}")

    for field in ("source", "doc_type", "agent_id", "parent_id", "chunk_role", "document_type"):
        try:
            qdrant_client.create_payload_index(
                COLLECTION_NAME, field, field_schema=PayloadSchemaType.KEYWORD,
            )
        except Exception:
            pass
    try:
        qdrant_client.create_payload_index(
            COLLECTION_NAME,
            field_name="text",
            field_schema=TextIndexParams(
                type="text",
                tokenizer=TokenizerType.WORD,
                min_token_len=2,
                max_token_len=30,
                lowercase=True,
            ),
        )
    except Exception:
        pass
    log.info("Payload indexes ensured (source, agent_id, parent_id, chunk_role, text)")


def delete_source(source_key: str):
    try:
        qdrant_client.delete(
            collection_name=COLLECTION_NAME,
            points_selector=Filter(must=[
                FieldCondition(key="source", match=MatchValue(value=source_key))
            ]),
        )
    except Exception as e:
        log.warning(f"Delete failed {source_key}: {e}")


def _base_payload(
    *,
    source_key: str,
    page: int,
    agent_id: str,
    doc_type: str,
    display_name: str,
    category: str,
    download_url: str,
    drive_id: str,
) -> dict:
    return {
        "source":       source_key,
        "page":         page,
        "agent_id":     agent_id,
        "doc_type":     doc_type,
        "display_name": display_name,
        "category":     category,
        "download_url": download_url,
        "drive_id":     drive_id,
    }


def _ingest_flat_chunks(
    pages: list[dict],
    source_key: str,
    meta: dict,
    agent_id: str,
    folder: str,
    fname: str,
) -> int:
    flat: list[tuple[str, int]] = []
    for pg in pages:
        for ch in chunk_text_flat(pg["text"]):
            flat.append((ch, pg["page"]))

    if not flat:
        return 0

    display_name = meta.get("display_name", fname)
    category = meta.get("category", "")
    drive_id = meta.get("drive_id", "")
    doc_type = "bieu_mau" if agent_id == "bieu_mau" else "pdf"
    download_url = f"/docs/{folder}/{fname}"

    total = 0
    batch_size = 20
    for i in range(0, len(flat), batch_size):
        batch_chunks = [c for c, _ in flat[i:i + batch_size]]
        batch_pages = [p for _, p in flat[i:i + batch_size]]
        vectors = embed_batch(batch_chunks)
        points = []
        for j, (chunk, pg, vec) in enumerate(zip(batch_chunks, batch_pages, vectors)):
            payload = _base_payload(
                source_key=source_key,
                page=pg,
                agent_id=agent_id,
                doc_type=doc_type,
                display_name=display_name,
                category=category,
                download_url=download_url,
                drive_id=drive_id,
            )
            payload.update({
                "text":          chunk,
                "chunk_role":    "flat",
                "parent_id":     "",
                "parent_text":   "",
                "child_index":   -1,
                "document_type": "prose",
                "section":       "",
                "table_headers": "[]",
                "row_count":     0,
                "table_index":   -1,
            })
            points.append(
                PointStruct(
                    id=make_flat_point_id(source_key, pg, i + j),
                    vector=vec,
                    payload=payload,
                )
            )
        qdrant_client.upsert(collection_name=COLLECTION_NAME, points=points)
        total += len(points)
        time.sleep(0.08)
    return total


def _ingest_parent_child(
    pages: list[dict],
    source_key: str,
    meta: dict,
    agent_id: str,
    folder: str,
    fname: str,
) -> int:
    records = build_document_child_records(pages, source_key)
    if not records:
        return 0

    display_name = meta.get("display_name", fname)
    category = meta.get("category", "")
    drive_id = meta.get("drive_id", "")
    doc_type = "pdf"
    download_url = f"/docs/{folder}/{fname}"

    total = 0
    batch_size = 20
    for i in range(0, len(records), batch_size):
        batch = records[i:i + batch_size]
        vectors = embed_batch([r.child_text for r in batch])
        points = []
        for rec, vec in zip(batch, vectors):
            payload = _base_payload(
                source_key=source_key,
                page=rec.page,
                agent_id=agent_id,
                doc_type=doc_type,
                display_name=display_name,
                category=category,
                download_url=download_url,
                drive_id=drive_id,
            )
            payload.update({
                "text":          rec.child_text,
                "parent_text":   rec.parent_text,
                "parent_id":     rec.parent_id,
                "child_index":   rec.child_index,
                "chunk_role":    "child",
                "document_type": "prose",
                "section":       "",
                "table_headers": "[]",
                "row_count":     0,
                "table_index":   -1,
            })
            points.append(
                PointStruct(
                    id=make_child_point_id(source_key, rec.parent_id, rec.child_index),
                    vector=vec,
                    payload=payload,
                )
            )
        qdrant_client.upsert(collection_name=COLLECTION_NAME, points=points)
        total += len(points)
        time.sleep(0.08)

    n_parents = len({r.parent_id for r in records})
    log.info(f"    parent-child: {total} children, {n_parents} parents")
    return total


def _ingest_metadata_rich(
    path: Path,
    pages: list[dict],
    source_key: str,
    meta: dict,
    agent_id: str,
    folder: str,
    fname: str,
) -> int:
    """Metadata-rich: bảng (pdfplumber) + prose (ý tưởng 7)."""
    display_name = meta.get("display_name", fname)
    category = meta.get("category", "")
    drive_id = meta.get("drive_id", "")
    doc_type = "pdf"
    download_url = f"/docs/{folder}/{fname}"

    raw_records = iter_ingest_records(path, pages, source_key, agent_id)
    if not raw_records:
        return 0

    total = 0
    batch_size = 20
    table_part_counter: dict[tuple[int, int], int] = {}

    for i in range(0, len(raw_records), batch_size):
        batch = raw_records[i:i + batch_size]
        vectors = embed_batch([t for t, _, _ in batch])
        points = []
        for (embed_text, partial, page), vec in zip(batch, vectors):
            payload = _base_payload(
                source_key=source_key,
                page=page,
                agent_id=agent_id,
                doc_type=doc_type,
                display_name=display_name,
                category=category,
                download_url=download_url,
                drive_id=drive_id,
            )
            payload.update(partial)

            dtype = payload.get("document_type", "prose")
            if dtype in ("table", "matrix"):
                t_idx = int(payload.get("table_index", 0))
                key = (page, t_idx)
                part = table_part_counter.get(key, 0)
                table_part_counter[key] = part + 1
                pid = make_table_point_id(source_key, page, t_idx, part)
            elif payload.get("chunk_role") == "child" and payload.get("parent_id"):
                pid = make_child_point_id(
                    source_key, payload["parent_id"], int(payload.get("child_index", 0)),
                )
            else:
                pid = make_prose_point_id(source_key, page, i + len(points))

            points.append(PointStruct(id=pid, vector=vec, payload=payload))

        qdrant_client.upsert(collection_name=COLLECTION_NAME, points=points)
        total += len(points)
        time.sleep(0.08)

    n_tables = sum(1 for _, p, _ in raw_records if p.get("document_type") in ("table", "matrix"))
    log.info(f"    metadata-rich: {total} points ({n_tables} table/matrix chunks)")
    return total


def ingest_document(
    path: Path,
    agent_id: str,
    folder: str,
    *,
    catalog: dict | None = None,
) -> int:
    fname = path.name
    meta = (catalog or {}).get(fname, {})
    display_name = meta.get("display_name", fname)
    source_key = f"{folder}/{fname}"

    if uses_table_metadata_ingest(agent_id):
        mode = "metadata-rich"
    elif uses_parent_child_ingest(agent_id):
        mode = "parent-child"
    else:
        mode = "flat"
    log.info(f"  [{agent_id}] {source_key} (ingest={mode})")

    delete_source(source_key)
    pages = extract_file(path)
    if not pages:
        stub = (
            f"Tài liệu KMA — {display_name}. "
            f"Phạm vi: {AGENTS[agent_id]['description'][:200]}. "
            f"File: {fname}."
        )
        pages = [{"page": 1, "text": stub}]
        log.warning(f"    Stub text for {fname}")

    if uses_table_metadata_ingest(agent_id):
        total = _ingest_metadata_rich(
            path, pages, source_key, meta, agent_id, folder, fname,
        )
    elif uses_parent_child_ingest(agent_id):
        total = _ingest_parent_child(pages, source_key, meta, agent_id, folder, fname)
    else:
        total = _ingest_flat_chunks(pages, source_key, meta, agent_id, folder, fname)

    log.info(f"    {total} vector points")
    return total


def ingest_domain(agent_id: str) -> int:
    cfg = AGENTS[agent_id]
    folder = cfg["folder"]
    dirpath = Path(DOCS_ROOT) / folder
    if not dirpath.is_dir():
        log.error(f"Missing folder: {dirpath}")
        return 0

    catalog = None
    if agent_id == "bieu_mau":
        cat_path = dirpath / "catalog.json"
        if cat_path.exists():
            catalog = json.loads(cat_path.read_text(encoding="utf-8"))

    exts = {".pdf", ".docx", ".doc"}
    files = sorted(f for f in dirpath.iterdir() if f.suffix.lower() in exts)
    log.info(f"Domain {agent_id}: {len(files)} files")

    total = 0
    for f in files:
        total += ingest_document(f, agent_id, folder, catalog=catalog)
    return total


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--domain", choices=list(AGENTS.keys()), default=None)
    args = parser.parse_args()

    log.info(
        "Parent-child ingest: %s (agents=%s)",
        USE_PARENT_CHILD_INGEST,
        ",".join(sorted(PARENT_CHILD_AGENTS)),
    )
    from config import USE_TABLE_METADATA_INGEST, TABLE_INGEST_AGENTS
    log.info(
        "Table metadata ingest: %s (agents=%s)",
        USE_TABLE_METADATA_INGEST,
        ",".join(sorted(TABLE_INGEST_AGENTS)),
    )
    ensure_collection()
    domains = [args.domain] if args.domain else list(AGENTS.keys())
    grand = 0
    for aid in domains:
        log.info(f"=== Ingesting agent: {aid} ===")
        grand += ingest_domain(aid)

    log.info(f"\n✓ Done. Total vector points indexed: {grand}")


if __name__ == "__main__":
    main()
