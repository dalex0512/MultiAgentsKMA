"""In-memory rate limiting for auth endpoints (single-process demo/production-small)."""

from __future__ import annotations

from datetime import datetime
from threading import Lock

from fastapi import HTTPException, Request, status


class InMemoryRateLimiter:
    def __init__(self) -> None:
        self._buckets: dict[str, list[float]] = {}
        self._lock = Lock()

    def enforce(self, key: str, *, max_calls: int, window_sec: int) -> None:
        now = datetime.utcnow().timestamp()
        cutoff = now - window_sec
        with self._lock:
            times = [t for t in self._buckets.get(key, []) if t > cutoff]
            if len(times) >= max_calls:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Quá nhiều yêu cầu. Vui lòng thử lại sau.",
                )
            times.append(now)
            self._buckets[key] = times


auth_rate_limiter = InMemoryRateLimiter()


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return "unknown"
