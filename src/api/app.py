"""FastAPI application for BasketLab basketball analytics.

Exposes the existing service layer (`src/services/`) over HTTP, allowing a
React front-end (or any HTTP client) to consume basketball statistics without
running the PyQt6 desktop application.

Usage
-----
From the repo root::

    uvicorn src.api.app:app --reload --port 8000

Or via the provided ``run_api.py`` helper at the repo root.
"""
import json
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.api.routers import collections, teams, players, lineups, scrape
from src.api.routers import shots, possessions, ai, reports, historical, analysis
from src.api.routers import analysis_predictive, matches, multi_phase


class UTF8JSONResponse(JSONResponse):
    """JSONResponse that always emits ``Content-Type: application/json; charset=utf-8``.

    FastAPI's default response omits the charset, which can cause browsers to
    misinterpret non-ASCII characters (ñ, tildes, ª …) when the context does
    not inherit an explicit encoding.  Explicit charset=utf-8 removes all
    ambiguity.
    """

    media_type = "application/json; charset=utf-8"

    def render(self, content: object) -> bytes:
        return json.dumps(
            content,
            ensure_ascii=False,
            allow_nan=False,
            indent=None,
            separators=(",", ":"),
        ).encode("utf-8")


app = FastAPI(
    title="BasketLab API",
    description="Basketball statistics API — FEB / FBCYL Spanish leagues",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    default_response_class=UTF8JSONResponse,
)

# ---------------------------------------------------------------------------
# CORS — reads ALLOWED_ORIGINS env var (comma-separated).
# In production (ENVIRONMENT=production) the variable is mandatory.
# In development it defaults to allowing all origins ("*").
# ---------------------------------------------------------------------------
_environment = os.getenv("ENVIRONMENT", "development")
_origins_env = os.getenv("ALLOWED_ORIGINS", "")
if not _origins_env and _environment == "production":
    raise RuntimeError(
        "ALLOWED_ORIGINS env var is required in production. "
        "Set it to the frontend URL, e.g. https://basketlab.vercel.app"
    )
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
app.include_router(scrape.router,      prefix="/api/v1/scrape",      tags=["scrape"])
app.include_router(shots.router,       prefix="/api/v1/shots",       tags=["shots"])
app.include_router(possessions.router, prefix="/api/v1/possessions", tags=["possessions"])
app.include_router(ai.router,          prefix="/api/v1/ai",          tags=["ai"])
app.include_router(reports.router,     prefix="/api/v1/reports",     tags=["reports"])
app.include_router(historical.router,  prefix="/api/v1/historical",  tags=["historical"])
app.include_router(analysis.router,    prefix="/api/v1/analysis",    tags=["analysis"])
app.include_router(analysis_predictive.router, prefix="/api/v1/analysis", tags=["analysis"])
app.include_router(matches.router,             prefix="/api/v1/matches",  tags=["matches"])
app.include_router(multi_phase.router,         prefix="/api/v1/multi",    tags=["multi-phase"])


@app.get("/", tags=["health"])
def root():
    """Health-check endpoint."""
    return {"status": "ok", "app": "BasketLab API"}
