import time
import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from app.services.redis_client import get_redis_client

logger = structlog.get_logger()

REQUEST_ID_HEADER = "X-Request-ID"
LATENCY_SAMPLE_CAP = 500
LATENCY_ROUTES_SET_KEY = "latency:routes"


def _route_template(request: Request) -> str:
    """The path template (e.g. "/modules/{module_id}/status"), not the literal
    URL, so latency samples aggregate per *route* rather than per unique ID."""
    route = request.scope.get("route")
    return route.path if route is not None else request.url.path


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Binds a request ID into structlog's contextvars for the life of the
    request, so it's automatically attached to every log line emitted while
    handling it — ours and third-party libraries' alike. Reuses an inbound
    `X-Request-ID` header if present (so it composes with an upstream
    proxy/gateway's own tracing), otherwise mints a new one. Also stashed on
    `request.state` so route handlers can pass it into an enqueued ARQ job,
    extending the same trace across the async boundary into the worker."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get(REQUEST_ID_HEADER) or uuid.uuid4().hex
        request.state.request_id = request_id

        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)

        try:
            response = await call_next(request)
        finally:
            structlog.contextvars.clear_contextvars()

        response.headers[REQUEST_ID_HEADER] = request_id
        return response


class TimingMiddleware(BaseHTTPMiddleware):
    """Measures request duration, logs it, and records it into a per-route
    Redis list (capped, most-recent-N) that GET /admin/metrics reads back to
    compute p50/p95 — Redis rather than in-process memory so the numbers are
    correct with multiple worker processes/replicas, not just whichever one
    happened to serve a given request."""

    async def dispatch(self, request: Request, call_next) -> Response:
        start = time.perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        finally:
            duration_ms = (time.perf_counter() - start) * 1000
            route_path = _route_template(request)
            logger.info(
                "request_completed",
                method=request.method,
                path=route_path,
                status_code=status_code,
                duration_ms=round(duration_ms, 1),
            )
            await _record_route_latency(request.method, route_path, duration_ms)


async def _record_route_latency(method: str, route_path: str, duration_ms: float) -> None:
    key = f"latency:{method}:{route_path}"
    try:
        async with get_redis_client().pipeline(transaction=True) as pipe:
            pipe.lpush(key, duration_ms)
            pipe.ltrim(key, 0, LATENCY_SAMPLE_CAP - 1)
            pipe.sadd(LATENCY_ROUTES_SET_KEY, key)
            await pipe.execute()
    except Exception:
        logger.warning("failed to record route latency", key=key)
