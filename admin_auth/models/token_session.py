from sqlalchemy import Boolean, Column, DateTime, Integer, String
from sqlalchemy.sql import func

from admin_auth.database import Base


class TokenSession(Base):
    """JWT jti tracking for refresh rotation and revoke."""

    __tablename__ = "token_sessions"

    jti = Column(String(36), primary_key=True)
    user_id = Column(Integer, index=True, nullable=False)
    family_id = Column(String(36), index=True, nullable=False)
    token_type = Column(String(16), nullable=False)  # access | refresh
    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked = Column(Boolean, default=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
