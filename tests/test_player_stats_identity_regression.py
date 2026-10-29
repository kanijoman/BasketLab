"""Bug #652: a player of a team written with two spellings (or under two names) came out in TWO rows with the games and totals split.

The season pipeline grouped by ``(player_id, player_name, team_name, team_id)``: a trailing space in the team name in some games, or a corrected spelling of
the player's name, made the same person two rows (35 of 4,403 player-team pairs of the 2025-26 and 2026-27 seasons in the real data). The identity is the
player id within the team id; the name and the team name shown are those of his LAST game.
"""
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from db_helpers import new_mock_db

sys.path.insert(0, str(Path(__file__).resolve().parent))

from local_vectors.games import build_games, for_mongomock  # noqa: E402
from src.database.repository import BasketballRepository  # noqa: E402


class _Mongomock:
    def __init__(self, col):
        self._col = col

    def aggregate(self, pipeline, **kwargs):
        return self._col.aggregate(for_mongomock(pipeline), **kwargs)


def _players(games):
    """What ``GET /players/{collection}`` answers (without the advanced figures)."""
    col = new_mock_db("identity")["LEAGUE"]
    col.insert_many(games)
    conn = MagicMock()
    conn.is_connected.return_value = True
    conn.get_collection.side_effect = lambda name: _Mongomock(col)
    return BasketballRepository(conn).get_player_stats("LEAGUE", None, None, None) or []


def _respell(games, team_id, spelling, from_game):
    """The team is written with another spelling from its ``from_game``-th game on (``TEAM.name`` and ``TEAM.TOTAL.name``, as FEB repeats it)."""
    seen = 0
    for game in games:
        for team in game["BOXSCORE"]["TEAM"]:
            if team["id"] != team_id:
                continue
            seen += 1
            if seen >= from_game:
                team["name"] = team["TOTAL"]["name"] = spelling
    return games


def _appearances(games, team_id):
    """``{player_id: [(play order, name, points)]}`` of the players who played for the team, straight from the box scores."""
    found = {}
    for order, game in enumerate(games):
        for team in game["BOXSCORE"]["TEAM"]:
            if team["id"] == team_id:
                for player in team["PLAYER"]:
                    if int(player.get("min", 0) or 0) > 0:
                        found.setdefault(player["id"], []).append((order, player["name"], int(player["pts"])))
    return found


def test_a_team_with_two_spellings_gives_one_row_per_player_with_all_his_games_regression():
    games = _respell(build_games(), "101", "ALPHA ", from_game=4)
    rows = [p for p in _players(games) if p["team_id"] == "101"]
    expected = _appearances(games, "101")
    assert sorted(p["player_id"] for p in rows) == sorted(expected)                         # one row per player, none split in two
    for row in rows:
        mine = expected[row["player_id"]]
        assert row["games_played"] == len(mine)
        assert row["total_pts"] == sum(pts for _o, _n, pts in mine)


def test_the_name_and_the_team_name_shown_are_those_of_his_last_game():
    games = _respell(build_games(), "101", "ALPHA ", from_game=4)
    rows = {p["player_id"]: p for p in _players(games) if p["team_id"] == "101"}
    spelled_when = {order: next(t["TOTAL"]["name"] for t in game["BOXSCORE"]["TEAM"] if t["id"] == "101") for order, game in enumerate(games)
                    if any(t["id"] == "101" for t in game["BOXSCORE"]["TEAM"])}
    for player_id, mine in _appearances(games, "101").items():
        last = max(mine)
        assert rows[player_id]["player_name"] == last[1]                                    # the name of his latest game
        assert rows[player_id]["team_name"] == spelled_when[last[0]]                        # and the spelling of the team in it


def test_a_player_whose_name_was_corrected_is_one_row_with_the_corrected_name_regression():
    """The fixture writes the first player of each team of the eighth game as ``J0. RENAMED`` in that game only."""
    games = build_games()
    renamed = {t["id"] for t in games[7]["BOXSCORE"]["TEAM"]}
    assert renamed and any(p["name"].endswith("RENAMED") for t in games[7]["BOXSCORE"]["TEAM"] for p in t["PLAYER"])
    rows = _players(games)
    for team_id in renamed:
        mine = [p for p in rows if p["team_id"] == team_id and p["player_id"] == f"{team_id}00"]
        expected = _appearances(games, team_id)[f"{team_id}00"]
        assert len(mine) == 1, team_id
        assert mine[0]["player_name"] == max(expected)[1] and mine[0]["games_played"] == len(expected)


def test_a_player_who_changed_team_is_one_row_per_team():
    """The identity is the player within the team: a transfer is two stints, not a merge."""
    games = build_games()
    moved = games[-1]["BOXSCORE"]["TEAM"][0]["PLAYER"][1]["id"]
    other_team = games[-1]["BOXSCORE"]["TEAM"][1]
    other_team["PLAYER"][0]["id"] = moved
    rows = [p for p in _players(games) if p["player_id"] == moved]
    assert len({p["team_id"] for p in rows}) == len(rows) == 2


def test_the_rows_do_not_depend_on_the_order_the_games_were_stored_in():
    games = _respell(build_games(), "101", "ALPHA ", from_game=4)
    key = lambda p: (p["team_id"], p["player_id"])  # noqa: E731
    forward = {key(p): (p["player_name"], p["team_name"], p["games_played"], p["total_pts"]) for p in _players(games)}
    backward = {key(p): (p["player_name"], p["team_name"], p["games_played"], p["total_pts"]) for p in _players(list(reversed(games)))}
    assert forward == backward


@pytest.mark.parametrize("filtered", [True, False])
def test_the_totals_of_a_league_do_not_change_when_the_identity_does(filtered):
    """Merging rows moves figures between rows, never creates or loses any: the points of all the players are the points in the box scores."""
    games = _respell(build_games(), "102", "BRAVO ", from_game=3)
    rows = _players(games)
    total = sum(int(p["pts"]) for g in games for t in g["BOXSCORE"]["TEAM"] for p in t["PLAYER"] if int(p.get("min", 0) or 0) > 0)
    assert sum(p["total_pts"] for p in rows) == total
