"""The shots of a competition published for the web (#685): one row per shot with its team and player, in the order the server reads them, so that the zones and
the raw shots of a team or a player are what the shot endpoints answer."""
import json
import sys
from pathlib import Path

import pytest
from db_helpers import new_mock_db

sys.path.insert(0, str(Path(__file__).resolve().parent / "local_vectors"))

import fbcyl_games  # noqa: E402
import games  # noqa: E402
from src.local_data.export import FORMAT  # noqa: E402
from src.local_data.shots_export import COLUMNS, export_shots  # noqa: E402
from src.shotcharts.fbcyl_zones import extract_shots_fbcyl  # noqa: E402
from src.shotcharts.feb_zones import classify_zone, extract_shots_feb  # noqa: E402

FEB = "L_F_-2_2025_2026_Liga_Regular_B"
FBCYL = "FBCYL_1ª_FASE-GRUPO_A-1_2026_"


@pytest.fixture()
def db():
    database = new_mock_db("shots")
    database[FEB].insert_many(games.build_games())
    database[FBCYL].insert_many(fbcyl_games.build_games())
    return database


def _rows(payload):
    return [dict(zip(payload["columns"], row)) for row in payload["shots"]]


def _slim(shots):
    return [{"x": s["x"], "y": s["y"], "made": s["made"], "zone": s["zone"]} for s in shots]


def test_the_payload_says_what_it_is_and_is_plain_json(db):
    payload = export_shots(db[FEB], FEB)
    assert (payload["format"], payload["league"], payload["collection"]) == (FORMAT, "feb", FEB)
    assert payload["columns"] == list(COLUMNS) and payload["games"] == 12
    assert payload["shots"] and len(payload["shots"][0]) == len(COLUMNS)
    json.dumps(payload)


def test_a_feb_shot_has_its_zone_its_team_and_its_player(db):
    rows = _rows(export_shots(db[FEB], FEB))
    assert all(r["zone"] == classify_zone(r["x"], r["y"]) for r in rows)
    assert {r["team_id"] for r in rows} <= {t[0] for t in games.TEAMS}
    assert any(r["player_id"] is None for r in rows) and any(r["player_id"] for r in rows)          # a dorsal no player has: for the team, for no player
    assert len(rows) == 12 * 24                                                                     # the two shots of a slot that does not exist are not there


@pytest.mark.parametrize("team", [t[0] for t in games.TEAMS])
def test_the_shots_of_a_feb_team_are_what_the_server_extracts_in_the_same_order(db, team):
    rows = [r for r in _rows(export_shots(db[FEB], FEB)) if r["team_id"] == team]
    assert _slim(rows) == _slim(extract_shots_feb(db[FEB], team, None)) and rows


def test_the_shots_of_a_feb_player_are_what_the_server_extracts(db):
    rows = _rows(export_shots(db[FEB], FEB))
    for player in sorted({r["player_id"] for r in rows if r["player_id"]})[:6]:
        mine = [r for r in rows if r["player_id"] == player]
        assert _slim(mine) == _slim(extract_shots_feb(db[FEB], None, player)), player


def test_the_whole_competition_is_what_the_server_extracts_without_filters(db):
    assert _slim(_rows(export_shots(db[FEB], FEB))) == _slim(extract_shots_feb(db[FEB], None, None))


def test_fbcyl_shots_come_from_the_player_coordinates_with_the_team_and_the_player_uuid(db):
    payload = export_shots(db[FBCYL], FBCYL)
    rows = _rows(payload)
    assert payload["league"] == "fbcyl" and rows
    assert _slim(rows) == _slim(extract_shots_fbcyl(db[FBCYL], None, None))
    team = rows[0]["team_id"]
    assert _slim([r for r in rows if r["team_id"] == team]) == _slim(extract_shots_fbcyl(db[FBCYL], team, None))
    uuid = next(r["player_id"] for r in rows if r["player_id"])
    assert _slim([r for r in rows if r["player_id"] == uuid]) == _slim(extract_shots_fbcyl(db[FBCYL], None, uuid))


def test_a_competition_with_no_shots_has_none(db):
    db["NONE"].insert_many([{k: v for k, v in g.items() if k != "SHOTCHART"} for g in games.build_games()])
    assert export_shots(db["NONE"], "NONE")["shots"] == []
