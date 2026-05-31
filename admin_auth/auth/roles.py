from fastapi import HTTPException

from admin_auth.models.user_minimal import User
from admin_auth.models.enums import UserRole


def check_dean_role(user: User):
    if user.role != UserRole.DEAN:
        raise HTTPException(status_code=403, detail="Not authorized. Dean access required.")
