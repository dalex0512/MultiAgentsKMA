"""Dean OTP login sessions — must exist before verify-otp / resend-otp."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Optional

from fastapi import HTTPException, status

from admin_auth.core.config import settings

# username -> session dict
_pending: dict[str, dict[str, Any]] = {}


def _expires_at(created_at: datetime) -> datetime:
    return created_at + timedelta(minutes=settings.PENDING_LOGIN_EXPIRE_MINUTES)


def _is_expired(entry: dict[str, Any]) -> bool:
    return datetime.utcnow() > _expires_at(entry["created_at"])


def prune_expired() -> None:
    expired = [u for u, e in _pending.items() if _is_expired(e)]
    for username in expired:
        del _pending[username]


def set_pending(*, username: str, user_id: int, role: str) -> None:
    prune_expired()
    now = datetime.utcnow()
    _pending[username] = {
        "user_id": user_id,
        "username": username,
        "role": role,
        "created_at": now,
        "last_otp_sent_at": now,
    }


def mark_otp_sent(username: str) -> None:
    entry = _pending.get(username)
    if entry:
        entry["last_otp_sent_at"] = datetime.utcnow()


def get_pending(username: str) -> Optional[dict[str, Any]]:
    prune_expired()
    entry = _pending.get(username)
    if not entry or _is_expired(entry):
        if username in _pending:
            del _pending[username]
        return None
    return entry


def require_pending(username: str) -> dict[str, Any]:
    entry = get_pending(username)
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Phiên xác thực đã hết hạn. Vui lòng đăng nhập lại.",
        )
    return entry


def clear_pending(username: str) -> None:
    _pending.pop(username, None)


def resend_cooldown_remaining(username: str) -> int:
    """Seconds until resend is allowed (0 = ok)."""
    entry = get_pending(username)
    if not entry:
        return 0
    last = entry.get("last_otp_sent_at") or entry["created_at"]
    elapsed = (datetime.utcnow() - last).total_seconds()
    remaining = settings.OTP_RESEND_COOLDOWN_SECONDS - int(elapsed)
    return max(0, remaining)


def enforce_resend_cooldown(username: str) -> None:
    remaining = resend_cooldown_remaining(username)
    if remaining > 0:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Vui lòng đợi {remaining} giây trước khi gửi lại OTP.",
        )
