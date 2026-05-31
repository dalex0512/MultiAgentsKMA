import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from admin_auth.auth.admin_guard import require_dean
from admin_auth.core.config import settings
from admin_auth.database import get_db
from admin_auth.models.document_record import DocumentRecord
from admin_auth.models.user_minimal import User
from admin_auth.services import document_ingest, document_storage
from admin_auth.services.antivirus import scan_upload
from admin_auth.services.audit import write_audit
from admin_auth.observability.metrics import UPLOAD_EVENTS
from admin_auth.services.rate_limit import auth_rate_limiter, client_ip
from config import AGENTS

log = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/documents", tags=["admin-documents"])


class CatalogEntryUpdate(BaseModel):
    display_name: str | None = None
    category: str | None = None


def _upload_limit(request: Request, username: str) -> None:
    ip = client_ip(request)
    auth_rate_limiter.enforce(
        f"admin_upload:{ip}:{username}",
        max_calls=settings.ADMIN_UPLOAD_MAX_PER_HOUR,
        window_sec=3600,
    )


@router.get("/agents")
def list_agents(_: User = Depends(require_dean)):
    return {
        "agents": [
            {
                "id": aid,
                "name": cfg["name"],
                "folder": cfg["folder"],
            }
            for aid, cfg in AGENTS.items()
        ]
    }


@router.get("")
def list_documents(
    agent_id: str | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_dean),
):
    agents = [agent_id] if agent_id and agent_id in AGENTS else list(AGENTS.keys())
    items = []
    for aid in agents:
        cfg = AGENTS[aid]
        for path in document_storage.list_agent_files(aid):
            sk = document_storage.source_key_for(aid, path.name)
            rec = db.query(DocumentRecord).filter(DocumentRecord.source_key == sk).first()
            stat = path.stat()
            items.append({
                "agent_id": aid,
                "agent_name": cfg["name"],
                "filename": path.name,
                "source_key": sk,
                "download_url": f"/docs/{cfg['folder']}/{path.name}",
                "file_size_bytes": stat.st_size,
                "chunk_count": rec.chunk_count if rec else None,
                "status": rec.status if rec else "on_disk",
                "uploaded_by": rec.uploaded_by if rec else None,
                "updated_at": (rec.updated_at.isoformat() if rec and rec.updated_at else None),
            })
    items.sort(key=lambda x: (x["agent_id"], x["filename"].lower()))
    return {"documents": items, "total": len(items)}


@router.post("/upload")
async def upload_document(
    request: Request,
    agent_id: str = Form(...),
    file: UploadFile = File(...),
    overwrite: str = Form("false"),
    db: Session = Depends(get_db),
    user: User = Depends(require_dean),
):
    _upload_limit(request, user.username)
    overwrite_flag = str(overwrite).lower() in ("true", "1", "yes", "on")
    document_storage.validate_agent_id(agent_id)
    filename = document_storage.sanitize_filename(file.filename or "")
    max_bytes = settings.ADMIN_MAX_UPLOAD_MB * 1024 * 1024
    content = await document_storage.read_upload_bounded(file, max_bytes)
    try:
        scan_upload(content, filename)
    except HTTPException:
        UPLOAD_EVENTS.labels(outcome="rejected_av").inc()
        raise

    dest = document_storage.agent_folder_path(agent_id) / filename
    existed_before = dest.exists()
    if existed_before and not overwrite_flag:
        raise HTTPException(
            status_code=409,
            detail=f"File '{filename}' đã tồn tại. Chọn ghi đè hoặc đổi tên file.",
        )

    path = document_storage.save_document_file(agent_id, filename, content)
    sk = document_storage.source_key_for(agent_id, filename)

    try:
        chunks = document_ingest.ingest_file(agent_id, path)
        status = "indexed" if chunks > 0 else "empty"
    except Exception as e:
        log.exception("ingest failed %s", sk)
        write_audit(
            db,
            action="document_upload",
            success=False,
            username=user.username,
            ip=client_ip(request),
            detail=f"{sk}: {e}",
        )
        raise HTTPException(status_code=500, detail=f"Ingest thất bại: {e}") from e

    rec = db.query(DocumentRecord).filter(DocumentRecord.source_key == sk).first()
    if not rec:
        rec = DocumentRecord(
            agent_id=agent_id,
            filename=filename,
            source_key=sk,
            uploaded_by=user.username,
        )
        db.add(rec)
    rec.file_size_bytes = len(content)
    rec.chunk_count = chunks
    rec.status = status
    rec.uploaded_by = user.username
    db.commit()

    write_audit(
        db,
        action="document_upload",
        success=True,
        username=user.username,
        ip=client_ip(request),
        detail=f"{sk} → {chunks} chunks",
    )
    UPLOAD_EVENTS.labels(outcome="ok").inc()

    return {
        "ok": True,
        "agent_id": agent_id,
        "filename": filename,
        "source_key": sk,
        "chunk_count": chunks,
        "download_url": f"/docs/{AGENTS[agent_id]['folder']}/{filename}",
        "overwritten": existed_before and overwrite_flag,
    }


@router.delete("/{agent_id}/{filename}")
def delete_document(
    request: Request,
    agent_id: str,
    filename: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_dean),
):
    filename = document_storage.sanitize_filename(filename)
    sk = document_storage.source_key_for(agent_id, filename)
    document_ingest.delete_vectors(sk)
    document_storage.delete_document_file(agent_id, filename)

    rec = db.query(DocumentRecord).filter(DocumentRecord.source_key == sk).first()
    if rec:
        db.delete(rec)
        db.commit()

    write_audit(
        db,
        action="document_delete",
        success=True,
        username=user.username,
        ip=client_ip(request),
        detail=sk,
    )
    return {"ok": True, "deleted": sk}


@router.post("/reindex/{agent_id}")
def reindex_agent(
    request: Request,
    agent_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_dean),
):
    _upload_limit(request, user.username)
    if agent_id not in AGENTS:
        raise HTTPException(status_code=400, detail="Agent không hợp lệ.")
    try:
        total = document_ingest.reindex_agent(agent_id)
    except Exception as e:
        log.exception("reindex %s", agent_id)
        raise HTTPException(status_code=500, detail=str(e)) from e

    write_audit(
        db,
        action="document_reindex",
        success=True,
        username=user.username,
        ip=client_ip(request),
        detail=f"{agent_id}: {total} chunks",
    )
    return {"ok": True, "agent_id": agent_id, "chunks_indexed": total}


@router.get("/catalog")
def get_catalog(_: User = Depends(require_dean)):
    return document_ingest.load_catalog("bieu_mau") or {}


@router.put("/catalog/{filename}")
def update_catalog_entry(
    request: Request,
    filename: str,
    body: CatalogEntryUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_dean),
):
    from pathlib import Path

    from config import DOCS_ROOT

    filename = document_storage.sanitize_filename(filename)
    cat_path = Path(DOCS_ROOT) / "bieu_mau" / "catalog.json"
    catalog = document_ingest.load_catalog("bieu_mau") or {}
    entry = catalog.get(filename, {})
    if body.display_name is not None:
        entry["display_name"] = body.display_name.strip()
    if body.category is not None:
        entry["category"] = body.category.strip()
    catalog[filename] = entry
    cat_path.parent.mkdir(parents=True, exist_ok=True)
    import json

    cat_path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")
    write_audit(
        db,
        action="catalog_update",
        success=True,
        username=user.username,
        ip=client_ip(request),
        detail=filename,
    )
    return {"ok": True, "filename": filename, "entry": entry}
