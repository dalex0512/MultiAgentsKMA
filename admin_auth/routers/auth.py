from datetime import timedelta
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy.orm import Session

from admin_auth.auth.dependencies import get_current_active_user
from admin_auth.auth.security import get_password_hash, verify_password
from admin_auth.core.config import settings
from admin_auth.crud.user import create_user, get_user_by_email, get_user_by_username
from admin_auth.database import get_db
from admin_auth.models.enums import UserRole
from admin_auth.models.user_minimal import User
from admin_auth.schemas.user import Token, User, UserCreate
from admin_auth.services import pending_login
from admin_auth.services.otp_service import (
    generate_otp,
    send_otp_email,
    store_otp,
    verify_otp,
)
from admin_auth.services.audit import write_audit
from admin_auth.services.rate_limit import auth_rate_limiter, client_ip

router = APIRouter(prefix="/auth", tags=["auth"])


class OTPVerifyRequest(BaseModel):
    username: str
    otp: str


class OTPResponse(BaseModel):
    requires_otp: bool
    message: str
    email_hint: Optional[str] = None


def _mask_email(email: str) -> str:
    email_parts = email.split("@")
    if len(email_parts) == 2:
        return email_parts[0][:3] + "***@" + email_parts[1]
    return "***"


def _enforce_login_rate_limit(request: Request) -> None:
    ip = client_ip(request)
    auth_rate_limiter.enforce(
        f"login:{ip}",
        max_calls=settings.AUTH_LOGIN_MAX_ATTEMPTS,
        window_sec=settings.AUTH_LOGIN_WINDOW_SEC,
    )


def _enforce_otp_send_limit(username: str) -> None:
    auth_rate_limiter.enforce(
        f"otp_send:{username}",
        max_calls=settings.AUTH_OTP_SEND_MAX,
        window_sec=settings.AUTH_OTP_SEND_WINDOW_SEC,
    )


def _enforce_otp_verify_limit(request: Request, username: str) -> None:
    ip = client_ip(request)
    auth_rate_limiter.enforce(
        f"otp_verify:{ip}:{username}",
        max_calls=settings.AUTH_OTP_VERIFY_MAX,
        window_sec=settings.AUTH_OTP_VERIFY_WINDOW_SEC,
    )


def _send_dean_otp_email(user: User) -> str:
    otp = generate_otp()
    store_otp(user.id, otp)
    full_name = user.full_name or user.username
    if not send_otp_email(user.email, otp, full_name):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send OTP email. Please try again.",
        )
    return _mask_email(user.email)


def _start_dean_otp_flow(user: User) -> dict:
    _enforce_otp_send_limit(user.username)
    email_hint = _send_dean_otp_email(user)
    pending_login.set_pending(
        username=user.username,
        user_id=user.id,
        role=user.role.value,
    )
    return {
        "requires_otp": True,
        "message": (
            f"OTP đã được gửi đến email của bạn. "
            f"Mã có hiệu lực trong {settings.OTP_EXPIRE_MINUTES} phút."
        ),
        "email_hint": email_hint,
    }


@router.post("/register", response_model=User)
def register_user(user: UserCreate, db: Session = Depends(get_db)):
    if not settings.ALLOW_PUBLIC_REGISTER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Đăng ký công khai đã tắt. Liên hệ quản trị hệ thống.",
        )

    if user.role == UserRole.DEAN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Không thể tự đăng ký tài khoản quản trị.",
        )

    db_user = get_user_by_username(db, username=user.username)
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")

    db_email = get_user_by_email(db, email=user.email)
    if db_email:
        raise HTTPException(status_code=400, detail="Email already registered")

    return create_user(db=db, user=user)


@router.post("/login")
async def login_for_access_token(
    request: Request,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Session = Depends(get_db),
):
    _enforce_login_rate_limit(request)

    ip = client_ip(request)
    user = get_user_by_username(db, username=form_data.username)
    if not user or not verify_password(form_data.password, user.hashed_password):
        write_audit(
            db,
            action="login",
            success=False,
            username=form_data.username,
            ip=ip,
            detail="bad_credentials",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        write_audit(db, action="login", success=False, username=user.username, ip=ip, detail="inactive")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if user.role != UserRole.DEAN:
        write_audit(db, action="login", success=False, username=user.username, ip=ip, detail="not_dean")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    write_audit(db, action="login", success=True, username=user.username, ip=ip, detail="otp_sent")
    return _start_dean_otp_flow(user)


@router.post("/verify-otp", response_model=Token)
async def verify_otp_login(
    request: Request,
    body: OTPVerifyRequest,
    db: Session = Depends(get_db),
):
    username = body.username.strip()
    otp = body.otp.strip()

    if not username or not otp.isdigit() or len(otp) != settings.OTP_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mã OTP không hợp lệ.",
        )

    _enforce_otp_verify_limit(request, username)
    pending = pending_login.require_pending(username)
    user_id = pending["user_id"]

    success, remaining = verify_otp(user_id, otp)

    ip = client_ip(request)
    if not success:
        if remaining <= 0:
            pending_login.clear_pending(username)
            write_audit(db, action="otp_verify", success=False, username=username, ip=ip, detail="locked")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Đã hết số lần thử. Vui lòng đăng nhập lại.",
            )
        write_audit(db, action="otp_verify", success=False, username=username, ip=ip, detail=f"retry_{remaining}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Mã OTP không đúng. Còn {remaining} lần thử.",
        )

    pending_login.clear_pending(username)
    write_audit(db, action="otp_verify", success=True, username=username, ip=ip)

    user = get_user_by_username(db, username=username)
    if not user or user.role != UserRole.DEAN:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        )

    from admin_auth.services.token_store import issue_token_pair

    tokens = issue_token_pair(db, user.id, user.username)
    return {**tokens, "role": user.role.value}


@router.post("/resend-otp")
async def resend_otp(
    request: Request,
    username: str = Form(...),
    db: Session = Depends(get_db),
):
    """Resend OTP — chỉ khi đã đăng nhập mật khẩu đúng (phiên pending còn hiệu lực)."""
    username = username.strip()
    _enforce_otp_verify_limit(request, username)

    pending_login.require_pending(username)
    pending_login.enforce_resend_cooldown(username)
    _enforce_otp_send_limit(username)

    user = get_user_by_username(db, username=username)
    if not user or user.role != UserRole.DEAN or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Phiên xác thực đã hết hạn. Vui lòng đăng nhập lại.",
        )

    _send_dean_otp_email(user)
    pending_login.mark_otp_sent(username)
    write_audit(
        db,
        action="otp_resend",
        success=True,
        username=username,
        ip=client_ip(request),
    )

    return {
        "message": (
            f"OTP mới đã được gửi. Mã có hiệu lực trong {settings.OTP_EXPIRE_MINUTES} phút."
        )
    }


@router.post("/change-password")
def change_password(
    request: Request,
    old_password: str = Form(...),
    new_password: str = Form(...),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    ip = client_ip(request)
    auth_rate_limiter.enforce(
        f"change_pw:{ip}:{current_user.username}",
        max_calls=5,
        window_sec=900,
    )

    if len(new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mật khẩu mới phải có ít nhất 8 ký tự.",
        )

    if not verify_password(old_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Old password is incorrect",
        )

    current_user.hashed_password = get_password_hash(new_password)
    db.commit()

    return {"message": "Password changed successfully"}

