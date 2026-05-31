"""
Session nóng–lạnh: Redis (TTL) + PostgreSQL (lâu dài), fallback RAM.
"""

from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any

from config import (
    HISTORY_HOT_MAX_MESSAGES,
    OPENAI_API_KEY,
    LLM_MODEL,
    SESSION_BACKEND,
    SESSION_COLD_IDLE_SEC,
    SESSION_HOT_TTL_SEC,
    SESSION_MAX_STORED,
    SESSION_SUMMARY_EVERY,
    SESSION_SUMMARY_MAX_CHARS,
    REDIS_URL,
)
from agents.conversation_context import format_history_text, trim_history
from agents.student_profile import StudentProfile

log = logging.getLogger(__name__)


@dataclass
class SessionState:
    session_id: str
    summary: str = ""
    turn_count: int = 0
    last_agents: list[str] = field(default_factory=list)
    last_form_filename: str = ""
    form_fill: object | None = None
    student_profile: StudentProfile = field(default_factory=StudentProfile)
    hot_messages: list[dict] = field(default_factory=list)
    last_activity: float = field(default_factory=time.time)
    query_cache: dict = field(default_factory=dict)
    QUERY_CACHE_TTL: float = 600

    def cache_query_result(self, question: str, result: dict):
        h = self._get_query_hash(question)
        self.query_cache[h] = (result, time.time())
        log.debug(
            "[session] query cached: %s, cache size=%d",
            question[:40],
            len(self.query_cache),
        )

    def get_cached_query_result(self, question: str) -> dict | None:
        h = self._get_query_hash(question)
        if h not in self.query_cache:
            return None
        result, timestamp = self.query_cache[h]
        if time.time() - timestamp > self.QUERY_CACHE_TTL:
            del self.query_cache[h]
            log.debug("[session] query cache expired: %s", question[:40])
            return None
        log.info("[session] query cache hit: %s", question[:40])
        return result

    @staticmethod
    def _get_query_hash(question: str) -> str:
        q_normalized = " ".join(question.lower().strip().split())
        return hashlib.md5(q_normalized.encode()).hexdigest()


class SessionStorageManager:
    """
    Facade session: memory | redis (+ postgres cold).
    API tương thích SessionStore cũ: create, get, after_turn.
    """

    def __init__(self, max_sessions: int = SESSION_MAX_STORED):
        self._max = max_sessions
        self._lock = threading.Lock()
        self._memory: dict[str, SessionState] = {}
        self._redis = None
        self._use_redis = SESSION_BACKEND == "redis" and bool(REDIS_URL)
        if self._use_redis:
            self._redis = self._connect_redis()

    @staticmethod
    def _connect_redis():
        try:
            import redis
            client = redis.from_url(REDIS_URL, decode_responses=True)
            client.ping()
            log.info("[session] Redis connected")
            return client
        except Exception as e:
            log.warning("[session] Redis unavailable, using memory: %s", e)
            return None

    @classmethod
    def from_config(cls) -> SessionStorageManager:
        return cls()

    def _redis_key(self, sid: str) -> str:
        return f"kma:session:{sid}"

    def _serialize_state(self, state: SessionState) -> str:
        payload = {
            "session_id": state.session_id,
            "summary": state.summary,
            "turn_count": state.turn_count,
            "last_agents": state.last_agents,
            "last_form_filename": state.last_form_filename,
            "hot_messages": state.hot_messages[-HISTORY_HOT_MAX_MESSAGES:],
            "last_activity": state.last_activity,
            "student_profile": asdict(state.student_profile) if state.student_profile else {},
        }
        return json.dumps(payload, ensure_ascii=False)

    def _deserialize_state(self, sid: str, raw: str) -> SessionState | None:
        try:
            d = json.loads(raw)
        except json.JSONDecodeError:
            return None
        prof = StudentProfile()
        sp = d.get("student_profile") or {}
        if isinstance(sp, dict):
            for k, v in sp.items():
                if hasattr(prof, k):
                    setattr(prof, k, v)
        return SessionState(
            session_id=sid,
            summary=d.get("summary", ""),
            turn_count=int(d.get("turn_count", 0)),
            last_agents=list(d.get("last_agents") or []),
            last_form_filename=d.get("last_form_filename", ""),
            form_fill=None,
            student_profile=prof,
            hot_messages=list(d.get("hot_messages") or []),
            last_activity=float(d.get("last_activity", time.time())),
        )

    def _persist_redis(self, state: SessionState):
        if not self._redis:
            return
        try:
            self._redis.setex(
                self._redis_key(state.session_id),
                SESSION_HOT_TTL_SEC,
                self._serialize_state(state),
            )
        except Exception as e:
            log.warning("[session] redis set failed: %s", e)

    def _load_redis(self, sid: str) -> SessionState | None:
        if not self._redis:
            return None
        try:
            raw = self._redis.get(self._redis_key(sid))
            if raw:
                return self._deserialize_state(sid, raw)
        except Exception as e:
            log.warning("[session] redis get failed: %s", e)
        return None

    def _evict_memory_if_needed(self):
        if len(self._memory) < self._max:
            return
        oldest = next(iter(self._memory))
        self._flush_cold(oldest, self._memory.get(oldest))
        del self._memory[oldest]
        log.info("[session] evicted memory %s", oldest[:8])

    def _flush_cold(self, sid: str, state: SessionState | None):
        """Đẩy session xuống PostgreSQL (best-effort)."""
        if not state or not sid:
            return
        try:
            from utils.session.cold_storage import persist_session_to_db
            persist_session_to_db(state)
            if self._redis:
                try:
                    self._redis.delete(self._redis_key(sid))
                except Exception:
                    pass
            log.info("[session] cold flush %s turns=%s", sid[:8], state.turn_count)
        except Exception as e:
            log.debug("[session] cold flush skipped: %s", e)

    def _maybe_flush_idle(self, state: SessionState):
        if time.time() - state.last_activity < SESSION_COLD_IDLE_SEC:
            return
        self._flush_cold(state.session_id, state)

    def create(self) -> str:
        sid = str(uuid.uuid4())
        state = SessionState(session_id=sid)
        with self._lock:
            self._evict_memory_if_needed()
            self._memory[sid] = state
        self._persist_redis(state)
        return sid

    def get(self, session_id: str | None) -> SessionState | None:
        if not session_id:
            return None
        with self._lock:
            state = self._memory.get(session_id)
        if state:
            return state
        loaded = self._load_redis(session_id)
        if loaded:
            with self._lock:
                self._memory[session_id] = loaded
            return loaded
        return None

    def _summarize(
        self,
        state: SessionState,
        history: list[dict],
        question: str,
        answer: str,
    ) -> str:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=OPENAI_API_KEY)
            resp = client.chat.completions.create(
                model=LLM_MODEL,
                messages=[{
                    "role": "user",
                    "content": (
                        f"Tóm tắt ngắn phiên KMA (tối đa {SESSION_SUMMARY_MAX_CHARS} ký tự).\n"
                        f"Tóm tắt cũ:\n{state.summary or '(Chưa có.)'}\n\n"
                        f"Hội thoại:\n{format_history_text(trim_history(history), max_chars=3000)}\n\n"
                        f"Câu hỏi: {question[:500]}\nTrả lời: {answer[:800]}\n\n"
                        "Tóm tắt mới (một đoạn):"
                    ),
                }],
                max_tokens=350,
                temperature=0.0,
            )
            text = resp.choices[0].message.content.strip()
            return text[:SESSION_SUMMARY_MAX_CHARS]
        except Exception as e:
            log.warning("[session] summarize failed: %s", e)
            return state.summary

    def after_turn(
        self,
        session_id: str,
        *,
        question: str,
        answer: str,
        agents_used: list[str],
        history: list[dict] | None = None,
    ) -> SessionState:
        with self._lock:
            state = self._memory.get(session_id)
            if not state:
                state = self._load_redis(session_id) or SessionState(session_id=session_id)
                self._memory[session_id] = state

            state.turn_count += 1
            state.last_agents = list(agents_used)
            state.last_activity = time.time()

            hist = history or []
            if question:
                state.hot_messages.append({"role": "user", "content": question[:2000]})
            if answer:
                state.hot_messages.append({"role": "assistant", "content": answer[:4000]})
            state.hot_messages = state.hot_messages[-HISTORY_HOT_MAX_MESSAGES:]

            if agents_used == ["bieu_mau"] or "bieu_mau" in agents_used:
                try:
                    from agents.form_filler import _resolve_filename
                    fn = _resolve_filename(question, hist)
                    if fn:
                        state.last_form_filename = fn
                except Exception:
                    pass

            if state.turn_count % SESSION_SUMMARY_EVERY == 0:
                state.summary = self._summarize(state, hist, question, answer)
                log.info("[session] %s summary updated (turn=%s)", session_id[:8], state.turn_count)

            self._persist_redis(state)
            self._maybe_flush_idle(state)
            return state

    def close_session(self, session_id: str | None):
        """Gọi khi client đóng chat — flush lạnh."""
        if not session_id:
            return
        with self._lock:
            state = self._memory.pop(session_id, None)
        if not state:
            state = self._load_redis(session_id)
        self._flush_cold(session_id, state)


def build_session_store() -> SessionStorageManager:
    return SessionStorageManager.from_config()
