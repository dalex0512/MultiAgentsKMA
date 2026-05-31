import json
import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response, StreamingResponse
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import AGENTS, AGENT_IDS
from pipelines.multi_agent_system import MultiAgentSystem
from agents.form_filler import get_filled_file_path
from admin_auth.core.config import settings as admin_settings
from admin_auth.database import init_db
from admin_auth.routers import auth as admin_auth_router
from admin_auth.routers import admin_me as admin_me_router
from admin_auth.routers import admin_benchmark as admin_benchmark_router
from admin_auth.routers import admin_documents as admin_documents_router
from admin_auth.routers import admin_news as admin_news_router
from admin_auth.routers import admin_security as admin_security_router
from admin_auth.routers import admin_system as admin_system_router
from admin_auth.routers import admin_analytics as admin_analytics_router
from admin_auth.routers import auth_tokens as auth_tokens_router
from admin_auth.routers import sso as sso_router
from admin_auth.services.admin_settings import load_settings
from admin_auth.services.news_board import list_news_items
from admin_auth.observability.metrics import (
    CHAT_LATENCY,
    CHAT_REQUESTS,
    metrics_response,
)
from admin_auth.services.rate_limit import client_ip
from api.chat_logging import record_chat, record_chat_from_event
from api.connection_tracker import track_chat_connection
from api.metrics_middleware import PrometheusMiddleware

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        init_db()
        log.info("admin_auth: database tables ready")
    except Exception as e:
        log.warning("admin_auth init_db skipped: %s", e)
    if admin_settings.uses_default_secret():
        log.warning(
            "admin_auth: SECRET_KEY is default — set a strong SECRET_KEY in .env before production"
        )
    if not (admin_settings.SMTP_EMAIL and admin_settings.SMTP_PASSWORD):
        log.warning(
            "admin_auth: SMTP chưa cấu hình — đăng nhập admin (OTP) sẽ thất bại cho đến khi có SMTP_EMAIL/SMTP_PASSWORD",
        )
    yield


app    = FastAPI(title="KMA Multi-Agent Chatbot", lifespan=lifespan)
system = MultiAgentSystem()

if admin_settings.METRICS_ENABLED:
    app.add_middleware(PrometheusMiddleware)

app.include_router(admin_auth_router.router)
app.include_router(auth_tokens_router.router)
app.include_router(sso_router.router)
app.include_router(admin_me_router.router)
app.include_router(admin_documents_router.router)
app.include_router(admin_news_router.router)
app.include_router(admin_system_router.router)
app.include_router(admin_security_router.router)
app.include_router(admin_benchmark_router.router)
app.include_router(admin_analytics_router.router)


@app.get("/metrics")
def prometheus_metrics():
    if not admin_settings.METRICS_ENABLED:
        raise HTTPException(status_code=404, detail="Metrics disabled")
    body, ctype = metrics_response()
    return Response(content=body, media_type=ctype)

static_dir = Path(__file__).parent.parent / "static"
docs_dir   = Path(__file__).parent.parent / "docs"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
app.mount("/docs",   StaticFiles(directory=str(docs_dir)),   name="docs")


class HistoryMessage(BaseModel):
    role:    str
    content: str


class ChatRequest(BaseModel):
    question:   str
    history:    list[HistoryMessage] = []
    session_id: str = ""


class SourceItem(BaseModel):
    source:       str
    page:         int
    score:        float
    display_name: str = ""
    download_url: str = ""
    agent_id:     str = ""


class PerAgentInfo(BaseModel):
    agent_id:          str
    agent_name:        str = ""
    pipeline:          str = ""
    qc:                float = 0.0
    router_reason:     str = ""
    complexity_intent: str = ""


class ChatResponse(BaseModel):
    answer:                str
    agents_used:           list[str]
    agent_names:           list[str]
    primary_agent:         str
    supervisor_reason:     str
    supervisor_intent:     str = ""
    supervisor_confidence: float = 0.0
    router_reason:         str = ""
    complexity_intent:     str = ""
    pipeline:              str
    qc:                float
    t_total:           float
    t_retrieval:       float
    t_llm:             float
    n_rounds:          int
    sources:           list[SourceItem]
    per_agent:         list[PerAgentInfo] = []
    session_id:        str = ""
    retrieval_query:   str = ""
    was_rewritten:     bool = False
    session_turn:      int = 0
    sub_questions:     list[str] = []
    planner_used:      bool = False
    planner_reason:    str = ""
    in_scope:          bool = True
    scope_category:    str = "kma"


class SessionResponse(BaseModel):
    session_id: str


admin_static = static_dir / "admin"


@app.get("/")
def index():
    return FileResponse(str(static_dir / "index.html"))


@app.get("/admin/login")
def admin_login_page():
    return FileResponse(str(admin_static / "login.html"))


@app.get("/admin/verify-otp")
def admin_verify_otp_page():
    return FileResponse(str(admin_static / "verify-otp.html"))


@app.get("/admin/dashboard")
def admin_dashboard_page():
    return FileResponse(str(admin_static / "dashboard.html"))


@app.get("/portal/status")
def portal_status():
    """Cổng SV: banner bảo trì & agent tạm tắt (không cần đăng nhập)."""
    s = load_settings()
    return {
        "maintenance_message": s.get("maintenance_message") or "",
        "disabled_agents": s.get("disabled_agents") or [],
    }


@app.get("/news")
def public_news_list():
    """Danh sách tin mới công khai cho trang chủ."""
    return {"items": list_news_items()}


@app.get("/bang-diem")
def bang_diem_page():
    return FileResponse(str(static_dir / "bang-diem.html"))


@app.get("/lich-hoc")
def lich_hoc_page():
    return FileResponse(str(static_dir / "lich-hoc.html"))


@app.get("/agents")
def list_agents():
    return {
        "agents": [
            {
                "id":          aid,
                "name":        cfg["name"],
                "folder":      cfg["folder"],
                "description": cfg["description"],
            }
            for aid, cfg in AGENTS.items()
        ]
    }


@app.post("/session/new", response_model=SessionResponse)
def new_session():
    return SessionResponse(session_id=system.create_session())


class SessionCloseRequest(BaseModel):
    session_id: str = ""


@app.post("/session/close")
def close_session(req: SessionCloseRequest):
    """Flush session xuống DB lạnh và giải phóng cache nóng."""
    sid = (req.session_id or "").strip()
    if not sid:
        raise HTTPException(status_code=400, detail="session_id required")
    from agents.session_memory import session_store
    session_store.close_session(sid)
    return {"ok": True, "session_id": sid}


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest, request: Request):
    history = [{"role": m.role, "content": m.content} for m in req.history]
    sid     = req.session_id.strip() or None
    ip      = client_ip(request)
    try:
        with track_chat_connection():
            with CHAT_LATENCY.labels(endpoint="/chat").time():
                result = system.chat(req.question, history=history, session_id=sid)
        CHAT_REQUESTS.labels(endpoint="/chat", outcome="ok").inc()
        record_chat(session_id=sid, question=req.question, result=result, client_ip=ip, stream=False)
    except Exception:
        CHAT_REQUESTS.labels(endpoint="/chat", outcome="error").inc()
        raise
    return ChatResponse(
        answer            = result.answer,
        agents_used       = result.agents_used,
        agent_names       = result.agent_names,
        primary_agent     = result.primary_agent,
        supervisor_reason     = result.supervisor_reason,
        supervisor_intent     = result.supervisor_intent,
        supervisor_confidence = result.supervisor_confidence,
        router_reason         = result.router_reason,
        complexity_intent     = result.complexity_intent,
        pipeline              = result.pipeline,
        qc                = result.qc,
        t_total           = result.t_total,
        t_retrieval       = result.t_retrieval,
        t_llm             = result.t_llm,
        n_rounds          = result.n_rounds,
        sources           = [SourceItem(**s) for s in result.sources],
        per_agent         = [
            PerAgentInfo(
                agent_id   = p.get("agent_id", ""),
                agent_name = p.get("agent_name", AGENTS.get(p.get("agent_id", ""), {}).get("name", "")),
                pipeline          = p.get("pipeline", ""),
                qc                = p.get("qc", 0.0),
                router_reason     = p.get("router_reason", ""),
                complexity_intent = p.get("complexity_intent", ""),
            )
            for p in result.per_agent
        ],
        session_id        = result.session_id,
        retrieval_query   = result.retrieval_query,
        was_rewritten     = result.was_rewritten,
        session_turn      = result.session_turn,
        sub_questions     = result.sub_questions,
        planner_used      = result.planner_used,
        planner_reason    = result.planner_reason,
        in_scope          = result.in_scope,
        scope_category    = result.scope_category,
    )


@app.post("/chat/stream")
def chat_stream(req: ChatRequest, request: Request):
    history = [{"role": m.role, "content": m.content} for m in req.history]
    sid     = req.session_id.strip() or None
    ip      = client_ip(request)

    def sse():
        try:
            with track_chat_connection():
                for event in system.chat_stream(req.question, history=history, session_id=sid):
                    if isinstance(event, dict) and event.get("type") == "done":
                        record_chat_from_event(
                            session_id=sid,
                            question=req.question,
                            event=event,
                            client_ip=ip,
                        )
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
            CHAT_REQUESTS.labels(endpoint="/chat/stream", outcome="ok").inc()
        except Exception:
            CHAT_REQUESTS.labels(endpoint="/chat/stream", outcome="error").inc()
            raise
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        sse(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/forms/filled/{download_id}/{filename}")
def download_filled_form(download_id: str, filename: str):
    """Tải bản sao đơn đã điền (không phải file gốc trong docs/)."""
    path = get_filled_file_path(download_id)
    if not path or path.name != filename:
        raise HTTPException(status_code=404, detail="File không tồn tại hoặc đã hết hạn.")
    return FileResponse(
        str(path),
        filename=filename,
        media_type="application/octet-stream",
    )


@app.get("/health")
def health():
    return {
        "status": "ok",
        "mode":   "multi_agent",
        "agents": AGENT_IDS,
        "memory":  "rewrite + session_summary",
        "planner":   "question_decomposition",
        "guardrail": "scope_filter",
    }
