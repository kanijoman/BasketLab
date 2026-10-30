"""Regenerate ``team_stats_feb.json``: the parity vectors of the local team tables (#327).

Python is the reference: the real season pipelines (team and rival) run on mongomock over the league of ``games.py``, once per filter, and the
file keeps the contract rows plus what the API answers. The web aggregates the rows on the device (``frontend/src/localdata``) and must give the
same figures. Run ``python tests/local_vectors/generate.py`` and review the diff after changing the pipelines or ``games.py``.
"""
import copy
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
from src.services.collection_service import CollectionService  # noqa: E402
from src.services.derived_coverage_service import DerivedCoverageService  # noqa: E402
from src.services.evolution_service import EVOLUTION_STAT_KEYS, EvolutionService  # noqa: E402
from src.services.multi_phase_service import MultiPhaseService  # noqa: E402
from src.services.pbp_extended_stats_service import PBPExtendedStatsService  # noqa: E402
from src.services.pbp_situation_stats_service import PBPSituationStatsService  # noqa: E402
from src.services.team_comparison_service import TeamComparisonService  # noqa: E402
from src.utils.time_utils import end_of_day, fbcyl_game_day  # noqa: E402

OUT = Path(__file__).resolve().parent / "team_stats_feb.json"
PLAYERS_OUT = Path(__file__).resolve().parent / "players_feb.json"
FBCYL_OUT = Path(__file__).resolve().parent / "team_stats_fbcyl.json"
COMPARISON_OUT = Path(__file__).resolve().parent / "comparison_feb.json"
COMPARISON_FBCYL_OUT = Path(__file__).resolve().parent / "comparison_fbcyl.json"
MULTI_OUT = Path(__file__).resolve().parent / "multi_phase.json"
EVOLUTION_OUT = Path(__file__).resolve().parent / "evolution_feb.json"
PBP_OUT = Path(__file__).resolve().parent / "pbp_feb.json"
PBP_FBCYL_OUT = Path(__file__).resolve().parent / "pbp_fbcyl.json"
SHOTS_OUT = Path(__file__).resolve().parent / "shots_feb.json"
SHOTS_FBCYL_OUT = Path(__file__).resolve().parent / "shots_fbcyl.json"
EVOLUTION_FBCYL_OUT = Path(__file__).resolve().parent / "evolution_fbcyl.json"
LINEUPS_OUT = Path(__file__).resolve().parent / "lineups_feb.json"
LINEUPS_FBCYL_OUT = Path(__file__).resolve().parent / "lineups_fbcyl.json"
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
    """FBCYL's date is a day: ``Oct 4, 2025, 7:00:00 PM`` (or the older writing without the comma) -> 2025-10-04 (the pipeline keeps only month, day and year)."""
    return datetime.strptime(fbcyl_game_day(doc["stats"]["time"]), "%Y-%m-%d")


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


# Multifase (#671): ``MultiPhaseService`` merges the tables of several collections. The two "phases" are the home games and the away games of each league's stored vectors
# (every team is in both, as in a league with a regular season and a play-off); the reference tables are the stored ones (FBCYL's players came from a real mongod).
SIBLING_NAMES = [
    "L_F_-2_2025_2026_Liga_Regular_A", "L_F_-2_2025_2026_Liga_Regular_B", "L_F_-2_2025_2026_Play-offs", "L_F_-2_2024_2025_Liga_Regular_A",
    "L_F_-2_2025_2026_ELIMINATORIAS", "PRIMERA_FEB_2025_2026_Liga_Regular_Unico", "PRIMERA_FEB_2025_2026_Play-offs", "3FEB_2025_2026_Liga_Regular_A", "3FEB_2025_2026_FASE_ASCENSO",
    "FBCYL_1ª_FASE-GRUPO_A-1_2026_", "FBCYL_1ª_FASE-GRUPO_B-1_2026_", "FBCYL_2ª_FASE-GRUPO_A-1_2026_", "FBCYL_1A_2025", "sin_anio",
]


def _stored(name: str) -> dict:
    return json.loads((Path(__file__).resolve().parent / name).read_text(encoding="utf-8"))


class _PhasesHandler:
    """What ``MultiPhaseService`` asks of its database: the table of each collection (a copy: the service renames fields in place)."""

    def __init__(self, teams: dict, players: dict) -> None:
        self._teams, self._players = teams, players

    def get_team_stats(self, collection):
        return json.loads(json.dumps(self._teams[collection]))

    def get_player_stats(self, collection):
        return json.loads(json.dumps(self._players[collection]))


def _multi(teams_file: str, players_file: str, is_fbcyl: bool) -> dict:
    teams = {c["name"]: c["team_stats"] for c in _stored(teams_file)["cases"]}
    players = {c["name"]: c["players"] for c in _stored(players_file)["cases"]}
    phases = {"PHASE_HOME": "home", "PHASE_AWAY": "away"}
    handler = _PhasesHandler({k: teams[v] for k, v in phases.items()}, {k: players[v] for k, v in phases.items()})
    service = MultiPhaseService(handler, list(phases))
    return {"phases": {k: {"team_stats": teams[v], "players": players[v]} for k, v in phases.items()},
            "team_stats": json.loads(json.dumps(service.get_combined_team_stats(is_fbcyl))), "players": json.loads(json.dumps(service.get_combined_player_stats(is_fbcyl)))}


def build_multi_vectors() -> dict:
    collections = CollectionService(MagicMock())
    siblings = {name: collections.get_sibling_collections(name, SIBLING_NAMES) for name in SIBLING_NAMES + ["L_F_-2_2025_2026_Otra_Fase_C"]}
    return {"siblings": {"names": SIBLING_NAMES, "expected": siblings},
            "feb": _multi("team_stats_feb.json", "players_feb.json", False), "fbcyl": _multi("team_stats_fbcyl.json", "players_fbcyl.json", True)}


# Evolución (#672): ``EvolutionService.get_competition_evolution`` over the real per-game pipelines of each league (FEB's and FBCYL's), for every stat and two windows.
EVOLUTION_WINDOWS = (3, 5)


def _evolution_pipeline(pipeline: list) -> list:
    """The pipeline for mongomock: the date is stored on the documents (``parsedDate``) instead of parsed by ``$dateFromString``, and ``$dateToString`` has no ``onNull``
    (every game of the fixtures has a date)."""
    cleaned = []
    for stage in for_mongomock(pipeline):
        if stage == {"$addFields": {}} or set(stage.get("$addFields", {"": 0})) <= {"timeParts", "parsedDate"}:
            continue                                                     # the date stages: the date is stored on the documents instead
        stage = copy.deepcopy(stage)
        project = stage.get("$project")
        if project and "game_date" in project:
            project["game_date"]["$dateToString"].pop("onNull", None)
        cleaned.append(stage)
    return cleaned


def _evolution_vectors(games: list, collection: str, team_ids) -> dict:
    col = mongomock.MongoClient()["v"][collection]
    col.insert_many(games)

    class _Col:
        def aggregate(self, pipeline, **kwargs):
            return col.aggregate(_evolution_pipeline(pipeline), **kwargs)

    class _Handler:
        class connection:  # noqa: N801 - the service reads ``db.connection.get_collection``
            @staticmethod
            def get_collection(name):
                return _Col()

        @staticmethod
        def get_teams_with_ids(name):
            return [{"id": str(team_id)} for team_id in team_ids(games)]

    class _Cached(EvolutionService):
        """The service as it is, but the per-game rows of a team are read once (every case asks for the same ones: only the stat and the window change)."""

        def __init__(self, handler) -> None:
            super().__init__(handler)
            self._rows = {}

        def _evolution_feb(self, coll, team_id):
            return self._rows.setdefault(("feb", team_id), super()._evolution_feb(coll, team_id))

        def _evolution_fbcyl(self, coll, team_id):
            return self._rows.setdefault(("fbcyl", team_id), super()._evolution_fbcyl(coll, team_id))

    service = _Cached(_Handler())
    return {"cases": [{"stat": stat, "window": window, "points": service.get_competition_evolution(collection, stat=stat, rolling_window=window)}
                      for stat in sorted(EVOLUTION_STAT_KEYS) for window in EVOLUTION_WINDOWS]}


def build_evolution_vectors() -> dict:
    games = build_games()
    for game in games:
        game["parsedDate"] = _played(game)
    return _evolution_vectors(games, "LEAGUE", lambda docs: sorted({t["id"] for g in docs for t in g["HEADER"]["TEAM"]}))


def build_fbcyl_evolution_vectors() -> dict:
    games = build_fbcyl_games()
    for game in games:
        game["parsedDate"] = _fbcyl_day(game)
    return _evolution_vectors(games, "FBCYL_LEAGUE", lambda docs: sorted({t["teamIdExtern"] for g in docs for t in g["stats"]["teams"]}))


# Análisis PBP (#676): the five pbp tables of the web, as the real services answer them over the ``DERIVED`` of the fixture games, and the ``derived`` payload the exporter
# makes of the same games (what the browser sums).
def _pbp_vectors(games: list, collection: str) -> dict:
    from unittest.mock import MagicMock

    from src.local_data.export import export_derived
    from src.services import pbp_extended_stats_service, pbp_situation_stats_service

    col = mongomock.MongoClient()["v"][collection]
    col.insert_many(games)
    pbp_extended_stats_service.clear_cache()
    pbp_situation_stats_service.clear_cache()
    handler = MagicMock()
    handler.repository.connection.get_collection.side_effect = lambda name: col
    extended, situations = PBPExtendedStatsService(handler), PBPSituationStatsService(handler)
    expected = {"origin": extended.get_points_by_origin(collection), "periods": extended.get_by_period(collection),
                "situations": situations.get_situations(collection), "timeouts": situations.get_timeout_effects(collection),
                "coverage": DerivedCoverageService(handler).get(collection)}
    return {"derived": json.loads(json.dumps(export_derived(col, collection), default=str)), "expected": json.loads(json.dumps(expected, default=str))}


def build_pbp_vectors() -> dict:
    return _pbp_vectors(build_games(), "L_F_-2_2025_2026_Liga_Regular_B")


def build_fbcyl_pbp_vectors() -> dict:
    return _pbp_vectors(build_fbcyl_games(), "FBCYL_1ª_FASE-GRUPO_A-1_2026_")


# Tiros (#685): the shots published for a competition and what the real endpoints answer for them (``get_shot_zones``, with and without the league, and ``get_shot_raw``).
def _shots_vectors(games: list, collection: str) -> dict:
    from unittest.mock import MagicMock

    from src.api.routers.shots import get_shot_raw, get_shot_zones
    from src.local_data.shots_export import export_shots

    col = mongomock.MongoClient()["v"][collection]
    col.insert_many(games)
    db = MagicMock()
    db.connection.get_collection.side_effect = lambda name: col
    payload = json.loads(json.dumps(export_shots(col, collection), default=str))
    rows = [dict(zip(payload["columns"], r)) for r in payload["shots"]]
    teams = sorted({r["team_id"] for r in rows})
    players = [next(r["player_id"] for r in rows if r["team_id"] == t and r["player_id"]) for t in teams]
    filters = [{}] + [{"team_id": t} for t in teams] + [{"player": p} for p in players] + [{"team_id": teams[0], "player": players[0]}, {"team_id": "NOBODY"}]
    cases = []
    for flt in filters:
        for compare in (None, "league"):
            zones = get_shot_zones(collection, flt.get("team_id"), flt.get("player"), compare, db)
            cases.append({"filter": flt, "compare": compare, "zones": json.loads(json.dumps(zones))})
    raw = [{"filter": flt, "limit": limit, "shots": json.loads(json.dumps(get_shot_raw(collection, flt.get("team_id"), flt.get("player"), limit, db)))}
           for flt in filters[:3] for limit in (5000, 7)]
    return {"payload": payload, "zones": cases, "raw": raw}


def build_shots_vectors() -> dict:
    return _shots_vectors(build_games(), "L_F_-2_2025_2026_Liga_Regular_B")


def build_fbcyl_shots_vectors() -> dict:
    return _shots_vectors(build_fbcyl_games(), "FBCYL_1ª_FASE-GRUPO_A-1_2026_")


def _write(path: Path, vectors: dict, compact: bool = False) -> None:
    """``compact`` for the files of tables of numbers, whose every value on a line of its own would weigh several times more."""
    text = json.dumps(vectors, ensure_ascii=False, separators=(",", ":"), sort_keys=True) if compact else json.dumps(vectors, ensure_ascii=False, indent=1, sort_keys=True)
    path.write_text(text + "\n", encoding="utf-8")


def main() -> None:
    _write(OUT, build_vectors())
    _write(PLAYERS_OUT, build_player_vectors())
    _write(FBCYL_OUT, build_fbcyl_vectors())
    _write(COMPARISON_OUT, build_comparison_vectors())
    _write(COMPARISON_FBCYL_OUT, build_fbcyl_comparison_vectors())
    _write(MULTI_OUT, build_multi_vectors())
    _write(EVOLUTION_OUT, build_evolution_vectors())
    _write(EVOLUTION_FBCYL_OUT, build_fbcyl_evolution_vectors())
    _write(PBP_OUT, build_pbp_vectors())
    _write(PBP_FBCYL_OUT, build_fbcyl_pbp_vectors())
    _write(SHOTS_OUT, build_shots_vectors())
    _write(SHOTS_FBCYL_OUT, build_fbcyl_shots_vectors())
    from lineup_vectors import build as build_lineups

    _write(LINEUPS_OUT, build_lineups("feb"), compact=True)
    _write(LINEUPS_FBCYL_OUT, build_lineups("fbcyl"), compact=True)
    print("wrote", OUT, PLAYERS_OUT, FBCYL_OUT, COMPARISON_OUT, COMPARISON_FBCYL_OUT, MULTI_OUT, EVOLUTION_OUT, EVOLUTION_FBCYL_OUT, PBP_OUT, PBP_FBCYL_OUT, SHOTS_OUT, SHOTS_FBCYL_OUT)
    import generate_fbcyl_players                                    # imports this module: only here, once it is loaded

    generate_fbcyl_players.main()


if __name__ == "__main__":
    main()
