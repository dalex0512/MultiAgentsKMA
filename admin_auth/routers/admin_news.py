from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile

from admin_auth.auth.admin_guard import require_dean
from admin_auth.core.config import settings
from admin_auth.models.user_minimal import User
from admin_auth.services.antivirus import scan_upload
from admin_auth.services.audit import write_audit
from admin_auth.services.document_storage import read_upload_bounded, sanitize_filename
from admin_auth.services.news_board import (
    NEWS_FOLDER,
    delete_news_item,
    ensure_news_folder,
    list_news_items,
    upsert_news_item,
)
from admin_auth.database import get_db
from admin_auth.services.rate_limit import auth_rate_limiter, client_ip
from sqlalchemy.orm import Session

router = APIRouter(prefix="/admin/news", tags=["admin-news"])


def _news_upload_limit(request: Request, username: str) -> None:
    ip = client_ip(request)
    auth_rate_limiter.enforce(
        f"admin_news_upload:{ip}:{username}",
        max_calls=settings.ADMIN_UPLOAD_MAX_PER_HOUR,
        window_sec=3600,
    )


@router.get("")
def admin_list_news(_: User = Depends(require_dean)):
    return {"items": list_news_items()}


@router.post("/upload")
async def upload_news_pdf(
    request: Request,
    file: UploadFile = File(...),
    title: str = Form(""),
    summary: str = Form(""),
    overwrite: str = Form("false"),
    db: Session = Depends(get_db),
    user: User = Depends(require_dean),
):
    _news_upload_limit(request, user.username)
    filename = sanitize_filename(file.filename or "")
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Tin mới chỉ hỗ trợ file PDF.")
    if not (summary or "").strip():
        raise HTTPException(status_code=400, detail="Vui lòng nhập mô tả ngắn cho tin mới.")

    max_bytes = settings.ADMIN_MAX_UPLOAD_MB * 1024 * 1024
    content = await read_upload_bounded(file, max_bytes)
    scan_upload(content, filename)
    ensure_news_folder()
    path = NEWS_FOLDER / filename
    overwrite_flag = str(overwrite).lower() in ("true", "1", "yes", "on")
    existed_before = path.exists()
    if existed_before and not overwrite_flag:
        raise HTTPException(
            status_code=409,
            detail=f"File '{filename}' đã tồn tại. Chọn ghi đè hoặc đổi tên file.",
        )
    path.write_bytes(content)
    item = upsert_news_item(
        filename=filename,
        title=title,
        summary=summary,
        uploaded_by=user.username,
    )
    write_audit(
        db,
        action="news_upload",
        success=True,
        username=user.username,
        ip=client_ip(request),
        detail=filename,
    )
    return {"ok": True, "item": item, "overwritten": existed_before and overwrite_flag}


@router.delete("/{filename}")
def admin_delete_news(
    request: Request,
    filename: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_dean),
):
    safe = sanitize_filename(filename)
    removed = delete_news_item(safe)
    write_audit(
        db,
        action="news_delete",
        success=True,
        username=user.username,
        ip=client_ip(request),
        detail=safe,
    )
    return {"ok": True, "deleted": safe, "removed_file": removed}
