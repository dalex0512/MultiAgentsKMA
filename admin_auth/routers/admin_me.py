from fastapi import APIRouter, Depends

from admin_auth.auth.dependencies import get_current_active_user
from admin_auth.auth.roles import check_dean_role
from admin_auth.models.user_minimal import User

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/me")
def get_admin_profile(current_user: User = Depends(get_current_active_user)):
    check_dean_role(current_user)
    return {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "role": current_user.role.value,
        "full_name": current_user.full_name,
    }
