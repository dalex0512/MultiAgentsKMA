from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from admin_auth.core.config import settings
from admin_auth.crud.user import get_user_by_email, get_user_by_username
from admin_auth.database import get_db
from admin_auth.models.enums import UserRole
from admin_auth.observability.metrics import AUTH_EVENTS
from admin_auth.routers.auth import _start_dean_otp_flow
from admin_auth.services.audit import write_audit
from admin_auth.services.rate_limit import client_ip
from admin_auth.services import sso_google, sso_ldap

router = APIRouter(prefix="/auth", tags=["auth-sso"])


@router.get("/sso/config")
def sso_config():
    return {
        "google": sso_google.is_configured(),
        "ldap": sso_ldap.is_configured(),
        "google_redirect": settings.GOOGLE_REDIRECT_URI if sso_google.is_configured() else None,
    }


@router.get("/google/login")
def google_login():
    if not sso_google.is_configured():
        raise HTTPException(status_code=503, detail="Google SSO chưa cấu hình.")
    return RedirectResponse(sso_google.build_login_url())


@router.get("/google/callback")
async def google_callback(
    request: Request,
    code: str = "",
    state: str = "",
    error: str = "",
    db: Session = Depends(get_db),
):
    if error:
        return RedirectResponse(f"/admin/login?error={error}")
    if not code or not sso_google.consume_state(state):
        return RedirectResponse("/admin/login?error=invalid_state")

    try:
        profile = await sso_google.exchange_code(code)
    except Exception:
        AUTH_EVENTS.labels(event="google_sso", outcome="fail").inc()
        return RedirectResponse("/admin/login?error=google_token")

    email = (profile.get("email") or "").strip().lower()
    if not email or not sso_google.email_allowed(email):
        return RedirectResponse("/admin/login?error=email_not_allowed")

    user = get_user_by_email(db, email=email)
    if not user or user.role != UserRole.DEAN or not user.is_active:
        write_audit(db, action="google_sso", success=False, detail=email, ip=client_ip(request))
        return RedirectResponse("/admin/login?error=no_account")

    write_audit(db, action="google_sso", success=True, username=user.username, ip=client_ip(request), detail=email)
    AUTH_EVENTS.labels(event="google_sso", outcome="ok").inc()
    _start_dean_otp_flow(user)

    return RedirectResponse(
        f"/admin/verify-otp?username={user.username}&sso=1"
    )


@router.post("/ldap/login")
async def ldap_login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    if not sso_ldap.is_configured():
        raise HTTPException(status_code=503, detail="LDAP chưa cấu hình.")

    profile = sso_ldap.authenticate(username.strip(), password)
    if not profile:
        AUTH_EVENTS.labels(event="ldap_sso", outcome="fail").inc()
        write_audit(db, action="ldap_sso", success=False, username=username, ip=client_ip(request))
        raise HTTPException(status_code=401, detail="LDAP: sai thông tin đăng nhập.")

    user = get_user_by_username(db, username=username.strip())
    if not user and profile.get("email"):
        user = get_user_by_email(db, email=profile["email"])

    if not user or user.role != UserRole.DEAN or not user.is_active:
        raise HTTPException(status_code=401, detail="Tài khoản không được phép đăng nhập admin.")

    write_audit(db, action="ldap_sso", success=True, username=user.username, ip=client_ip(request))
    AUTH_EVENTS.labels(event="ldap_sso", outcome="ok").inc()
    return _start_dean_otp_flow(user)
