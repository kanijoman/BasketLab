"""Minimal FastAPI app for the BasketLab scraper service.

Loads ONLY scrape + collections routers — never imports sklearn/scipy/numpy/pandas.
Saves ~200MB RAM vs the full app, making scraping viable on the free Render tier.

Usage
-----
    python run_scraper.py
"""
import json
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.api.routers import scrape, collections


class UTF8JSONResponse(JSONResponse):
    """JSONResponse that always emits Content-Type: application/json; charset=utf-8."""

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
    title="BasketLab Scraper API",
    description="Data ingestion service — FEB / FBCYL Spanish leagues",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    default_response_class=UTF8JSONResponse,
)

# ---------------------------------------------------------------------------
# CORS — same logic as the main app
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
# Routers — only scrape + collections (no ML, no analytics)
# ---------------------------------------------------------------------------
app.include_router(scrape.router,      prefix="/api/v1/scrape",      tags=["scrape"])
app.include_router(collections.router, prefix="/api/v1/collections", tags=["collections"])
