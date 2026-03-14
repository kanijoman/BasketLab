"""FastAPI application for MetricsForAll basketball analytics.

Exposes the existing service layer (`src/services/`) over HTTP, allowing a
React front-end (or any HTTP client) to consume basketball statistics without
running the PyQt6 desktop application.

Usage
-----
From the repo root::

    uvicorn src.api.app:app --reload --port 8000

Or via the provided ``run_api.py`` helper at the repo root.
"""
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routers import collections, teams, players, lineups

app = FastAPI(
    title="MetricsForAll API",
    description="Basketball statistics API — FEB / FBCYL Spanish leagues",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ---------------------------------------------------------------------------
# CORS — reads ALLOWED_ORIGINS env var (comma-separated) for production.
# Falls back to wide-open for local development.
# ---------------------------------------------------------------------------
_origins_env = os.getenv("ALLOWED_ORIGINS", "")
_allowed_origins: list[str] = (
    [o.strip() for o in _origins_env.split(",") if o.strip()]
    if _origins_env
    else ["*"]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routers — all under /api/v1/ for forward-compatibility with auth layers
# ---------------------------------------------------------------------------
app.include_router(collections.router, prefix="/api/v1/collections", tags=["collections"])
app.include_router(teams.router,       prefix="/api/v1/teams",       tags=["teams"])
app.include_router(players.router,     prefix="/api/v1/players",     tags=["players"])
app.include_router(lineups.router,     prefix="/api/v1/lineups",     tags=["lineups"])


@app.get("/", tags=["health"])
def root():
    """Health-check endpoint."""
    return {"status": "ok", "app": "MetricsForAll API"}
