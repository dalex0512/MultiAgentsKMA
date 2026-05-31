from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from admin_auth.auth.admin_guard import require_dean
from admin_auth.core.config import settings
from admin_auth.database import SessionLocal, get_db
from admin_auth.models.user_minimal import User
from admin_auth.services.admin_settings import load_settings, save_settings
from admin_auth.services.qdrant_stats import collection_health
from config import AGENTS, ACCURACY_MODE, FAST_MODE, THRESHOLD1, THRESHOLD2, TOP_K
from pipelines.retrieval import QdrantRetriever

router = APIRouter(prefix="/admin/system", tags=["admin-system"])


class SettingsUpdate(BaseModel):
    disabled_agents: list[str] | None = None
    maintenance_message: str | None = None


class RetrieveTestRequest(BaseModel):
    query: str
    agent_id: str
    top_k: int = 5


@router.get("/health")
def system_health(_: User = Depends(require_dean)):
    db_ok = False
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        db_ok = True
    except Exception as e:
        db_err = str(e)
    else:
        db_err = None

    qdrant = collection_health()
    cfg_warnings = []
    if settings.uses_default_secret():
        cfg_warnings.append("SECRET_KEY đang dùng giá trị mặc định — đổi trong .env trước production.")
    if not (settings.SMTP_EMAIL and settings.SMTP_PASSWORD):
        cfg_warnings.append("Thiếu SMTP_EMAIL/SMTP_PASSWORD — không gửi được OTP admin.")

    return {
        "postgres": {"ok": db_ok, "error": db_err},
        "qdrant": qdrant,
        "config_warnings": cfg_warnings,
        "routing": {
            "fast_mode": FAST_MODE,
            "accuracy_mode": ACCURACY_MODE,
            "top_k": TOP_K,
            "threshold1": THRESHOLD1,
            "threshold2": THRESHOLD2,
        },
        "agents": [
            {"id": aid, "name": cfg["name"], "folder": cfg["folder"]}
            for aid, cfg in AGENTS.items()
        ],
    }


@router.get("/settings")
def get_settings(_: User = Depends(require_dean)):
    return load_settings()


@router.patch("/settings")
def patch_settings(body: SettingsUpdate, _: User = Depends(require_dean)):
    current = load_settings()
    if body.disabled_agents is not None:
        invalid = [a for a in body.disabled_agents if a not in AGENTS]
        if invalid:
            raise HTTPException(status_code=400, detail=f"Agent không hợp lệ: {invalid}")
        current["disabled_agents"] = body.disabled_agents
    if body.maintenance_message is not None:
        current["maintenance_message"] = body.maintenance_message.strip()[:500]
    return save_settings(current)


@router.post("/retrieve-test")
def retrieve_test(body: RetrieveTestRequest, _: User = Depends(require_dean)):
    if body.agent_id not in AGENTS:
        raise HTTPException(status_code=400, detail="Agent không hợp lệ.")
    q = (body.query or "").strip()
    if len(q) < 3:
        raise HTTPException(status_code=400, detail="Câu truy vấn quá ngắn.")

    top_k = max(1, min(body.top_k, 12))
    retriever = QdrantRetriever()
    docs, elapsed = retriever.retrieve(q, agent_id=body.agent_id, top_k=top_k)
    return {
        "query": q,
        "agent_id": body.agent_id,
        "elapsed_sec": elapsed,
        "hits": [
            {
                "score": round(d.get("score", 0), 4),
                "rank_score": round(d.get("_rank_score", d.get("score", 0)), 4),
                "source": d.get("source", ""),
                "page": d.get("page", 0),
                "display_name": d.get("display_name", ""),
                "text_preview": (d.get("text", "") or "")[:400],
                "download_url": d.get("download_url", ""),
            }
            for d in docs
        ],
    }
