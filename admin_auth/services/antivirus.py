import logging
import shutil
import subprocess
import tempfile
from pathlib import Path

from fastapi import HTTPException, status

from admin_auth.core.config import settings

log = logging.getLogger(__name__)


def scan_upload(content: bytes, filename: str) -> None:
    """Quét malware trước khi lưu. Bỏ qua nếu CLAMAV_ENABLED=false."""
    if not settings.CLAMAV_ENABLED:
        return

    if not content:
        return

    infected = _scan_with_clamscan(content, filename)
    if infected:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File không an toàn — phát hiện nội dung nghi ngờ (antivirus).",
        )


def _scan_with_clamscan(content: bytes, filename: str) -> bool:
    clam = settings.CLAMAV_BIN
    if not shutil.which(clam):
        log.warning("ClamAV bật nhưng không tìm thấy %s — bỏ qua quét", clam)
        return False

    suffix = Path(filename).suffix or ".bin"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        proc = subprocess.run(
            [clam, "--no-summary", tmp_path],
            capture_output=True,
            text=True,
            timeout=120,
            encoding="utf-8",
            errors="replace",
        )
        if proc.returncode == 1:
            log.warning("ClamAV infected: %s %s", filename, proc.stdout)
            return True
        if proc.returncode not in (0, 1):
            log.warning("ClamAV exit %s: %s", proc.returncode, proc.stderr)
        return False
    except subprocess.TimeoutExpired:
        log.error("ClamAV timeout for %s", filename)
        raise HTTPException(status_code=503, detail="Antivirus scan timeout.")
    finally:
        Path(tmp_path).unlink(missing_ok=True)
