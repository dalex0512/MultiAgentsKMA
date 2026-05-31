from pydantic import BaseModel
from typing import Optional

from admin_auth.models.enums import UserRole


class Token(BaseModel):
    access_token: str
    refresh_token: str | None = None
    token_type: str
    role: UserRole


class TokenData(BaseModel):
    username: Optional[str] = None
    role: Optional[UserRole] = None


class UserBase(BaseModel):
    username: str
    email: str
    full_name: Optional[str] = None
    phone_number: Optional[str] = None
    role: UserRole


class UserCreate(UserBase):
    password: str
    student_code: Optional[str] = None
    lecturer_code: Optional[str] = None
    department_id: Optional[int] = None


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[str] = None
    phone_number: Optional[str] = None
    student_code: Optional[str] = None
    lecturer_code: Optional[str] = None
    department_id: Optional[int] = None


class User(UserBase):
    id: int
    is_active: bool = True
    student_code: Optional[str] = None
    lecturer_code: Optional[str] = None
    department_name: Optional[str] = None

    class Config:
        from_attributes = True


class PasswordChange(BaseModel):
    old_password: str
    new_password: str
