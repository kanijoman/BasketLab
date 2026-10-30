"""The vectors of Combinaciones on the device (#686): the published per-game counters of a team and what the real ``LineupService`` answers over the same games for every
combination of size, statistic, period, minimums and last game, the reference of ``frontend/src/localdata/lineups.test.ts``.

The players of a lineup have no order in the API (a ``frozenset``), so each row is written with its players by id, and the ties of a sort have none either: the browser
compares the rows without order.
"""
import json
from datetime import datetime, timedelta
from itertools import groupby
from typing import Any, Dict, List

from lineup_games import FBCYL, FEB, Repo, sample_games, team_of

from src.local_data.lineups_export import export_lineups
from src.services.lineup_service import LineupService

NOW = datetime(2025, 11, 12, 12, 0, 0)
# cut after fewer periods each time: the lineups of the last quarter are of the first game alone, those of the first quarter of all five
PLAN = [{"day": "2025-10-05", "periods": 4}, {"day": "2025-10-19", "periods": 3}, {"day": "2025-11-01", "periods": 2},
        {"day": "2025-11-04", "periods": 1}, {"day": "2025-11-09", "periods": 1}]
FREE = {"min_minutes": 0, "min_games": 0}
# ``(configuration, sizes)``: every size with the defaults and with no minimums; the rest on the sizes that show them (a file of every size of every case would weigh megabytes)
CONFIGS = [
    ({"name": "defaults (15 minutes, 5 games)"}, (3, 5)), ({"name": "no minimums", **FREE}, (2, 3, 4, 5)),
    ({"name": "two games", "min_minutes": 0, "min_games": 2}, (4,)), ({"name": "game log", "include_game_log": True, **FREE}, (5,)),
    ({"name": "last 7 days", "period": 7, **FREE}, (5,)), ({"name": "last 30 days", "period": 30, "min_minutes": 0, "min_games": 3}, (4,)),
    ({"name": "last 200 days", "period": 200, **FREE}, (5,)), ({"name": "the last game", "last_game": True, **FREE}, (3,)),
    ({"name": "by DRtg (lower is better)", "stat": "drtg", **FREE}, (5,)), ({"name": "by TOV% (lower is better)", "stat": "tov_pct", **FREE}, (5,)),
    ({"name": "by assists", "stat": "ast", **FREE}, (4,)), ({"name": "by eFG%", "stat": "efg_pct", **FREE}, (5,)),
    ({"name": "nothing in the period", "period": 1, **FREE}, (5,)),
    ({"name": "the minimum of games is capped to the games of the period", "period": 7, "min_minutes": 0}, (5,)),
]


def _by_id(row: Dict[str, Any]) -> Dict[str, Any]:
    """The row with its players sorted by id (names and photos follow): the order of a ``frozenset`` is not reproducible."""
    order = sorted(range(len(row["player_ids"])), key=lambda i: str(row["player_ids"][i]))
    for key in ("player_ids", "player_names", "players", "player_photo_urls"):
        if key in row:
            row[key] = [row[key][i] for i in order]
    return row


def tied_by_id(rows: List[Dict[str, Any]], stat: str) -> List[Dict[str, Any]]:
    """The rows with each run of equal ``stat`` ordered by player ids: the order of ties follows the iteration of a ``frozenset`` (it changes from one run to the next); the browser
    answers the same rows and its test puts its ties in this order before comparing."""
    out: List[Dict[str, Any]] = []
    for _, run in groupby(rows, key=lambda row: row.get(stat) or 0):
        out += sorted(run, key=lambda row: [str(i) for i in row["player_ids"]])
    return out


def _answer(repo: Repo, name: str, team: str, size: int, config: Dict[str, Any]) -> List[Dict[str, Any]]:
    period = config.get("period", 0)
    rows = LineupService(repo).get_lineup_analysis(
        name, team, "Team A", size, stat=config.get("stat", "net_rating"), date_filter={"$gte": NOW - timedelta(days=period)} if period else None,
        include_game_log=config.get("include_game_log", False), min_minutes=config.get("min_minutes", 15), min_games=config.get("min_games", 5),
        last_game=config.get("last_game", False))
    return tied_by_id([_by_id(row) for row in json.loads(json.dumps(rows, default=str))], config.get("stat", "net_rating"))


def build(kind: str) -> Dict[str, Any]:
    name = FEB if kind == "feb" else FBCYL
    games = sample_games(kind, PLAN)
    team = team_of(kind, games)
    repo = Repo(games, [{"id": team, "name": "Team A"}], kind == "fbcyl")
    published = json.loads(json.dumps(export_lineups(repo, name), default=str))
    cases = [{"config": config, "size": size, "rows": _answer(repo, name, team, size, config)} for config, sizes in CONFIGS for size in sizes]
    return {"now": NOW.strftime("%Y-%m-%dT%H:%M:%S"), "team": team, "published": published, "cases": cases}
