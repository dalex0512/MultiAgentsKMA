import uuid
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from admin_auth.core.config import settings
from admin_auth.models.token_session import TokenSession


def new_family_id() -> str:
    return str(uuid.uuid4())


def new_jti() -> str:
    return str(uuid.uuid4())


def register_token(
    db: Session,
    *,
    jti: str,
    user_id: int,
    family_id: str,
    token_type: str,
    expires_at: datetime,
) -> None:
    db.add(
        TokenSession(
            jti=jti,
            user_id=user_id,
            family_id=family_id,
            token_type=token_type,
            expires_at=expires_at,
            revoked=False,
        )
    )
    db.commit()


def is_jti_active(db: Session, jti: str) -> bool:
    row = db.query(TokenSession).filter(TokenSession.jti == jti).first()
    if not row or row.revoked:
        return False
    if row.expires_at and row.expires_at.replace(tzinfo=None) < datetime.utcnow():
        return False
    return True


def revoke_jti(db: Session, jti: str) -> None:
    row = db.query(TokenSession).filter(TokenSession.jti == jti).first()
    if row:
        row.revoked = True
        db.commit()


def revoke_family(db: Session, family_id: str) -> int:
    rows = db.query(TokenSession).filter(
        TokenSession.family_id == family_id,
        TokenSession.revoked.is_(False),
    ).all()
    for r in rows:
        r.revoked = True
    db.commit()
    return len(rows)


def revoke_all_for_user(db: Session, user_id: int) -> int:
    rows = db.query(TokenSession).filter(
        TokenSession.user_id == user_id,
        TokenSession.revoked.is_(False),
    ).all()
    for r in rows:
        r.revoked = True
    db.commit()
    return len(rows)


def issue_token_pair(db: Session, user_id: int, username: str, family_id: str | None = None) -> dict:
    from admin_auth.auth.security import create_access_token, create_refresh_token

    family_id = family_id or new_family_id()
    access_jti = new_jti()
    refresh_jti = new_jti()

    access_exp = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    refresh_exp = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    access_token = create_access_token(
        data={"sub": username, "user_id": user_id, "jti": access_jti, "typ": "access", "fid": family_id},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    refresh_token = create_refresh_token(
        data={"sub": username, "user_id": user_id, "jti": refresh_jti, "typ": "refresh", "fid": family_id},
        expires_delta=timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )

    register_token(db, jti=access_jti, user_id=user_id, family_id=family_id, token_type="access", expires_at=access_exp)
    register_token(db, jti=refresh_jti, user_id=user_id, family_id=family_id, token_type="refresh", expires_at=refresh_exp)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "family_id": family_id,
    }
