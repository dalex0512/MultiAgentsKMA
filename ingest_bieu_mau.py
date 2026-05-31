"""
Ingest biểu mẫu đơn từ KMA vào Qdrant.
Hỗ trợ: .pdf (pypdf), .docx (python-docx), .doc (antiword)

Usage: python ingest_bieu_mau.py
"""

import sys, uuid, time, json, logging, subprocess
from pathlib import Path


def make_point_id(source: str, page: int, chunk_idx: int) -> str:
    """Deterministic UUID5 — upsert thay vì tạo bản sao khi re-ingest."""
    key = f"{source}::page{page}::chunk{chunk_idx}"
    return str(uuid.uuid5(uuid.NAMESPACE_URL, key))

import numpy as np
from pypdf import PdfReader
from docx import Document
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance, VectorParams, PointStruct,
    Filter, FieldCondition, MatchValue,
    PayloadSchemaType,
)

from config import (
    QDRANT_URL, QDRANT_API_KEY,
    COLLECTION_NAME, EMBED_MODEL, CHUNK_SIZE, CHUNK_OVERLAP,
    embed_client,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

BIEU_MAU_DIR = Path(__file__).parent / "docs" / "bieu_mau"
CATALOG_PATH = BIEU_MAU_DIR / "catalog.json"
EMBED_DIM    = 1536
SERVER_BASE  = "/docs/bieu_mau"   # served by FastAPI StaticFiles

openai_client  = embed_client()
qdrant_client  = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)


# ── Text extractors ──────────────────────────────────────────────────────────

def extract_pdf(path: Path) -> list[dict]:
    reader = PdfReader(str(path))
    pages = []
    for i, page in enumerate(reader.pages):
        text = (page.extract_text() or "").strip()
        if text:
            pages.append({"page": i + 1, "text": text})
    return pages


def extract_docx(path: Path) -> list[dict]:
    doc   = Document(str(path))
    text  = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    if not text.strip():
        return []
    return [{"page": 1, "text": text}]


def extract_doc(path: Path) -> list[dict]:
    try:
        result = subprocess.run(
            ["antiword", str(path)],
            capture_output=True, text=True, timeout=30, encoding="utf-8", errors="ignore"
        )
        text = result.stdout.strip()
        if not text:
            return []
        return [{"page": 1, "text": text}]
    except Exception as e:
        log.warning(f"antiword failed for {path.name}: {e}")
        return []


def extract_text(path: Path) -> list[dict]:
    ext = path.suffix.lower()
    if ext == ".pdf":
        return extract_pdf(path)
    elif ext == ".docx":
        return extract_docx(path)
    elif ext == ".doc":
        return extract_doc(path)
    else:
        log.warning(f"Unsupported format: {path.name}")
        return []


# ── Chunking / Embedding ─────────────────────────────────────────────────────

def chunk_text(text: str) -> list[str]:
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


# ── Collection ───────────────────────────────────────────────────────────────

def ensure_collection():
    existing = [c.name for c in qdrant_client.get_collections().collections]
    if COLLECTION_NAME not in existing:
        qdrant_client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=EMBED_DIM, distance=Distance.COSINE),
        )
        log.info(f"Created collection: {COLLECTION_NAME}")

    # Payload indexes — cần để filter delete hoạt động
    for field in ("source", "doc_type"):
        try:
            qdrant_client.create_payload_index(
                COLLECTION_NAME, field, field_schema=PayloadSchemaType.KEYWORD)
        except Exception:
            pass  # already exist
    log.info("Payload indexes ensured (source, doc_type)")


def delete_source(source_name: str):
    """Xoá toàn bộ points của một source trước khi re-ingest."""
    try:
        qdrant_client.delete(
            collection_name=COLLECTION_NAME,
            points_selector=Filter(must=[
                FieldCondition(key="source", match=MatchValue(value=source_name))
            ]),
        )
        log.debug(f"  Deleted old points for: {source_name}")
    except Exception as e:
        log.warning(f"  Could not delete old points for {source_name}: {e}")


# ── Ingest one file ──────────────────────────────────────────────────────────

def ingest_file(path: Path, catalog: dict) -> int:
    fname = path.name
    meta  = catalog.get(fname, {})
    display_name = meta.get("display_name", fname)
    drive_id     = meta.get("drive_id", "")
    category     = meta.get("category", "biểu mẫu")
    download_url = f"{SERVER_BASE}/{fname}"

    source_key = f"bieu_mau/{fname}"
    log.info(f"  → {fname} ({display_name})")

    # Xoá bản cũ trước để tránh duplicate khi re-ingest
    delete_source(source_key)

    pages = extract_text(path)
    if not pages:
        # Không extract được text → stub chunk để chatbot biết file tồn tại
        pages = [{"page": 1, "text": f"Biểu mẫu: {display_name}. Danh mục: {category}. File: {fname}."}]
        log.warning(f"    No text extracted, using stub for {fname}")

    flat_chunks = []
    for page_data in pages:
        for chunk in chunk_text(page_data["text"]):
            flat_chunks.append((chunk, page_data["page"]))

    if not flat_chunks:
        return 0

    batch_size = 20
    total_indexed = 0
    for i in range(0, len(flat_chunks), batch_size):
        batch_chunks = [c for c, _ in flat_chunks[i:i+batch_size]]
        batch_pages  = [p for _, p in flat_chunks[i:i+batch_size]]
        vectors = embed_batch(batch_chunks)
        ps = [
            PointStruct(
                id=make_point_id(source_key, pg, i + j),
                vector=vec,
                payload={
                    "text":         chunk,
                    "source":       source_key,
                    "page":         pg,
                    "doc_type":     "bieu_mau",
                    "display_name": display_name,
                    "category":     category,
                    "download_url": download_url,
                    "drive_id":     drive_id,
                },
            )
            for j, (chunk, pg, vec) in enumerate(zip(batch_chunks, batch_pages, vectors))
        ]
        qdrant_client.upsert(collection_name=COLLECTION_NAME, points=ps)
        total_indexed += len(ps)
        time.sleep(0.1)

    log.info(f"    {total_indexed} chunks indexed")
    return total_indexed


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    files   = [f for f in sorted(BIEU_MAU_DIR.iterdir())
               if f.suffix.lower() in (".pdf", ".docx", ".doc")]

    log.info(f"Found {len(files)} biểu mẫu files")
    ensure_collection()

    total = 0
    for f in files:
        total += ingest_file(f, catalog)

    log.info(f"\n✓ Done. Total chunks indexed: {total}")


if __name__ == "__main__":
    main()
