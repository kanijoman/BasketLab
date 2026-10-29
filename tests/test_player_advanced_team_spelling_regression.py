"""Bug #647: the players of a team written with two spellings across games lost their advanced figures (USG%, ORtg...).

``_enrich_with_advanced_stats`` looked the team context up by NAME: the team rows carry the name of one game and the players the name of
theirs, so a trailing space in some games left those players with the defaults (``-`` in USG%, 0.0 ORtg/DRtg/Net, and other keys than the
normal path). The team id is stable: the context is looked up by it, and the defaults use the keys of the normal path.
"""
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from db_helpers import new_mock_db

sys.path.insert(0, str(Path(__file__).resolve().parent))

from local_vectors.games import build_games, for_mongomock  # noqa: E402
from src.database.repository import BasketballRepository  # noqa: E402
from src.services._team_id import with_team_id  # noqa: E402
from src.services.player_stats_service import PlayerStatsService  # noqa: E402

ADVANCED = ("usage_pct", "orating", "drating", "net_rtg", "ast_pct", "tov_pct_adv", "stl_pct", "blk_pct", "drb_pct", "orb_pct", "pie")


class _Mongomock:
    def __init__(self, col):
        self._col = col

    def aggregate(self, pipeline, **kwargs):
        return self._col.aggregate(for_mongomock(pipeline), **kwargs)


def _players(games):
    """What ``GET /players/{collection}`` answers for a league."""
    col = new_mock_db("spelling")["LEAGUE"]
    col.insert_many(games)
    conn = MagicMock()
    conn.is_connected.return_value = True
    conn.get_collection.side_effect = lambda name: _Mongomock(col)
    repo = BasketballRepository(conn)
    handler = type("Handler", (), {"get_team_stats": lambda self, c: with_team_id(repo.get_team_stats(c)),
                                   "get_opponent_stats": lambda self, c: with_team_id(repo.get_opponent_stats(c))})()
    players = repo.get_player_stats("LEAGUE", None, None, None) or []
    PlayerStatsService(handler)._enrich_with_advanced_stats("LEAGUE", players)
    return players


def _respell(games, team_id, spelling):
    """ALPHA is written with another spelling in every game but the first one it plays (the name the team rows keep)."""
    first = True
    for game in games:
        for team in game["BOXSCORE"]["TEAM"]:
            if team["id"] != team_id:
                continue
            if not first:
                team["name"] = team["TOTAL"]["name"] = spelling
            first = False
    return games


def test_a_team_with_two_spellings_keeps_the_advanced_figures_of_its_players_regression():
    """Every row of the team, under either spelling, is enriched with the context of the team id (the pipeline groups by name too, so a player may have two rows)."""
    rows = [p for p in _players(_respell(build_games(), "101", "ALPHA ")) if p["team_id"] == "101"]
    assert {p["team_name"] for p in rows} == {"ALPHA", "ALPHA "}
    played = [p for p in rows if p["total_minutes"] > 0]
    assert played
    for player in played:
        assert player["usage_pct"] > 0 and player["orating"] > 0, (player["player_id"], player["team_name"])


@pytest.mark.parametrize("key", ADVANCED)
def test_the_defaults_use_the_keys_of_the_normal_path(key):
    players = [{"player_id": "x", "team_name": "NO CONTEXT", "team_id": "999"}]
    handler = type("Handler", (), {"get_team_stats": lambda self, c: [], "get_opponent_stats": lambda self, c: []})()
    PlayerStatsService(handler)._enrich_with_advanced_stats("LEAGUE", players)
    assert key in players[0]
