import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.api.health import router as health_router
from app.api.metrics import router as metrics_router
from app.api.projects import router as projects_router
from app.api.search import router as search_router
from app.core.config import settings
from app.core.database import init_db
from app.core.logger import log_event
from app.core.metrics import metrics
from app.core.ratelimit import RateLimitMiddleware


app = FastAPI(title="Repomind API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RateLimitMiddleware)


@app.middleware("http")
async def observability_middleware(request: Request, call_next):
    start = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        metrics.incr("http_requests_total", 1)
        metrics.incr("http_requests_errors_total", 1)
        log_event("request_error", path=request.url.path, method=request.method)
        raise
    duration = time.perf_counter() - start
    metrics.observe("http_request_duration_seconds", duration)
    metrics.incr("http_requests_total", 1)
    if response.status_code >= 500:
        metrics.incr("http_requests_errors_total", 1)
    log_event(
        "request",
        path=request.url.path,
        method=request.method,
        status_code=response.status_code,
        duration_seconds=round(duration, 4),
    )
    return response


@app.on_event("startup")
def on_startup() -> None:
    init_db()


app.include_router(auth_router)
app.include_router(projects_router)
app.include_router(search_router)
app.include_router(health_router)
app.include_router(metrics_router)


@app.get("/")
def root():
    return {"message": "Repomind API is running", "docs": "/docs"}
