from sqlalchemy import Column, DateTime, Integer, String
from sqlalchemy.sql import func

from admin_auth.database import Base


class DocumentRecord(Base):
    __tablename__ = "document_records"

    id = Column(Integer, primary_key=True, index=True)
    agent_id = Column(String(32), nullable=False, index=True)
    filename = Column(String(255), nullable=False)
    source_key = Column(String(512), nullable=False, unique=True, index=True)
    file_size_bytes = Column(Integer, default=0)
    chunk_count = Column(Integer, default=0)
    status = Column(String(32), default="indexed")  # indexed | failed | deleted
    uploaded_by = Column(String(64), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
