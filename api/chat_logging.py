import logging

from admin_auth.database import SessionLocal
from admin_auth.services.chat_analytics import log_chat

log = logging.getLogger(__name__)


def record_chat(
    *,
    session_id: str | None,
    question: str,
    result,
    client_ip: str | None = None,
    stream: bool = False,
) -> None:
    try:
        db = SessionLocal()
        log_chat(
            db,
            session_id=session_id or getattr(result, "session_id", None),
            question=question,
            primary_agent=getattr(result, "primary_agent", None),
            agents_used=list(getattr(result, "agents_used", []) or []),
            pipeline=getattr(result, "pipeline", None),
            in_scope=getattr(result, "in_scope", True),
            qc=float(getattr(result, "qc", 0) or 0),
            t_total=float(getattr(result, "t_total", 0) or 0),
            source_count=len(getattr(result, "sources", []) or []),
            client_ip=client_ip,
            stream=stream,
        )
        db.close()
    except Exception as e:
        log.warning("chat log failed: %s", e)


def record_chat_from_event(
    *,
    session_id: str | None,
    question: str,
    event: dict,
    client_ip: str | None = None,
) -> None:
    if event.get("type") != "done":
        return
    try:
        db = SessionLocal()
        log_chat(
            db,
            session_id=session_id or event.get("session_id"),
            question=question,
            primary_agent=event.get("primary_agent"),
            agents_used=event.get("agents_used") or [],
            pipeline=event.get("pipeline"),
            in_scope=event.get("in_scope", True),
            qc=float(event.get("qc") or 0),
            t_total=float(event.get("t_total") or 0),
            source_count=len(event.get("sources") or []),
            client_ip=client_ip,
            stream=True,
        )
        db.close()
    except Exception as e:
        log.warning("chat stream log failed: %s", e)
