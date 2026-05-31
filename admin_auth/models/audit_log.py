from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text
from sqlalchemy.sql import func

from admin_auth.database import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(64), index=True, nullable=True)
    ip = Column(String(64), nullable=True)
    action = Column(String(64), nullable=False, index=True)
    detail = Column(Text, nullable=True)
    success = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
