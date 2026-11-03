"""The server takes no writes from the web any more (issue #724, towards switching Render off: #334).

Loading data is the job of the scheduled refresh of the archive (``archive-refresh.yml``), removing a competition is the purge (``archive-purge.yml``) and the Administration page of
the web is gone. So the routes that scraped, ingested history or dropped a collection, and the separate scraper service that served them, are gone too. What the kept predictive
code reads (``/historical/seasons``, ``/historical/teams``) and its training routes (behind ``ADMIN_API_KEY``) stay until the predictive analysis is reworked.
"""
import importlib.util
from pathlib import Path

import pytest

from src.api.app import app

ROOT = Path(__file__).resolve().parents[1]


def _routes():
    """The routes of the app NOW (not at import: a worker that collects many test modules must not freeze a half-built app) and a guard that it is the whole app."""
    routes = {(method, route.path) for route in app.routes for method in (getattr(route, "methods", None) or set())}
    assert ("GET", "/api/v1/health") in routes or any(path.startswith("/api/v1/") for _, path in routes), "the API routes are not mounted"
    return routes


RETIRED = [
    ("DELETE", "/api/v1/collections/{name}"),
    ("POST", "/api/v1/scrape/start"),
    ("GET", "/api/v1/scrape/progress/{job_id}"),
    ("GET", "/api/v1/scrape/feb/competitions"),
    ("GET", "/api/v1/scrape/feb/seasons"),
    ("GET", "/api/v1/scrape/feb/groups"),
    ("GET", "/api/v1/scrape/fbcyl/init"),
    ("GET", "/api/v1/scrape/fbcyl/categories"),
    ("GET", "/api/v1/scrape/fbcyl/competitions"),
    ("POST", "/api/v1/historical/ingest"),
    ("POST", "/api/v1/historical/ingest_competition"),
    ("GET", "/api/v1/historical/progress/{job_id}"),
]


@pytest.mark.parametrize("method, path", RETIRED)
def test_the_route_is_gone(method, path):
    assert (method, path) not in _routes()


def test_no_route_of_the_scrape_router_is_left():
    assert not [path for _, path in _routes() if path.startswith("/api/v1/scrape")]


def test_the_reads_the_kept_code_needs_and_the_listing_stay():
    for route in (("GET", "/api/v1/collections/list"), ("GET", "/api/v1/historical/seasons"), ("GET", "/api/v1/historical/teams"),
                  ("POST", "/api/v1/analysis/elasticity/train")):
        assert route in _routes()


def test_the_separate_scraper_service_is_gone():
    assert importlib.util.find_spec("src.api.scraper_app") is None
    assert not (ROOT / "run_scraper.py").exists()
    render = (ROOT / "render.yaml").read_text(encoding="utf-8")
    assert "basketlab-scraper" not in render and "run_scraper.py" not in render


def test_the_services_the_refresh_uses_are_still_there():
    from src.services.fbcyl_match_ingest import scrape_fbcyl_collection  # noqa: F401
    from src.services.feb_match_ingest import scrape_feb_collection  # noqa: F401
