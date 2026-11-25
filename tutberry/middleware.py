"""JSON request logs with correlation identifiers."""
import time
import uuid

import structlog
from opentelemetry import trace

from tutberry.metrics import DURATION, REQUESTS

structlog.configure(processors=[structlog.contextvars.merge_contextvars, structlog.processors.add_log_level, structlog.processors.TimeStamper(fmt="iso", utc=True), structlog.processors.JSONRenderer()], logger_factory=structlog.PrintLoggerFactory(), cache_logger_on_first_use=True)
logger = structlog.get_logger()

class RequestLoggingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        structlog.contextvars.clear_contextvars()
        request_id = request.headers.get("X-Request-Id") or str(uuid.uuid4())
        context = trace.get_current_span().get_span_context()
        structlog.contextvars.bind_contextvars(request_id=request_id, trace_id=format(context.trace_id, '032x') if context.is_valid else None)
        start = time.perf_counter()
        try:
            response = self.get_response(request)
        except Exception:
            logger.exception("request_failed", method=request.method, path=request.path)
            raise
        route = request.resolver_match.route if request.resolver_match else "unmatched"
        if route != "metrics":
            method = request.method if request.method in {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"} else "OTHER"
            REQUESTS.labels(method, route, str(response.status_code)).inc()
            DURATION.labels(method, route).observe(time.perf_counter() - start)
        response["X-Request-Id"] = request_id
        logger.info("request_handled", method=request.method, path=request.path, status_code=response.status_code, duration_ms=int((time.perf_counter()-start)*1000))
        return response


class NoStoreMiddleware:
    """Prevent caching of API responses containing user or booking data."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.path.startswith("/api/"):
            response["Cache-Control"] = "no-store"
        return response
