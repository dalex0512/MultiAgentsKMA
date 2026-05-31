"""Prometheus metrics — /metrics"""

from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

CHAT_REQUESTS = Counter(
    "kma_chat_requests_total",
    "Chat API requests",
    ["endpoint", "outcome"],
)
CHAT_LATENCY = Histogram(
    "kma_chat_latency_seconds",
    "Chat request latency",
    ["endpoint"],
    buckets=(0.5, 1, 2, 5, 10, 20, 40, 90, 180, 300),
)
AUTH_EVENTS = Counter(
    "kma_auth_events_total",
    "Auth events",
    ["event", "outcome"],
)
UPLOAD_EVENTS = Counter(
    "kma_admin_upload_total",
    "Admin document uploads",
    ["outcome"],
)
HTTP_REQUESTS = Counter(
    "kma_http_requests_total",
    "HTTP requests",
    ["method", "path_group", "status"],
)


def metrics_response():
    return generate_latest(), CONTENT_TYPE_LATEST
