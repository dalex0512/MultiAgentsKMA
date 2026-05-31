from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.sql import func

from admin_auth.database import Base


class ChatSessionArchive(Base):
    """Tầng lạnh — lịch sử hội thoại sau khi flush từ Redis/RAM."""

    __tablename__ = "chat_session_archives"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(64), unique=True, index=True, nullable=False)
    summary = Column(Text, nullable=True)
    turn_count = Column(Integer, default=0)
    last_agents = Column(String(500), nullable=True)
    messages_json = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())
