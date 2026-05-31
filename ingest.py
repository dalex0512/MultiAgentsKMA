"""
Ingest PDF documents into Qdrant Cloud.
Usage: python ingest.py docs/
"""

import sys
import uuid
import time
import hashlib
import logging
from pathlib import Path

import numpy as np
from pypdf import PdfReader
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance, VectorParams, PointStruct,
    PayloadSchemaType,
)

from config import (
    QDRANT_URL, QDRANT_API_KEY,
    COLLECTION_NAME, EMBED_MODEL, CHUNK_SIZE, CHUNK_OVERLAP,
    embed_client,
)


def make_point_id(source: str, page: int, chunk_idx: int) -> str:
    """Deterministic UUID5 so re-ingesting the same file upserts, not duplicates."""
    key = f"{source}::page{page}::chunk{chunk_idx}"
    return str(uuid.uuid5(uuid.NAMESPACE_URL, key))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

openai_client = embed_client()
qdrant_client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)

EMBED_DIM = 1536


def extract_text(pdf_path: Path) -> list[dict]:
    reader = PdfReader(str(pdf_path))
    pages = []
    for i, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        text = text.strip()
        if text:
            pages.append({"page": i + 1, "text": text})
    return pages


def chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    words = text.split()
    chunks, start = [], 0
    while start < len(words):
        end = min(start + size, len(words))
        chunks.append(" ".join(words[start:end]))
        start += size - overlap
    return chunks


def embed_batch(texts: list[str]) -> list[list[float]]:
    response = openai_client.embeddings.create(input=texts, model=EMBED_MODEL)
    return [item.embedding for item in response.data]


def ensure_collection():
    existing = [c.name for c in qdrant_client.get_collections().collections]
    if COLLECTION_NAME not in existing:
        qdrant_client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=EMBED_DIM, distance=Distance.COSINE),
        )
        log.info(f"Created collection: {COLLECTION_NAME}")
    else:
        log.info(f"Collection exists: {COLLECTION_NAME}")

    # Payload indexes needed for filter-based delete (deduplication)
    try:
        qdrant_client.create_payload_index(
            COLLECTION_NAME, "source", field_schema=PayloadSchemaType.KEYWORD)
        qdrant_client.create_payload_index(
            COLLECTION_NAME, "doc_type", field_schema=PayloadSchemaType.KEYWORD)
        log.info("Payload indexes ensured (source, doc_type)")
    except Exception:
        pass  # already exist


def delete_source(source_name: str):
    """Xoá toàn bộ points của một source trước khi ingest lại (tránh duplicate)."""
    from qdrant_client.models import Filter, FieldCondition, MatchValue
    try:
        qdrant_client.delete(
            collection_name=COLLECTION_NAME,
            points_selector=Filter(must=[
                FieldCondition(key="source", match=MatchValue(value=source_name))
            ]),
        )
        log.info(f"  Deleted old points for: {source_name}")
    except Exception as e:
        log.warning(f"  Could not delete old points for {source_name}: {e}")


def ingest_pdf(pdf_path: Path):
    log.info(f"Processing: {pdf_path.name}")
    pages = extract_text(pdf_path)
    if not pages:
        log.warning(f"No text extracted from {pdf_path.name}")
        return 0

    # Xoá bản cũ trước (nếu có) để tránh duplicate khi re-ingest
    delete_source(pdf_path.name)

    chunk_counter = 0
    points = []
    for page_data in pages:
        chunks = chunk_text(page_data["text"])
        if not chunks:
            continue

        batch_size = 20
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i + batch_size]
            vectors = embed_batch(batch)
            for chunk_text_val, vector in zip(batch, vectors):
                points.append(PointStruct(
                    id=make_point_id(pdf_path.name, page_data["page"], chunk_counter),
                    vector=vector,
                    payload={
                        "text":     chunk_text_val,
                        "source":   pdf_path.name,
                        "page":     page_data["page"],
                        "doc_type": "pdf",
                    },
                ))
                chunk_counter += 1
            time.sleep(0.1)

    if points:
        qdrant_client.upsert(collection_name=COLLECTION_NAME, points=points)
        log.info(f"  {pdf_path.name}: {len(points)} chunks indexed")
    return len(points)


def main(docs_dir: str):
    docs_path = Path(docs_dir)
    pdfs = list(docs_path.glob("*.pdf"))
    if not pdfs:
        log.error(f"No PDF files found in {docs_dir}")
        sys.exit(1)

    ensure_collection()
    total = 0
    for pdf in pdfs:
        total += ingest_pdf(pdf)

    log.info(f"Done. Total chunks indexed: {total}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python ingest.py <docs_folder>")
        sys.exit(1)
    main(sys.argv[1])
