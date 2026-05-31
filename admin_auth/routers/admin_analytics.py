from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from admin_auth.auth.admin_guard import require_dean
from admin_auth.database import get_db
from admin_auth.models.user_minimal import User
from admin_auth.services.chat_analytics import analytics_summary

router = APIRouter(prefix="/admin/analytics", tags=["admin-analytics"])


@router.get("/chat")
def chat_analytics(
    days: int = 7,
    db: Session = Depends(get_db),
    _: User = Depends(require_dean),
):
    return analytics_summary(db, days=days)
