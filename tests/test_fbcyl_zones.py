"""FBCYL shot zones: team-relative half-court coordinates -> the same 10 zones as FEB (#150)."""
import pytest

from src.shotcharts.fbcyl_zones import extract_shots_fbcyl, stream_zone_counts_fbcyl
from src.shotcharts.feb_zones import ZONE_META, aggregate_zones
from db_helpers import new_mock_db


def _pt(x, y):
    return {"xnormalize": x, "ynormalize": y}


def _player(uuid, two_ok=(), two_ko=(), three_ok=(), three_ko=()):
    return {"uuid": uuid, "data": {
        "shootingOfTwoSuccessfulPoint": [_pt(*p) for p in two_ok],
        "shootingOfTwoFailedPoint": [_pt(*p) for p in two_ko],
        "shootingOfThreeSuccessfulPoint": [_pt(*p) for p in three_ok],
        "shootingOfThreeFailedPoint": [_pt(*p) for p in three_ko],
    }}


@pytest.fixture()
def coll():
    c = new_mock_db()["FBCYL_X"]
    c.insert_one({"stats": {"teams": [
        {"teamIdExtern": 10, "players": [_player("a", two_ok=[(11.6, 50.0)], two_ko=[(11.6, 50.0)])]},
        {"teamIdExtern": 20, "players": [_player("b", three_ko=[(20.0, 6.0)]), _player("c", two_ok=[(30.0, 30.0)])]},
    ]}})
    return c


def test_league_extraction_reads_all_teams_and_players(coll):
    shots = extract_shots_fbcyl(coll, team_id=None, player_filter=None)
    assert len(shots) == 4
    assert {s["made"] for s in shots} == {True, False}
    assert all({"zone", "made", "x", "y"} <= set(s) for s in shots)


def test_team_filter_uses_teamidextern_as_string_or_int(coll):
    assert len(extract_shots_fbcyl(coll, team_id="10", player_filter=None)) == 2
    assert len(extract_shots_fbcyl(coll, team_id="20", player_filter=None)) == 2


def test_player_filter_uses_uuid(coll):
    assert len(extract_shots_fbcyl(coll, team_id=None, player_filter="c")) == 1


def test_shot_next_to_the_basket_is_classified_in_the_paint(coll):
    shots = extract_shots_fbcyl(coll, team_id="10", player_filter=None)
    assert {s["zone"] for s in shots} == {"paint"}


def test_both_teams_share_the_same_orientation_regression():
    """Coordinates are already folded into one half for every team: the team index must not
    mirror the court (the FEB conversion would flip left/right for the second team)."""
    c = new_mock_db()["FBCYL_Y"]
    shot = [_pt(25.0, 20.0)]  # off-centre mid-range shot
    c.insert_one({"stats": {"teams": [
        {"teamIdExtern": 1, "players": [_player("a", two_ok=[(25.0, 20.0)])]},
        {"teamIdExtern": 2, "players": [_player("b", two_ok=[(25.0, 20.0)])]},
    ]}})
    a = extract_shots_fbcyl(c, "1", None)[0]
    b = extract_shots_fbcyl(c, "2", None)[0]
    assert (a["x"], a["y"], a["zone"]) == (b["x"], b["y"], b["zone"])
    assert shot  # fixture sanity


def test_stream_counts_have_the_feb_shape(coll):
    acc = stream_zone_counts_fbcyl(coll, team_id=None, player_filter=None)
    assert set(acc) == set(ZONE_META)
    zones = {z["zone"]: z for z in aggregate_zones(acc)}
    assert sum(z["fga"] for z in zones.values()) == 4
    assert zones["paint"]["fga"] == 2 and zones["paint"]["fgm"] == 1


def test_malformed_points_are_skipped():
    c = new_mock_db()["FBCYL_Z"]
    c.insert_one({"stats": {"teams": [{"teamIdExtern": 1, "players": [
        {"uuid": "a", "data": {"shootingOfTwoSuccessfulPoint": [{"x": 5}, None, _pt(10.0, 50.0)]}},
        {"uuid": "b"},
    ]}]}})
    assert len(extract_shots_fbcyl(c, None, None)) == 1
