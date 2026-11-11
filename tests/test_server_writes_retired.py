"""The server takes no writes from the web any more (issue #724, towards a server that takes no writes: #334).

Loading data is the job of the scheduled refresh of the archive (``archive-refresh.yml``), removing a competition is the purge (``archive-purge.yml``) and the Administration page of
the web is gone. So the routes that scraped, ingested history or dropped a collection, and the separate scraper service that served them, are gone too. So is the old predictive analysis
(#853: ``/analysis/*``, ``/historical/*``, scikit-learn, the HISTORICAL and ELASTICITIES collections): the preview of the match and the simulation of the league are computed in the browser.
"""
import importlib.util
from pathlib import Path

import pytest

from api_routes import api_operations
from src.api.app import app

ROOT = Path(__file__).resolve().parents[1]


def _routes():
    """The operations of the API now (from the OpenAPI schema: ``app.routes`` is nested in newer FastAPI versions and a flat loop over it sees none of them, see ``api_routes``)."""
    return set(api_operations(app))


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


def test_no_route_of_the_old_predictive_analysis_is_left():
    left = [path for _, path in _routes() if path.startswith(("/api/v1/analysis", "/api/v1/historical"))]
    assert left == []


def test_the_listing_of_the_competitions_stays():
    assert ("GET", "/api/v1/collections/list") in _routes()


def test_the_server_has_no_route_that_needs_the_admin_key_any_more():
    """Nothing is trained or ingested through the API: the guard (``require_admin``) stays as the pattern for a write endpoint, tested in ``test_admin_auth``."""
    from api_routes import takes_the_admin_key

    assert [key for key, operation in api_operations(app).items() if takes_the_admin_key(operation)] == []


def test_the_separate_scraper_service_is_gone():
    assert importlib.util.find_spec("src.api.scraper_app") is None
    assert not (ROOT / "run_scraper.py").exists()


def test_the_services_the_refresh_uses_are_still_there():
    from src.services.fbcyl_match_ingest import scrape_fbcyl_collection  # noqa: F401
    from src.services.feb_match_ingest import scrape_feb_collection  # noqa: F401
