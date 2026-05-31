"""Cap nhat email admin dean1 (chay sau khi doi dia chi nhan OTP)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from admin_auth.database import SessionLocal, init_db
from admin_auth.models.user_minimal import User

NEW_EMAIL = "mrsauhoaquaaaa@gmail.com"
USERNAME = "dean1"


def main():
    init_db()
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == USERNAME).first()
        if not user:
            print(f"User {USERNAME} not found. Run: python create_admin_account.py")
            return
        old = user.email
        user.email = NEW_EMAIL
        db.commit()
        print(f"OK: {USERNAME} email updated")
        print(f"  {old} -> {NEW_EMAIL}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
