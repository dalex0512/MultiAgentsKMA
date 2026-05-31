import json
from datetime import datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from admin_auth.models.chat_log import ChatLog


def log_chat(
    db: Session,
    *,
    session_id: str | None,
    question: str,
    primary_agent: str | None,
    agents_used: list[str],
    pipeline: str | None,
    in_scope: bool,
    qc: float,
    t_total: float,
    source_count: int,
    client_ip: str | None = None,
    stream: bool = False,
) -> None:
    preview = (question or "").strip().replace("\n", " ")[:500]
    db.add(
        ChatLog(
            session_id=session_id,
            question_preview=preview,
            primary_agent=primary_agent,
            agents_used=json.dumps(agents_used, ensure_ascii=False),
            pipeline=pipeline,
            in_scope=in_scope,
            qc=qc or 0.0,
            t_total=t_total or 0.0,
            source_count=source_count or 0,
            client_ip=client_ip,
            stream=stream,
        )
    )
    db.commit()


def analytics_summary(db: Session, days: int = 7) -> dict:
    days = max(1, min(days, 90))
    since = datetime.utcnow() - timedelta(days=days)

    total = db.query(ChatLog).filter(ChatLog.created_at >= since).count()

    by_agent_rows = (
        db.query(ChatLog.primary_agent, func.count(ChatLog.id))
        .filter(ChatLog.created_at >= since, ChatLog.primary_agent.isnot(None))
        .group_by(ChatLog.primary_agent)
        .all()
    )
    by_agent = {row[0]: row[1] for row in by_agent_rows if row[0]}

    by_pipeline_rows = (
        db.query(ChatLog.pipeline, func.count(ChatLog.id))
        .filter(ChatLog.created_at >= since, ChatLog.pipeline.isnot(None))
        .group_by(ChatLog.pipeline)
        .all()
    )
    by_pipeline = {row[0]: row[1] for row in by_pipeline_rows if row[0]}

    avg_t = (
        db.query(func.avg(ChatLog.t_total))
        .filter(ChatLog.created_at >= since)
        .scalar()
    ) or 0.0

    in_scope_n = (
        db.query(ChatLog)
        .filter(ChatLog.created_at >= since, ChatLog.in_scope.is_(True))
        .count()
    )

    stream_n = (
        db.query(ChatLog)
        .filter(ChatLog.created_at >= since, ChatLog.stream.is_(True))
        .count()
    )

    recent = (
        db.query(ChatLog)
        .filter(ChatLog.created_at >= since)
        .order_by(ChatLog.created_at.desc())
        .limit(25)
        .all()
    )

    return {
        "days": days,
        "total_chats": total,
        "in_scope_rate": round(100 * in_scope_n / total, 1) if total else 0,
        "stream_share": round(100 * stream_n / total, 1) if total else 0,
        "avg_response_sec": round(float(avg_t), 2),
        "by_primary_agent": by_agent,
        "by_pipeline": by_pipeline,
        "recent": [
            {
                "id": r.id,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "question_preview": r.question_preview,
                "primary_agent": r.primary_agent,
                "pipeline": r.pipeline,
                "qc": r.qc,
                "t_total": r.t_total,
                "in_scope": r.in_scope,
                "stream": r.stream,
            }
            for r in recent
        ],
    }
