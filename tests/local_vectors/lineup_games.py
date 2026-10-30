"""Games for the lineups ("Combinaciones", #686): the real sample games (FEB's and FBCYL's, with their play-by-play) played on different days, some of them cut after a period.

The play-by-play of the fixture leagues is minimal and gives no lineups; these are real, and cutting some games at the end of a period makes the lineups differ from game to game
(without it every game would repeat the same figures and a merge of games would prove nothing). ``Repo`` is the real lineup code over those games: the database is the only thing
replaced, the date filters and the last game are applied as MongoDB does (an instant per game, ``local_data.lineups_export.game_at``).
"""
import copy
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import Mock

from bson import json_util

from src.database.repository import BasketballRepository
from src.local_data.lineups_export import game_at

SAMPLES = Path(__file__).resolve().parent.parent.parent / "src" / "JSON_samples"
FEB = "L_F_-2_2025_2026_Liga_Regular_B"
FBCYL = "FBCYL_1ª_FASE-GRUPO_A-1_2026_"
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _day(day: str, kind: str) -> str:
    """The stored date of a game of ``YYYY-MM-DD`` (the format of each league; FBCYL's is the current one, with its comma and narrow no-break space)."""
    year, month, number = day.split("-")
    if kind == "feb":
        return f"{number}-{month}-{year} - 12:30"
    return f"{MONTHS[int(month) - 1]} {int(number)}, {year}, 6:00:00 PM"


def sample_games(kind: str, plan: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """One game per entry of ``plan`` (``{"day": "YYYY-MM-DD", "periods": 4}``): the sample cut after ``periods`` quarters, with its own ``_id`` and date. The dump is extended JSON."""
    doc = json_util.loads((SAMPLES / ("feb_game.json" if kind == "feb" else "fbcyl_game.json")).read_text(encoding="utf-8"))
    games = []
    for n, entry in enumerate(plan):
        game = copy.deepcopy(doc)
        game["_id"] = f"g{n}"
        limit = entry.get("periods", 4)
        if kind == "feb":
            game["HEADER"]["starttime"] = _day(entry["day"], kind)
            game["PLAYBYPLAY"]["LINES"] = [line for line in game["PLAYBYPLAY"]["LINES"] if int(line.get("quarter") or 0) <= limit]
        else:
            game["stats"]["time"] = _day(entry["day"], kind)
            game["moves"] = [move for move in game["moves"] if int(move.get("period") or 0) <= limit]
        games.append(game)
    return games


def team_of(kind: str, games: List[Dict[str, Any]], index: int = 0) -> str:
    teams = games[0]["HEADER"]["TEAM"] if kind == "feb" else games[0]["stats"]["teams"]
    return str(teams[index]["id"] if kind == "feb" else teams[index]["teamIdExtern"])


class Repo(BasketballRepository):
    """The lineup repository over given games."""

    def __init__(self, games: List[Dict[str, Any]], teams: List[Dict[str, str]], fbcyl: bool) -> None:
        super().__init__(Mock())
        self.games, self.teams, self.fbcyl = games, teams, fbcyl

    def get_teams_with_ids(self, name):
        return list(self.teams)

    def _at(self, game) -> Optional[str]:
        return game_at((game.get("stats") or {}).get("time") if self.fbcyl else (game.get("HEADER") or {}).get("starttime"), self.fbcyl)

    def get_games_for_team(self, name, team_id, only_with_playbyplay=False, projection=None, date_filter=None):
        games = copy.deepcopy(self.games)
        if date_filter is not None:
            cutoff = date_filter["$gte"].strftime("%Y-%m-%dT%H:%M:%S")
            games = [g for g in games if self._at(g) and self._at(g) >= cutoff]
        return games

    def get_last_game_for_team(self, name, team_id, only_with_playbyplay=False, projection=None):
        dated = [g for g in self.games if self._at(g)]
        return copy.deepcopy([max(dated, key=self._at)]) if dated else []

    def _bulk_load_player_names(self, name, ids, is_fbcyl):
        return {str(i): (f"Name {i}", None if is_fbcyl else f"https://img/{i}") for i in ids}
