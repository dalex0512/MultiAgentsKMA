from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from sqlalchemy.orm import Session

from admin_auth.auth.admin_guard import require_dean
from admin_auth.auth.security import get_password_hash, verify_password
from admin_auth.database import get_db
from admin_auth.models.audit_log import AuditLog
from admin_auth.models.user_minimal import User
from admin_auth.services.audit import write_audit
from admin_auth.services.rate_limit import auth_rate_limiter, client_ip
from admin_auth.services.token_store import revoke_all_for_user

router = APIRouter(prefix="/admin/security", tags=["admin-security"])


@router.get("/audit-logs")
def list_audit_logs(
    limit: int = 50,
    db: Session = Depends(get_db),
    _: User = Depends(require_dean),
):
    limit = max(1, min(limit, 200))
    rows = (
        db.query(AuditLog)
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
        .all()
    )
    return {
        "logs": [
            {
                "id": r.id,
                "username": r.username,
                "ip": r.ip,
                "action": r.action,
                "detail": r.detail,
                "success": r.success,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]
    }


@router.post("/change-password")
def admin_change_password(
    request: Request,
    old_password: str = Form(...),
    new_password: str = Form(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_dean),
):
    ip = client_ip(request)
    auth_rate_limiter.enforce(f"change_pw:{ip}:{user.username}", max_calls=5, window_sec=900)

    if len(new_password) < 8:
        raise HTTPException(status_code=400, detail="Mật khẩu mới phải có ít nhất 8 ký tự.")

    if not verify_password(old_password, user.hashed_password):
        write_audit(
            db,
            action="password_change",
            success=False,
            username=user.username,
            ip=ip,
            detail="wrong_old_password",
        )
        raise HTTPException(status_code=400, detail="Mật khẩu cũ không đúng.")

    user.hashed_password = get_password_hash(new_password)
    db.commit()
    write_audit(
        db,
        action="password_change",
        success=True,
        username=user.username,
        ip=ip,
    )
    return {"message": "Đổi mật khẩu thành công."}


@router.post("/revoke-sessions")
def revoke_all_sessions(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_dean),
):
    """Thu hồi mọi refresh/access token của tài khoản đang đăng nhập."""
    n = revoke_all_for_user(db, user.id)
    write_audit(
        db,
        action="revoke_all_sessions",
        success=True,
        username=user.username,
        ip=client_ip(request),
        detail=f"revoked={n}",
    )
    return {"message": f"Đã thu hồi {n} phiên token.", "revoked": n}
