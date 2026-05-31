import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from admin_auth.core.config import settings
from admin_auth.observability.metrics import HTTP_REQUESTS


def _path_group(path: str) -> str:
    if path.startswith("/admin"):
        return "/admin/*"
    if path.startswith("/auth"):
        return "/auth/*"
    if path in ("/chat", "/chat/stream"):
        return path
    return "other"


class PrometheusMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if not settings.METRICS_ENABLED:
            return await call_next(request)

        t0 = time.perf_counter()
        response: Response = await call_next(request)
        elapsed = time.perf_counter() - t0
        group = _path_group(request.url.path)
        HTTP_REQUESTS.labels(
            method=request.method,
            path_group=group,
            status=str(response.status_code),
        ).inc()
        response.headers["X-Response-Time"] = f"{elapsed:.3f}"
        return response
