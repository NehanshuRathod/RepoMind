from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.api.health import router as health_router
from app.api.projects import router as projects_router
from app.api.search import router as search_router
from app.core.config import settings
from app.core.database import init_db


app = FastAPI(title="Repomind API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    init_db()


app.include_router(auth_router)
app.include_router(projects_router)
app.include_router(search_router)
app.include_router(health_router)


@app.get("/")
def root():
    return {"message": "Repomind API is running", "docs": "/docs"}
