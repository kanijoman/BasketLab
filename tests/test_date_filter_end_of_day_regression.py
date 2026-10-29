"""Bug #643: ``to_date`` (``YYYY-MM-DD``, documented as inclusive) left out the games of that very day in FEB.

The routers turned ``to_date`` into midnight and the pipelines filter ``parsedDate <= to``; FEB writes the game with its time (``dd-mm-yyyy - hh:mm``), so
a game at 20:30 of the «hasta» day was out (FBCYL, whose pipelines keep only the day, had it in: the two leagues disagreed). The bound is the END of the day.
"""
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.api.app import app
from src.api.deps import get_db

V1 = "/api/v1"
LAST_DAY_EVENING = datetime(2025, 11, 12, 20, 30)
NEXT_DAY_MIDNIGHT = datetime(2025, 11, 13, 0, 0)


@pytest.fixture()
def client():
    app.dependency_overrides[get_db] = lambda: MagicMock()
    yield TestClient(app, raise_server_exceptions=True)
    app.dependency_overrides.clear()


def _bounds(date_filter: dict) -> tuple:
    return date_filter["$gte"], date_filter["$lte"]


def _assert_last_day_is_in(upper: datetime) -> None:
    assert LAST_DAY_EVENING <= upper < NEXT_DAY_MIDNIGHT


def test_team_tables_include_the_games_of_the_last_day(client):
    with patch("src.api.routers.teams.TeamStatsService") as svc:
        svc.return_value.load_season_data.return_value = {"team_stats": [], "opponent_stats": []}
        assert client.get(f"{V1}/teams/COL?from_date=2025-11-01&to_date=2025-11-12").status_code == 200
    lower, upper = _bounds(svc.return_value.load_season_data.call_args.kwargs["date_filter"])
    assert lower == datetime(2025, 11, 1)                                   # the start of the first day: unchanged
    _assert_last_day_is_in(upper)


def test_player_tables_include_the_games_of_the_last_day(client):
    with patch("src.api.routers.players.PlayerStatsService") as svc:
        svc.return_value.load_season_data.return_value = []
        assert client.get(f"{V1}/players/COL?from_date=2025-11-01&to_date=2025-11-12").status_code == 200
    lower, upper = _bounds(svc.return_value.load_season_data.call_args.kwargs["date_filter"])
    assert lower == datetime(2025, 11, 1)
    _assert_last_day_is_in(upper)


def test_the_stretch_of_a_comparison_includes_its_last_day_so_those_games_are_not_counted_as_the_rest_of_the_season(client):
    with patch("src.api.routers.teams.TeamComparisonService") as svc:
        svc.return_value.compare.return_value = {}
        assert client.get(f"{V1}/teams/COL/compare?by=period&from_date=2025-11-01&to_date=2025-11-12").status_code == 200
    _by, date_from, date_to = svc.return_value.compare.call_args.args[1:4]
    assert date_from == datetime(2025, 11, 1)
    _assert_last_day_is_in(date_to)


@pytest.mark.parametrize("path, patched, kwargs", [
    ("teams/COL", "src.api.routers.teams.TeamStatsService", {"team_stats": [], "opponent_stats": []}),
    ("players/COL", "src.api.routers.players.PlayerStatsService", []),
])
def test_only_to_date_and_only_from_date_still_work(client, path, patched, kwargs):
    with patch(patched) as svc:
        svc.return_value.load_season_data.return_value = kwargs
        client.get(f"{V1}/{path}?to_date=2025-11-12")
        only_to = svc.return_value.load_season_data.call_args.kwargs["date_filter"]
        client.get(f"{V1}/{path}?from_date=2025-11-01")
        only_from = svc.return_value.load_season_data.call_args.kwargs["date_filter"]
    assert set(only_to) == {"$lte"} and set(only_from) == {"$gte"}
    _assert_last_day_is_in(only_to["$lte"])
    assert only_from["$gte"] == datetime(2025, 11, 1)
