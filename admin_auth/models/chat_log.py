from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String, Text
from sqlalchemy.sql import func

from admin_auth.database import Base


class ChatLog(Base):
    __tablename__ = "chat_logs"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(64), index=True, nullable=True)
    question_preview = Column(String(500), nullable=False)
    primary_agent = Column(String(32), index=True, nullable=True)
    agents_used = Column(String(200), nullable=True)
    pipeline = Column(String(32), nullable=True)
    in_scope = Column(Boolean, default=True)
    qc = Column(Float, default=0.0)
    t_total = Column(Float, default=0.0)
    source_count = Column(Integer, default=0)
    client_ip = Column(String(64), nullable=True)
    stream = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
