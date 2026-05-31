from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from admin_auth.auth.security import decode_token
from admin_auth.core.config import settings
from admin_auth.crud.user import get_user_by_username
from admin_auth.database import get_db
from admin_auth.models.user_minimal import User
from admin_auth.schemas.user import TokenData
from admin_auth.services.token_store import is_jti_active

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login", auto_error=True)
oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl="auth/login", auto_error=False)


async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        if payload.get("typ") not in (None, "access"):
            raise credentials_exception
        username: str = payload.get("sub")
        jti: str = payload.get("jti")
        if username is None:
            raise credentials_exception
        if jti and not is_jti_active(db, jti):
            raise credentials_exception
        token_data = TokenData(username=username)
    except JWTError:
        raise credentials_exception
    user = get_user_by_username(db, username=token_data.username)
    if user is None:
        raise credentials_exception
    return user


async def get_current_active_user(current_user: User = Depends(get_current_user)):
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user
