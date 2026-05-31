"""
Đếm kết nối chat đang active (SSE / POST) — phục vụ load-adaptive router.
"""

from __future__ import annotations

import threading
from contextlib import contextmanager

_lock = threading.Lock()
_active = 0


def get_active_chat_connections() -> int:
    with _lock:
        return _active


@contextmanager
def track_chat_connection():
    global _active
    with _lock:
        _active += 1
    try:
        yield
    finally:
        with _lock:
            _active = max(0, _active - 1)
