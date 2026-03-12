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
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routers import collections, teams, players, lineups

app = FastAPI(
    title="MetricsForAll API",
    description="Basketball statistics API — FEB / FBCYL Spanish leagues",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ---------------------------------------------------------------------------
# CORS — wide open in dev; tighten for production deploy
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(collections.router, prefix="/api/collections", tags=["collections"])
app.include_router(teams.router,       prefix="/api/teams",       tags=["teams"])
app.include_router(players.router,     prefix="/api/players",     tags=["players"])
app.include_router(lineups.router,     prefix="/api/lineups",     tags=["lineups"])


@app.get("/", tags=["health"])
def root():
    """Health-check endpoint."""
    return {"status": "ok", "app": "MetricsForAll API"}
