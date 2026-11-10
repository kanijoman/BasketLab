"""The API endpoints that nothing called are gone (#202, with the check of 10/11/2026).

Every path of the API was searched in the web, the app, the scripts and the workflows: these had no reference at all. The packages are built by Actions and the app
downloads them from the ``live-packages`` branch (the endpoint «se retira con #334» of docs/LIVE.md, which stayed), the web makes its PDF, DOCX and multi-phase tables in
the browser, and nobody asked for the other reports. What the web or the development mode (``?data=api``) does use is still there.
"""
import importlib.util

import pytest

from src.api.app import app
from src.services.multi_phase_service import MultiPhaseService

REMOVED_ROUTES = [
    "/api/v1/reports/export-pdf",
    "/api/v1/reports/{collection}/player-scouting/{player_id}",
    "/api/v1/reports/{collection}/team-scouting/{team_name}",
    "/api/v1/reports/{collection}/season-summary",
    "/api/v1/multi/team-stats/breakdown",
    "/api/v1/multi/player-stats/breakdown",
    "/api/v1/collections/{name}/freshness",
]


def paths():
    return {getattr(route, "path", "") for route in app.routes}


@pytest.mark.parametrize("path", REMOVED_ROUTES)
def test_the_endpoint_without_a_client_is_gone(path):
    assert path not in paths()


def test_the_live_router_is_gone_with_its_four_endpoints():
    assert not [p for p in paths() if p.startswith("/api/v1/live")]
    assert importlib.util.find_spec("src.api.routers.live_package") is None


def test_the_report_builders_only_those_endpoints_used_are_gone():
    assert importlib.util.find_spec("src.services.report_service") is None


@pytest.mark.parametrize("name", ["get_team_stats_breakdown", "get_player_stats_breakdown"])
def test_the_multi_phase_breakdowns_are_gone(name):
    assert not hasattr(MultiPhaseService, name)


@pytest.mark.parametrize("path", [
    "/api/v1/health", "/api/v1/multi/team-stats", "/api/v1/multi/player-stats", "/api/v1/multi/sibling-collections",
    "/api/v1/reports/individual-scouting/docx", "/api/v1/reports/{collection}/weekly-report", "/api/v1/reports/team-report/{collection}",
    "/api/v1/matches/{collection}", "/api/v1/scouting-rival",
])
def test_what_the_web_or_the_development_mode_still_uses_stays(path):
    assert path in paths()
