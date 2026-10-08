"""GET /shots/{collection}?compare=league adds league-relative ratings per zone (#139)."""
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.api.app import app
from src.api.deps import get_db
from src.shotcharts.feb_zones import ZONE_META

URL = "/api/v1/shots/FEB_LF2_2025"


def _accum(**zones):
    acc = {z: {"fga": 0, "fgm": 0} for z in ZONE_META}
    for z, (fgm, fga) in zones.items():
        acc[z] = {"fga": fga, "fgm": fgm}
    return acc


TEAM = _accum(paint=(60, 100), top_three=(2, 50))
LEAGUE = _accum(paint=(4000, 10000), top_three=(1700, 5000))


@pytest.fixture()
def client():
    app.dependency_overrides[get_db] = lambda: MagicMock()
    yield TestClient(app)
    app.dependency_overrides.clear()


def _patch(side):
    return patch("src.api.routers.shots._stream_zone_counts_feb", side_effect=side)


def _by_zone(resp):
    return {z["zone"]: z for z in resp.json()}


def test_default_response_has_no_rating_fields(client):
    with _patch(lambda coll, team_id, player_filter: TEAM) as m:
        r = client.get(f"{URL}?team_id=7")
    assert m.call_count == 1
    assert "rating" not in r.json()[0]


def test_compare_league_adds_rating_fields(client):
    def side(coll, team_id, player_filter):
        return TEAM if team_id == "7" else LEAGUE

    with _patch(side) as m:
        r = client.get(f"{URL}?team_id=7&compare=league")
    assert r.status_code == 200
    zones = _by_zone(r)
    assert zones["paint"]["rating"] == "above"
    assert zones["paint"]["league_pct"] == pytest.approx(40.0)
    assert zones["top_three"]["rating"] == "below"
    assert zones["corner_left"]["rating"] == "none"
    assert m.call_count == 2  # team scan + league scan


def test_compare_league_without_filters_scans_once_and_is_average(client):
    with _patch(lambda coll, team_id, player_filter: LEAGUE) as m:
        r = client.get(f"{URL}?compare=league")
    assert m.call_count == 1
    assert _by_zone(r)["paint"]["rating"] == "average"


def test_compare_league_for_a_player_uses_the_league_baseline(client):
    def side(coll, team_id, player_filter):
        return TEAM if player_filter == "p1" else LEAGUE

    with _patch(side):
        r = client.get(f"{URL}?player=p1&compare=league")
    assert _by_zone(r)["paint"]["rating"] == "above"


def test_invalid_compare_value_is_422(client):
    assert client.get(f"{URL}?compare=other").status_code == 422


def test_fbcyl_returns_empty_even_with_compare(client):
    r = client.get("/api/v1/shots/FBCYL_U16_2025_A?compare=league")
    assert r.status_code == 200 and r.json() == []
