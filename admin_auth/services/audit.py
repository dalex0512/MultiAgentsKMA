from sqlalchemy.orm import Session

from admin_auth.models.audit_log import AuditLog


def write_audit(
    db: Session,
    *,
    action: str,
    success: bool = True,
    username: str | None = None,
    ip: str | None = None,
    detail: str | None = None,
) -> None:
    db.add(
        AuditLog(
            username=username,
            ip=ip,
            action=action,
            detail=detail,
            success=success,
        )
    )
    db.commit()
