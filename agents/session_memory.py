"""
Session memory — facade tới SessionStorageManager (RAM / Redis + PostgreSQL).
"""

from agents.student_profile import StudentProfile
from utils.session_storage_manager import SessionState, SessionStorageManager, build_session_store

# Singleton dùng chung API + MultiAgentSystem
session_store: SessionStorageManager = build_session_store()

__all__ = [
    "SessionState",
    "StudentProfile",
    "session_store",
    "SessionStorageManager",
]
