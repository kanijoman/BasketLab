"""GET /shots/{collection}?compare=league rates each zone against how the competition shoots there (#139, #760).

The reference is the distribution of the teams (or of the players, when a player is asked for) of the competition, not an average with fixed margins: ``above`` over the upper quartile,
``below`` under the lower one, weighted by the attempts of each entity.
"""
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


# eight teams of the competition: the key_area at 40, 42, … 54 % on 100 shots each and the top three at 30 % on 50
COMPETITION = {str(i): _accum(key_area=(40 + 2 * i, 100), center_three=(15, 50)) for i in range(8)}
TEAM = COMPETITION["7"]                       # 54 %
LOW = COMPETITION["0"]                        # 40 %
MID = COMPETITION["3"]                        # 46 %


@pytest.fixture()
def client():
    app.dependency_overrides[get_db] = lambda: MagicMock()
    yield TestClient(app)
    app.dependency_overrides.clear()


def _stream(accum):
    return patch("src.api.routers.shots._stream_zone_counts_feb", side_effect=lambda coll, team_id, player_filter: accum)


def _owners(table=None):
    return patch("src.api.routers.shots.zone_counts_by_owner", side_effect=lambda coll, name, by: table or COMPETITION)


def _by_zone(resp):
    return {z["zone"]: z for z in resp.json()}


def test_default_response_has_no_rating_fields_and_asks_for_no_distribution(client):
    with _stream(TEAM), _owners() as owners:
        r = client.get(f"{URL}?team_id=7")
    assert owners.call_count == 0
    assert "rating" not in r.json()[0]


def test_compare_league_rates_a_team_against_the_distribution_of_the_teams(client):
    with _stream(TEAM), _owners() as owners:
        r = client.get(f"{URL}?team_id=7&compare=league")
    assert r.status_code == 200 and owners.call_args.args[2] == "team" and owners.call_count == 1
    zones = _by_zone(r)
    assert zones["key_area"]["rating"] == "above" and zones["key_area"]["league_pct"] == pytest.approx(47.0)
    assert zones["key_area"]["percentile"] == pytest.approx(100 * 7.5 / 8)
    assert zones["center_three"]["rating"] == "average"                         # every team shoots alike there: nobody is above or below
    assert zones["left_corner_three"]["rating"] == "none"                           # the team did not shoot there


def test_the_lowest_team_is_below_and_the_middle_one_is_average(client):
    with _stream(LOW), _owners():
        assert _by_zone(client.get(f"{URL}?team_id=0&compare=league"))["key_area"]["rating"] == "below"
    with _stream(MID), _owners():
        assert _by_zone(client.get(f"{URL}?team_id=3&compare=league"))["key_area"]["rating"] == "average"


def test_compare_league_without_filters_rates_the_competition_against_its_teams_once(client):
    league = _accum(key_area=(376, 800), center_three=(120, 400))
    with _stream(league), _owners() as owners:
        r = client.get(f"{URL}?compare=league")
    assert owners.call_count == 1 and owners.call_args.args[2] == "team"
    assert _by_zone(r)["key_area"]["rating"] == "average"


def test_compare_league_for_a_player_uses_the_distribution_of_the_players(client):
    players = {f"p{i}": _accum(key_area=(m, 50)) for i, m in enumerate((15, 17, 19, 21, 23, 25))}
    players["rookie"] = _accum(key_area=(1, 1))                                  # a single shot at 100 %: it weighs one shot
    with _stream(players["p5"]), _owners(players) as owners:
        r = client.get(f"{URL}?player=p5&compare=league")
    assert owners.call_args.args[2] == "player"
    assert _by_zone(r)["key_area"]["rating"] == "above"


def test_invalid_compare_value_is_422(client):
    assert client.get(f"{URL}?compare=other").status_code == 422


def _fbcyl_db():
    from db_helpers import new_mock_db

    coll = new_mock_db()["FBCYL_U16_2025_A"]
    pt = lambda x, y: {"xnormalize": x, "ynormalize": y}  # noqa: E731
    teams = [{"teamIdExtern": i, "players": [{"uuid": f"u{i}", "data": {
        "shootingOfTwoSuccessfulPoint": [pt(11.6, 50.0)] * (2 + i), "shootingOfTwoFailedPoint": [pt(11.6, 50.0)] * (8 - i)}}]} for i in range(8)]
    coll.insert_one({"stats": {"teams": teams}})
    db = MagicMock()
    db.connection.get_collection.return_value = coll
    return db


@pytest.fixture()
def fbcyl_client():
    app.dependency_overrides[get_db] = lambda: _fbcyl_db()
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_fbcyl_collections_now_return_zones(fbcyl_client):
    r = fbcyl_client.get("/api/v1/shots/FBCYL_U16_2025_A?team_id=1")
    zones = _by_zone(r)
    assert len(zones) == 10 and zones["key_area"]["fga"] == 10 and zones["key_area"]["fgm"] == 3


def test_fbcyl_compare_league_rates_against_the_distribution_of_the_fbcyl_teams(fbcyl_client):
    top = _by_zone(fbcyl_client.get("/api/v1/shots/FBCYL_U16_2025_A?team_id=7&compare=league"))["key_area"]
    assert top["league_pct"] == pytest.approx(55.0) and top["rating"] == "above"                 # 9 of 10 against teams from 2 to 9 of 10
    assert _by_zone(fbcyl_client.get("/api/v1/shots/FBCYL_U16_2025_A?team_id=0&compare=league"))["key_area"]["rating"] == "below"
    assert _by_zone(fbcyl_client.get("/api/v1/shots/FBCYL_U16_2025_A?team_id=4&compare=league"))["key_area"]["rating"] == "average"


def test_fbcyl_player_is_rated_against_the_players_by_uuid(fbcyl_client):
    zones = _by_zone(fbcyl_client.get("/api/v1/shots/FBCYL_U16_2025_A?player=u7&compare=league"))
    assert zones["key_area"]["rating"] == "above" and zones["key_area"]["fga"] == 10


def test_fbcyl_raw_shots_are_returned(fbcyl_client):
    r = fbcyl_client.get("/api/v1/shots/FBCYL_U16_2025_A/raw?team_id=1")
    assert len(r.json()) == 10 and {"x", "y", "made", "zone"} <= set(r.json()[0])
