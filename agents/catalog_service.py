"""
Tra cứu catalog biểu mẫu (docs/bieu_mau/catalog.json) — tool cho Agent Biểu mẫu.
"""

import json
import logging
from pathlib import Path

from config import DOCS_ROOT

log = logging.getLogger(__name__)

CATALOG_PATH = Path(DOCS_ROOT) / "bieu_mau" / "catalog.json"


def load_catalog() -> dict:
    if not CATALOG_PATH.exists():
        return {}
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


def search_forms(query: str, limit: int = 8) -> list[dict]:
    """Tìm biểu mẫu theo từ khóa trong display_name / category / filename."""
    q = query.lower()
    tokens = [t for t in q.split() if len(t) > 1]
    catalog = load_catalog()
    scored: list[tuple[int, dict]] = []

    for fname, meta in catalog.items():
        display = (meta.get("display_name") or "").lower()
        category = (meta.get("category") or "").lower()
        blob = f"{fname} {display} {category}".lower()
        score = sum(1 for t in tokens if t in blob)
        if score > 0 or any(k in blob for k in tokens):
            scored.append((score, {
                "filename":     fname,
                "display_name": meta.get("display_name", fname),
                "category":     meta.get("category", ""),
                "download_url": f"/docs/bieu_mau/{fname}",
                "drive_id":     meta.get("drive_id", ""),
            }))

    scored.sort(key=lambda x: (-x[0], x[1]["display_name"]))
    return [item for _, item in scored[:limit]]


def format_catalog_context(forms: list[dict]) -> str:
    if not forms:
        return ""
    lines = ["=== Danh mục biểu mẫu liên quan (catalog KMA) ==="]
    for i, f in enumerate(forms, 1):
        fname = f.get("filename", "")
        lines.append(
            f"[BM{i}] {f['display_name']} | File: {fname} | Loại: {f['category']} | "
            f"Tải: {f['download_url']}"
        )
    return "\n".join(lines)
