import time
from collections import defaultdict
from ipaddress import ip_address
from threading import Lock

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.core.config import settings

SEARCH_PREFIXES = ("/projects/",)
INDEXING_PREFIXES = ("/projects", "/index")


class _Window:
    def __init__(self, limit: int) -> None:
        self.limit = limit
        self.count = 0
        self.window_start = time.monotonic()

    def allow(self, now: float, window_seconds: float = 60.0) -> bool:
        if now - self.window_start >= window_seconds:
            self.window_start = now
            self.count = 0
        if self.count >= self.limit:
            return False
        self.count += 1
        return True


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app) -> None:
        super().__init__(app)
        self._lock = Lock()
        self._buckets: dict[tuple[str, str], _Window] = defaultdict(
            lambda: _Window(settings.rate_limit_per_minute)
        )

    def _client_key(self, request) -> str:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        host = request.client.host if request.client else "unknown"
        try:
            return str(ip_address(host))
        except ValueError:
            return host

    def _limit_for(self, path: str) -> int:
        if any(path.startswith(prefix) and path.endswith("/search") for prefix in SEARCH_PREFIXES):
            return settings.search_rate_limit_per_minute
        if any(path.startswith(prefix) for prefix in INDEXING_PREFIXES):
            return settings.indexing_rate_limit_per_minute
        return settings.rate_limit_per_minute

    async def dispatch(self, request, call_next):
        if not settings.rate_limit_enabled:
            return await call_next(request)

        path = request.url.path
        limit = self._limit_for(path)
        key = (self._client_key(request), path)
        with self._lock:
            window = self._buckets.get(key)
            if window is None or window.limit != limit:
                window = _Window(limit)
                self._buckets[key] = window
            allowed = window.allow(time.monotonic())
        if not allowed:
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded. Please slow down and retry shortly."},
            )
        return await call_next(request)
