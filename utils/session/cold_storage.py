"""Lưu session đầy đủ xuống PostgreSQL (tầng lạnh)."""

from __future__ import annotations

import json
import logging

log = logging.getLogger(__name__)


def persist_session_to_db(state) -> None:
    """
    Best-effort persist — bỏ qua nếu DB chưa migrate hoặc không cấu hình.
    """
    try:
        from admin_auth.database import SessionLocal
        from admin_auth.models.chat_session import ChatSessionArchive
    except ImportError as e:
        log.debug("[session:cold] models unavailable: %s", e)
        return

    db = SessionLocal()
    try:
        messages_json = json.dumps(
            getattr(state, "hot_messages", []) or [],
            ensure_ascii=False,
        )
        existing = (
            db.query(ChatSessionArchive)
            .filter(ChatSessionArchive.session_id == state.session_id)
            .first()
        )
        if existing:
            existing.summary = (state.summary or "")[:4000]
            existing.turn_count = state.turn_count
            existing.last_agents = ",".join(state.last_agents or [])[:500]
            existing.messages_json = messages_json
        else:
            db.add(
                ChatSessionArchive(
                    session_id=state.session_id,
                    summary=(state.summary or "")[:4000],
                    turn_count=state.turn_count,
                    last_agents=",".join(state.last_agents or [])[:500],
                    messages_json=messages_json,
                )
            )
        db.commit()
    except Exception as e:
        db.rollback()
        raise
    finally:
        db.close()
