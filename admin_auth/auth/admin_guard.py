from fastapi import Depends

from admin_auth.auth.dependencies import get_current_active_user
from admin_auth.auth.roles import check_dean_role
from admin_auth.models.user_minimal import User


async def require_dean(current_user: User = Depends(get_current_active_user)) -> User:
    check_dean_role(current_user)
    return current_user
