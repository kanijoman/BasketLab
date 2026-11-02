"""The vectors of the quartiles of the players on the device (#707): what the real ``PlayerStatsService.get_quartiles`` answers over a player table, the reference of
``frontend/src/localdata/playerQuartiles.test.ts``.

Only the load of the table is replaced (the table is the one the vectors of the player tables already prove equal to the API's); the filter of games, the minimum of values and
``np.percentile`` are the service's. Besides the sample leagues, a table of awkward floats checks the interpolation where a quantile falls between two values at more than half way
(numpy interpolates from the near end, and the last digit shows it).
"""
import json
import random
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import MagicMock

from src.services.player_stats_service import PlayerStatsService

HERE = Path(__file__).resolve().parent
FIELDS = ("points_per_game", "rebounds_per_game", "offensive_rebounds_per_game", "defensive_rebounds_per_game", "assists_per_game", "steals_per_game", "turnovers_per_game",
          "blocks_per_game", "fouls_per_game", "valoracion_per_game", "pllss_per_game", "minutes_per_game", "fg1_percentage", "fg2_percentage", "fg3_percentage")


def _quartiles(players: List[Dict[str, Any]]) -> Dict[str, Dict[str, float]]:
    service = PlayerStatsService(MagicMock())
    service.load_season_data = lambda *_a, **_kw: players          # type: ignore[method-assign]
    return service.get_quartiles("X")


def _awkward() -> List[Dict[str, Any]]:
    """23 players with floats with many decimals, some with fewer than three games (out), some with a missing figure; ``fg3_percentage`` has only three values (no quartiles)."""
    rng = random.Random(707)
    players = []
    for i in range(23):
        row: Dict[str, Any] = {"games_played": 2 if i % 7 == 6 else rng.randint(3, 30)}
        for field in FIELDS:
            row[field] = None if (i + len(field)) % 11 == 0 else rng.uniform(0, 40) / rng.choice((1, 3, 7))
        if i >= 3:
            row["fg3_percentage"] = None
        players.append(row)
    return players


def build() -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for kind, name in (("feb", "players_feb.json"), ("fbcyl", "players_fbcyl.json")):
        players = json.loads((HERE / name).read_text(encoding="utf-8"))["cases"][0]["players"]      # the whole season, no filter
        out[kind] = {"players": players, "quartiles": _quartiles(players)}
    awkward = _awkward()
    out["awkward"] = {"players": awkward, "quartiles": _quartiles(awkward)}
    return out
