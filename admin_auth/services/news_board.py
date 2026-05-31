from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException

from admin_auth.services.document_storage import sanitize_filename
from config import DOCS_ROOT

NEWS_FOLDER = Path(DOCS_ROOT) / "tin_moi"
NEWS_META_FILE = NEWS_FOLDER / "news.json"


def ensure_news_folder() -> Path:
    NEWS_FOLDER.mkdir(parents=True, exist_ok=True)
    return NEWS_FOLDER


def _read_meta_raw() -> list[dict]:
    ensure_news_folder()
    if not NEWS_META_FILE.exists():
        return []
    try:
        data = json.loads(NEWS_META_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    return []


def _write_meta(items: list[dict]) -> None:
    ensure_news_folder()
    NEWS_META_FILE.write_text(
        json.dumps(items, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _to_public_item(item: dict) -> dict:
    filename = str(item.get("filename") or "")
    title = str(item.get("title") or filename)
    summary = str(item.get("summary") or "")
    uploaded_at = str(item.get("uploaded_at") or "")
    uploaded_by = str(item.get("uploaded_by") or "")
    return {
        "filename": filename,
        "title": title,
        "summary": summary,
        "uploaded_at": uploaded_at,
        "uploaded_by": uploaded_by,
        "download_url": f"/docs/tin_moi/{filename}" if filename else "",
    }


def list_news_items() -> list[dict]:
    rows = []
    for item in _read_meta_raw():
        filename = str(item.get("filename") or "").strip()
        if not filename:
            continue
        path = NEWS_FOLDER / filename
        if not path.is_file():
            continue
        rows.append(_to_public_item(item))
    rows.sort(key=lambda x: x.get("uploaded_at", ""), reverse=True)
    return rows


def upsert_news_item(
    *,
    filename: str,
    title: str,
    summary: str,
    uploaded_by: str,
) -> dict:
    rows = _read_meta_raw()
    now = datetime.now(timezone.utc).isoformat()
    norm_filename = sanitize_filename(filename)
    if not norm_filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Tin mới chỉ hỗ trợ file PDF.")

    replaced = False
    for row in rows:
        if str(row.get("filename") or "") == norm_filename:
            row["title"] = title.strip() or norm_filename
            row["summary"] = summary.strip()
            row["uploaded_at"] = now
            row["uploaded_by"] = uploaded_by
            replaced = True
            break
    if not replaced:
        rows.append(
            {
                "filename": norm_filename,
                "title": title.strip() or norm_filename,
                "summary": summary.strip(),
                "uploaded_at": now,
                "uploaded_by": uploaded_by,
            }
        )
    _write_meta(rows)
    for item in rows:
        if str(item.get("filename") or "") == norm_filename:
            return _to_public_item(item)
    raise HTTPException(status_code=500, detail="Không thể lưu metadata tin mới.")


def delete_news_item(filename: str) -> bool:
    norm_filename = sanitize_filename(filename)
    path = NEWS_FOLDER / norm_filename
    existed = path.is_file()
    if existed:
        path.unlink()

    rows = _read_meta_raw()
    filtered = [r for r in rows if str(r.get("filename") or "") != norm_filename]
    if len(filtered) != len(rows):
        _write_meta(filtered)
    elif not NEWS_META_FILE.exists():
        _write_meta(filtered)
    return existed
