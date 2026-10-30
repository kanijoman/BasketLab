"""Regenerate ``team_stats_feb.json``: the parity vectors of the local team tables (#327).

Python is the reference: the real season pipelines (team and rival) run on mongomock over the league of ``games.py``, once per filter, and the
file keeps the contract rows plus what the API answers. The web aggregates the rows on the device (``frontend/src/localdata``) and must give the
same figures. Run ``python tests/local_vectors/generate.py`` and review the diff after changing the pipelines or ``games.py``.
"""
import json
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

import mongomock

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src"), str(Path(__file__).resolve().parent)]

from fbcyl_games import build_games as build_fbcyl_games  # noqa: E402
from games import build_games, for_mongomock  # noqa: E402

from src.database.aggregation import AggregationPipelineBuilder as Pipelines  # noqa: E402
from src.database.aggregation.fbcyl_per_game_pipeline import build_fbcyl_season_rows_pipeline  # noqa: E402
from src.database.aggregation.fbcyl_pipeline import FBCYLPipelineBuilder  # noqa: E402
from src.database.repository import BasketballRepository  # noqa: E402
from src.services._team_id import with_team_id  # noqa: E402
from src.services.player_stats_service import PlayerStatsService  # noqa: E402
from src.services.team_comparison_service import TeamComparisonService  # noqa: E402
from src.utils.time_utils import end_of_day  # noqa: E402

OUT = Path(__file__).resolve().parent / "team_stats_feb.json"
PLAYERS_OUT = Path(__file__).resolve().parent / "players_feb.json"
FBCYL_OUT = Path(__file__).resolve().parent / "team_stats_fbcyl.json"
COMPARISON_OUT = Path(__file__).resolve().parent / "comparison_feb.json"
COMPARISON_FBCYL_OUT = Path(__file__).resolve().parent / "comparison_fbcyl.json"
FILTERS = [
    {"name": "all"},
    {"name": "home", "venue": "home"},
    {"name": "away", "venue": "away"},
    {"name": "won", "result": "won"},
    {"name": "lost", "result": "lost"},
    {"name": "home won", "venue": "home", "result": "won"},
    {"name": "from date", "from": "2025-11-01"},
    {"name": "to date (the games of the last day are in)", "to": "2025-11-13"},
    {"name": "date range", "from": "2025-10-20", "to": "2025-11-25"},
    {"name": "date range away lost", "from": "2025-10-20", "to": "2025-11-25", "venue": "away", "result": "lost"},
    {"name": "empty range", "from": "2030-01-01"},
]


def _played(doc: dict) -> datetime:
    return datetime.strptime(doc["HEADER"]["starttime"], "%d-%m-%Y - %H:%M")


def _run(games: list, filt: dict) -> dict:
    """What ``GET /teams/{collection}`` answers for these games and the venue / result of the filter (dates are applied by choosing the games)."""
    col = mongomock.MongoClient()["v"]["LEAGUE"]
    if games:
        col.insert_many(games)
    venue = {"home": True, "away": False}.get(filt.get("venue"))
    result = filt.get("result")
    return {"team_stats": with_team_id(list(col.aggregate(Pipelines.build_team_stats_pipeline(None, venue, result)))),
            "opponent_stats": with_team_id(list(col.aggregate(Pipelines.build_opponent_stats_pipeline(None, venue, result))))}


def _in_range(doc: dict, filt: dict) -> bool:
    """The API turns ``from`` into the start of its day and ``to`` into the END of its day (``end_of_day``, bug #643): a game played on the ``to`` day is in."""
    played = _played(doc)
    return ("from" not in filt or played >= datetime.fromisoformat(filt["from"])) and ("to" not in filt or played <= end_of_day(filt["to"]))


def _clean(rows: list) -> list:
    return [{k: v for k, v in row.items() if k != "_id" or isinstance(v, str)} for row in rows]


def build_vectors() -> dict:
    games = build_games()
    col = mongomock.MongoClient()["v"]["LEAGUE"]
    col.insert_many(build_games())
    rows = [{k: v for k, v in r.items() if k != "_id"} for r in col.aggregate(Pipelines.build_season_rows_pipeline())]
    cases = []
    for filt in FILTERS:
        out = _run([g for g in build_games() if _in_range(g, filt)], filt)
        cases.append({"filter": {k: v for k, v in filt.items() if k != "name"}, "name": filt["name"], "team_stats": _clean(out["team_stats"]),
                      "opponent_stats": _clean(out["opponent_stats"])})
    return {"games": len(games), "rows": rows, "cases": cases}


PLAYER_FILTERS = FILTERS + [
    {"name": "one team", "team": "BRAVO"},
    {"name": "one team away won", "team": "CHARLIE", "venue": "away", "result": "won"},
    {"name": "unknown team", "team": "NOBODY"},
]


class _Mongomock:
    """A collection whose pipelines are run without ``$dateFromString`` (see ``for_mongomock``)."""

    def __init__(self, col):
        self._col = col

    def aggregate(self, pipeline, **kwargs):
        return self._col.aggregate(for_mongomock(pipeline), **kwargs)


def _repository(games: list) -> BasketballRepository:
    col = mongomock.MongoClient()["v"]["LEAGUE"]
    if games:
        col.insert_many(games)
    conn = MagicMock()
    conn.is_connected.return_value = True
    conn.get_collection.side_effect = lambda name: _Mongomock(col)
    return BasketballRepository(conn)


def _players(games: list, filt: dict) -> list:
    """What ``GET /players/{collection}`` answers: the players of the games in range, their advanced figures from the season-wide team context."""
    venue = {"home": True, "away": False}.get(filt.get("venue"))
    players = _repository(games).get_player_stats("LEAGUE", None, venue, filt.get("result"), team_filter=filt.get("team")) or []
    if players:
        everything = _repository(build_games())
        handler = type("Handler", (), {"get_team_stats": everything.get_team_stats, "get_opponent_stats": everything.get_opponent_stats})()
        PlayerStatsService(handler)._enrich_with_advanced_stats("LEAGUE", players)
    return players


def build_player_vectors() -> dict:
    col = mongomock.MongoClient()["v"]["LEAGUE"]
    col.insert_many(build_games())
    rows = list(_Mongomock(col).aggregate(Pipelines.build_season_player_rows_pipeline()))
    cases = [{"filter": {k: v for k, v in f.items() if k != "name"}, "name": f["name"],
              "players": _players([g for g in build_games() if _in_range(g, f)], f)} for f in PLAYER_FILTERS]
    return {"rows": rows, "cases": cases}


def _fbcyl_day(doc: dict) -> datetime:
    """FBCYL's date is a day: ``Oct 4, 2025 7:00:00 PM`` -> 2025-10-04 (the pipeline keeps only month, day and year)."""
    return datetime.strptime(" ".join(doc["stats"]["time"].split(" ")[:3]), "%b %d, %Y")


def _fbcyl_in_range(doc: dict, filt: dict) -> bool:
    """Both bounds are inclusive days in FBCYL (unlike FEB's midnight bound, issue #643)."""
    day = _fbcyl_day(doc)
    return ("from" not in filt or day >= datetime.fromisoformat(filt["from"])) and ("to" not in filt or day <= datetime.fromisoformat(filt["to"]))


def build_fbcyl_vectors() -> dict:
    """The FBCYL team tables: ``team_stats`` and ``opponent_stats`` (the rivals' figures, since #642; it used to repeat the team's own table)."""
    col = mongomock.MongoClient()["v"]["FBCYL_LEAGUE"]
    col.insert_many(build_fbcyl_games())
    rows = list(col.aggregate(build_fbcyl_season_rows_pipeline()))
    cases = []
    for filt in FILTERS:
        subset = mongomock.MongoClient()["v"]["FBCYL_LEAGUE"]
        games = [g for g in build_fbcyl_games() if _fbcyl_in_range(g, filt)]
        if games:
            subset.insert_many(games)
        venue = {"home": True, "away": False}.get(filt.get("venue"))
        stats = list(subset.aggregate(FBCYLPipelineBuilder.build_team_stats_pipeline(None, venue, filt.get("result"))))
        rivals = list(subset.aggregate(FBCYLPipelineBuilder.build_opponent_stats_pipeline(None, venue, filt.get("result"))))
        cases.append({"filter": {k: v for k, v in filt.items() if k != "name"}, "name": filt["name"],
                      "team_stats": [{k: v for k, v in row.items() if k != "_id"} for row in stats],
                      "opponent_stats": [{k: v for k, v in row.items() if k != "_id"} for row in rivals]})
    return {"rows": rows, "cases": cases}


# The comparisons of the web (#607, #670): both groups of the season through ``TeamComparisonService`` over a handler that answers with the pipelines of each league.
COMPARISONS = [
    {"name": "home vs away", "by": "venue"},
    {"name": "won vs lost", "by": "result"},
    {"name": "stretch from a date", "by": "period", "from": "2025-11-01"},
    {"name": "stretch up to a date (the games of the last day are in)", "by": "period", "to": "2025-11-13"},
    {"name": "stretch between two dates", "by": "period", "from": "2025-10-20", "to": "2025-11-25"},
    {"name": "stretch that holds no game", "by": "period", "from": "2030-01-01"},
]


def _in_stretch(played: datetime, stretch: dict) -> bool:
    """What Mongo does with a stretch ``{"$gte": a, "$lte": b}`` and with its complement ``{"$not": stretch}`` (the rest of the season)."""
    if "$not" in stretch:
        return not _in_stretch(played, stretch["$not"])
    return ("$gte" not in stretch or played >= stretch["$gte"]) and ("$lte" not in stretch or played <= stretch["$lte"])


class _SeasonHandler:
    """``get_team_stats`` / ``get_opponent_stats`` of a league for the filters the comparison asks: the games are chosen by date and the pipelines run on them."""

    def __init__(self, games: list, played, run) -> None:
        self._games, self._played, self._run = games, played, run

    def _tables(self, date_filter, venue, result) -> dict:
        chosen = [g for g in self._games if date_filter is None or _in_stretch(self._played(g), date_filter)]
        return self._run(chosen, {"venue": {True: "home", False: "away"}.get(venue), "result": result})

    def get_team_stats(self, collection, date_filter=None, venue_filter=None, result_filter=None):
        return self._tables(date_filter, venue_filter, result_filter)["team_stats"]

    def get_opponent_stats(self, collection, date_filter=None, venue_filter=None, result_filter=None):
        return self._tables(date_filter, venue_filter, result_filter)["opponent_stats"]


def _comparisons(handler: _SeasonHandler) -> list:
    cases = []
    for case in COMPARISONS:
        date_from = datetime.fromisoformat(case["from"]) if "from" in case else None
        date_to = end_of_day(case["to"]) if "to" in case else None             # as the router turns the dates
        expected = TeamComparisonService(handler).compare("LEAGUE", case["by"], date_from, date_to)
        cases.append({"name": case["name"], "by": case["by"], "range": {k: case[k] for k in ("from", "to") if k in case}, "expected": json.loads(json.dumps(expected))})
    return cases


def build_comparison_vectors() -> dict:
    return {"cases": _comparisons(_SeasonHandler(build_games(), _played, _run))}


def _fbcyl_run(games: list, filt: dict) -> dict:
    subset = mongomock.MongoClient()["v"]["FBCYL_LEAGUE"]
    if games:
        subset.insert_many(games)
    venue = {"home": True, "away": False}.get(filt.get("venue"))
    return {"team_stats": with_team_id(list(subset.aggregate(FBCYLPipelineBuilder.build_team_stats_pipeline(None, venue, filt.get("result"))))),
            "opponent_stats": with_team_id(list(subset.aggregate(FBCYLPipelineBuilder.build_opponent_stats_pipeline(None, venue, filt.get("result")))))}


def build_fbcyl_comparison_vectors() -> dict:
    """FBCYL keeps only the day of a game, so a stretch is a range of whole days (both ends inclusive) and so is the rest of the season."""
    return {"cases": _comparisons(_SeasonHandler(build_fbcyl_games(), _fbcyl_day, _fbcyl_run))}


def _write(path: Path, vectors: dict) -> None:
    path.write_text(json.dumps(vectors, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    _write(OUT, build_vectors())
    _write(PLAYERS_OUT, build_player_vectors())
    _write(FBCYL_OUT, build_fbcyl_vectors())
    _write(COMPARISON_OUT, build_comparison_vectors())
    _write(COMPARISON_FBCYL_OUT, build_fbcyl_comparison_vectors())
    print("wrote", OUT, PLAYERS_OUT, FBCYL_OUT, COMPARISON_OUT, COMPARISON_FBCYL_OUT)
    import generate_fbcyl_players                                    # imports this module: only here, once it is loaded

    generate_fbcyl_players.main()


if __name__ == "__main__":
    main()
