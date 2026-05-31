from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from admin_auth.auth.dependencies import oauth2_scheme_optional
from admin_auth.auth.security import decode_token
from admin_auth.core.config import settings
from admin_auth.database import get_db
from admin_auth.models.user_minimal import User
from admin_auth.observability.metrics import AUTH_EVENTS
from admin_auth.services.audit import write_audit
from admin_auth.services.rate_limit import auth_rate_limiter, client_ip
from admin_auth.services.token_store import (
    is_jti_active,
    issue_token_pair,
    revoke_family,
    revoke_jti,
)

router = APIRouter(prefix="/auth", tags=["auth-tokens"])


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str | None = None


@router.post("/refresh")
def refresh_tokens(
    request: Request,
    body: RefreshRequest,
    db: Session = Depends(get_db),
):
    ip = client_ip(request)
    auth_rate_limiter.enforce(f"refresh:{ip}", max_calls=30, window_sec=900)

    payload = decode_token(body.refresh_token)
    if not payload or payload.get("typ") != "refresh":
        AUTH_EVENTS.labels(event="refresh", outcome="fail").inc()
        raise HTTPException(status_code=401, detail="Refresh token không hợp lệ.")

    jti = payload.get("jti")
    username = payload.get("sub")
    user_id = payload.get("user_id")
    family_id = payload.get("fid")

    if not jti or not is_jti_active(db, jti):
        AUTH_EVENTS.labels(event="refresh", outcome="fail").inc()
        raise HTTPException(status_code=401, detail="Refresh token đã hết hạn hoặc bị thu hồi.")

    revoke_jti(db, jti)

    from admin_auth.crud.user import get_user_by_username

    user = get_user_by_username(db, username=username)
    if not user or not user.is_active or user.id != user_id:
        raise HTTPException(status_code=401, detail="User không hợp lệ.")

    tokens = issue_token_pair(db, user.id, user.username, family_id=family_id)
    AUTH_EVENTS.labels(event="refresh", outcome="ok").inc()
    write_audit(db, action="token_refresh", success=True, username=username, ip=ip)

    return {**tokens, "role": user.role.value}


@router.post("/logout")
def logout(
    request: Request,
    body: LogoutRequest,
    db: Session = Depends(get_db),
    token: str | None = Depends(oauth2_scheme_optional),
):
    ip = client_ip(request)
    username = None

    if body.refresh_token:
        payload = decode_token(body.refresh_token)
        if payload and payload.get("fid"):
            revoke_family(db, payload["fid"])
            username = username or payload.get("sub")

    if token:
        payload = decode_token(token)
        if payload and payload.get("jti"):
            revoke_jti(db, payload["jti"])

    AUTH_EVENTS.labels(event="logout", outcome="ok").inc()
    if username:
        write_audit(db, action="logout", success=True, username=username, ip=ip)

    return {"message": "Đã đăng xuất."}
