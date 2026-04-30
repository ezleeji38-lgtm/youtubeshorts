"""FastAPI 진입점 (단일 사용자 로컬 도구)."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import shorts
from .config import settings
from .db import init_db

app = FastAPI(
    title=f"{settings.channel_name} — Cool Vibe Playlist Toolkit",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(shorts.router, prefix="/api/shorts", tags=["shorts"])


@app.on_event("startup")
def on_startup() -> None:
    init_db()


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "channel": settings.channel_name}
