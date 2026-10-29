"""The contract rows of the FBCYL local player tables (#644): one row per player and game, with the identity already resolved.

FBCYL's player pipeline resolves identities in several passes (normalised name + uuid completed with ``$max``), drops the phantom players (timePlayed
40 and every stat zero) and reads the plus-minus from ``inOutsList`` with a ``$reduce``. The device does none of that: the exporter hands it clean
rows and it only sums by ``(player_uuid, team_id)``. The identity is completed over the WHOLE season, which is more correct than the pipeline's
(it completes it over the games the filter keeps).
"""
import sys
from pathlib import Path

import pytest
from db_helpers import new_mock_db

sys.path.insert(0, str(Path(__file__).resolve().parent / "local_vectors"))

from fbcyl_games import GHOST_GAME, GHOST_PLAYER, NO_UUID_GAMES, NO_UUID_PLAYER, PLAYERS, TEAMS, build_games  # noqa: E402
from src.local_data.export import export_collection, fbcyl_player_rows, in_out_balance, normalised_name  # noqa: E402

COLLECTION = "FBCYL_LEAGUE"


@pytest.fixture()
def collection():
    col = new_mock_db("fbcyl_players")[COLLECTION]
    col.insert_many(build_games())
    return col


def _rows(collection):
    return fbcyl_player_rows(collection)


def test_a_player_who_did_not_play_and_a_phantom_have_no_row(collection):
    rows = _rows(collection)
    # 12 games x 2 teams x 10 players, minus the one who never plays (the last) and the phantom of game 4 (one per team)
    assert len(rows) == 12 * 2 * (PLAYERS - 1) - 2
    ghost_game = build_games()[GHOST_GAME - 1]["_id"]
    assert not [r for r in rows if r["match_id"] == ghost_game and r["player_name"].startswith(f"JUGADOR{GHOST_PLAYER:02d}")]


def test_each_row_carries_venue_result_date_and_the_team(collection):
    rows = _rows(collection)
    game = build_games()[0]
    home = next(r for r in rows if r["match_id"] == game["_id"] and r["is_local"])
    away = next(r for r in rows if r["match_id"] == game["_id"] and not r["is_local"])
    assert (home["team_id"], away["team_id"]) == (TEAMS[0][0], TEAMS[1][0]) or (home["team_id"], away["team_id"]) == (TEAMS[1][0], TEAMS[0][0])
    assert home["starttime"] == game["stats"]["time"] and home["won"] != away["won"] or home["tied"]
    assert {"minutes", "pts", "val", "p1a", "p1m", "p2a", "p2m", "p3a", "p3m", "ro", "rd", "rt", "assist", "to", "bs", "st", "pf", "rf", "pllss"} <= set(home)
    assert "_id" not in home and "in_out_diffs" not in home and "uuid" not in home


def test_the_uuid_left_out_of_some_appearances_is_completed_from_the_players_other_games(collection):
    rows = _rows(collection)
    team_id, name = TEAMS[0]
    mine = [r for r in rows if r["team_id"] == team_id and r["player_name"].startswith(f"JUGADOR{NO_UUID_PLAYER:02d}")]
    assert len(mine) > len(NO_UUID_GAMES) and {r["player_uuid"] for r in mine} == {f"{team_id}-{NO_UUID_PLAYER:02d}"}


def test_a_player_without_any_uuid_falls_back_to_the_normalised_name():
    col = new_mock_db("nouuid")[COLLECTION]
    games = build_games()[:2]
    for game in games:
        for team in game["stats"]["teams"]:
            for player in team["players"]:
                player["uuid"] = None
    col.insert_many(games)
    rows = _rows(col)
    assert rows and all(r["player_uuid"] == normalised_name(r["player_name"]) for r in rows)


@pytest.mark.parametrize("name, expected", [
    ("MARIA GONZALEZ GARCIA", "M GONZALEZ GARCIA"),          # initial + the last two words
    ("ANA PEREZ", "A ANA PEREZ"),                            # two words: the first one is also "the one before the last"
    ("MADONNA", "M MADONNA MADONNA"),                        # one word: the negative index of $arrayElemAt counts from the end
    ("  DOS  ESPACIOS", "  ESPACIOS"),                       # split on every single space: the empty words count
    (None, None),
])
def test_the_normalised_name_is_the_one_of_the_pipeline(name, expected):
    assert normalised_name(name) == expected


@pytest.mark.parametrize("diffs, balance", [
    ([], 0), ([5], 0),                                       # nobody went in and out
    ([-15, -22, -37, -42, -41, -51], (-22 + 15) + (-42 + 37) + (-51 + 41)),
    ([0, 10, 3], 10),                                        # an IN without its OUT is not counted
    ([0, None, 3, 4], 0),                                    # a missing pointDiff makes the whole $reduce null: the game adds nothing
])
def test_the_plus_minus_is_the_sum_of_out_minus_in(diffs, balance):
    assert in_out_balance(diffs) == balance


def test_the_plus_minus_row_equals_what_the_in_out_list_says(collection):
    rows = {(r["match_id"], r["team_id"], r["player_name"]): r for r in _rows(collection)}
    for game in build_games():
        for team in game["stats"]["teams"]:
            for player in team["players"]:
                row = rows.get((game["_id"], team["teamIdExtern"], player["name"]))
                if row:
                    assert row["pllss"] == in_out_balance([e.get("pointDiff") for e in player["inOutsList"]])


def test_the_rows_do_not_depend_on_the_order_the_games_were_stored_in_regression():
    forward, backward = new_mock_db("fw")[COLLECTION], new_mock_db("bw")[COLLECTION]
    forward.insert_many(build_games())
    backward.insert_many(list(reversed(build_games())))
    assert _rows(forward) == _rows(backward)


def test_an_fbcyl_competition_exports_its_player_rows(collection):
    payload = export_collection(collection, COLLECTION)
    assert payload["league"] == "fbcyl" and payload["player_rows"] == _rows(collection) and payload["player_rows"]


def test_a_player_whose_uuid_key_is_missing_not_just_null_is_still_a_row_regression():
    """Real FBCYL data (the only competition of the local database): some players come without a ``uuid`` key at all, and Mongo leaves a missing field
    out of a ``$project`` instead of writing ``null``: reading ``row["uuid"]`` raised ``KeyError`` for the whole competition."""
    col = new_mock_db("missing_uuid")[COLLECTION]
    games = build_games()[:3]
    for team in games[0]["stats"]["teams"]:
        for player in team["players"]:
            del player["uuid"]
    for team in games[1]["stats"]["teams"]:
        del team["players"][0]["name"]
    col.insert_many(games)
    rows = _rows(col)
    assert rows and all(r["player_uuid"] for r in rows if r.get("player_name") is not None)
    assert {r["match_id"] for r in rows} == {g["_id"] for g in games}
