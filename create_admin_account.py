"""Tạo tài khoản dean1 để test OTP. Chạy từ thư mục demo."""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from admin_auth.database import SessionLocal, init_db
from admin_auth.models.user_minimal import User
from admin_auth.auth.security import get_password_hash
from admin_auth.models.enums import UserRole

ADMIN_EMAIL = "mrsauhoaquaaaa@gmail.com"


def create_admin():
    init_db()
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == "dean1").first()
        if user:
            user.email = ADMIN_EMAIL
            user.full_name = user.full_name or "Quản trị KMA"
            db.commit()
            print(f"dean1 updated — OTP email: {ADMIN_EMAIL}")
            return
        user = User(
            username="dean1",
            email=ADMIN_EMAIL,
            hashed_password=get_password_hash("password123"),
            full_name="Quản trị KMA",
            role=UserRole.DEAN,
            is_active=True,
        )
        db.add(user)
        db.commit()
        print("OK: dean1 / password123 (role=dean)")
        print(f"OTP sent to: {ADMIN_EMAIL}")
    finally:
        db.close()


if __name__ == "__main__":
    create_admin()
