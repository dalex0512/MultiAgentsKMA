from datetime import datetime, timedelta
from typing import Optional

import bcrypt
from jose import JWTError, jwt

from admin_auth.core.config import settings


def verify_password(plain_password, hashed_password):
    if isinstance(plain_password, str):
        plain_password = plain_password.encode("utf-8")
    if isinstance(hashed_password, str):
        hashed_password = hashed_password.encode("utf-8")
    return bcrypt.checkpw(plain_password, hashed_password)


def get_password_hash(password):
    if isinstance(password, str):
        password = password.encode("utf-8")
    return bcrypt.hashpw(password, bcrypt.gensalt()).decode("utf-8")


def _encode(data: dict, expires_delta: timedelta) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + expires_delta
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    delta = expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {**data, "typ": data.get("typ", "access")}
    return _encode(payload, delta)


def create_refresh_token(data: dict, expires_delta: Optional[timedelta] = None):
    delta = expires_delta or timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {**data, "typ": "refresh"}
    return _encode(payload, delta)


def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        return None


def decode_access_token(token: str):
    payload = decode_token(token)
    if not payload or payload.get("typ") not in (None, "access"):
        return None
    return payload
