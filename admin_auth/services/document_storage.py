import re
from pathlib import Path

from fastapi import HTTPException, UploadFile, status

from admin_auth.core.config import settings
from config import AGENTS, DOCS_ROOT

_SAFE_NAME = re.compile(r"^[\w.\- ()\u00C0-\u1EF9]+$", re.UNICODE)
_ALLOWED = {".pdf", ".docx", ".doc"}


def validate_agent_id(agent_id: str) -> dict:
    if agent_id not in AGENTS:
        raise HTTPException(status_code=400, detail="Agent không hợp lệ.")
    return AGENTS[agent_id]


def sanitize_filename(name: str) -> str:
    base = Path(name).name.strip()
    if not base or base in (".", ".."):
        raise HTTPException(status_code=400, detail="Tên file không hợp lệ.")
    if ".." in base or "/" in base or "\\" in base:
        raise HTTPException(status_code=400, detail="Tên file không hợp lệ.")
    if not _SAFE_NAME.match(base):
        raise HTTPException(
            status_code=400,
            detail="Tên file chỉ được chứa chữ, số, dấu cách, gạch ngang và .pdf/.docx/.doc",
        )
    ext = Path(base).suffix.lower()
    if ext not in _ALLOWED:
        raise HTTPException(
            status_code=400,
            detail="Chỉ chấp nhận file .pdf, .docx, .doc",
        )
    return base


async def read_upload_bounded(file: UploadFile, max_bytes: int) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while True:
        part = await file.read(1024 * 256)
        if not part:
            break
        total += len(part)
        if total > max_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File vượt quá {max_bytes // (1024 * 1024)} MB.",
            )
        chunks.append(part)
    return b"".join(chunks)


def agent_folder_path(agent_id: str) -> Path:
    cfg = validate_agent_id(agent_id)
    path = Path(DOCS_ROOT) / cfg["folder"]
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_document_file(agent_id: str, filename: str, content: bytes) -> Path:
    folder = agent_folder_path(agent_id)
    dest = folder / filename
    dest.write_bytes(content)
    return dest


def delete_document_file(agent_id: str, filename: str) -> bool:
    cfg = validate_agent_id(agent_id)
    path = Path(DOCS_ROOT) / cfg["folder"] / filename
    if path.is_file():
        path.unlink()
        return True
    return False


def list_agent_files(agent_id: str) -> list[Path]:
    cfg = validate_agent_id(agent_id)
    dirpath = Path(DOCS_ROOT) / cfg["folder"]
    if not dirpath.is_dir():
        return []
    exts = _ALLOWED
    return sorted(
        f for f in dirpath.iterdir()
        if f.is_file() and f.suffix.lower() in exts
    )


def source_key_for(agent_id: str, filename: str) -> str:
    cfg = validate_agent_id(agent_id)
    return f"{cfg['folder']}/{filename}"
