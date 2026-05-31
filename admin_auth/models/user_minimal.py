from sqlalchemy import Boolean, Column, DateTime, Enum, Integer, String
from sqlalchemy.sql import func

from admin_auth.database import Base
from admin_auth.models.enums import UserRole


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(Enum(UserRole, native_enum=False, length=20), nullable=False)
    full_name = Column(String)
    phone_number = Column(String)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
