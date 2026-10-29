"""Rival scouting report service (issue #299): the engine's view of a team, the rule-based team report and the matchup.

``ScoutingRivalService(db).build(collection, team_id, own_team_id=None, progress=None)`` replays every game of the competition
to learn the season and the games of the chosen team "as live" (``live_prep.scouting_collect``), adds the rule-based team report
in rival mode (``TeamReportService``) and, given our team, the stat-by-stat matchup (``live_prep.scouting_compare``), and puts it
into words (``live_prep.scouting_report``). The team is a parameter: any team of any FEB collection. Heavy (CPU) and meant to run
as a background task; games are read one at a time (memory). The rule report is an enrichment: if it fails the scouting goes on.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Iterable, List, Optional

from src.live_prep.scouting_collect import ALL, LEAGUE, scout_team, scout_team_scopes
from src.live_prep.scouting_compare import compare_teams
from src.live_prep.scouting_report import build_scouting_report
from src.live_prep.scouting_scopes import cup_games, team_levels
from src.services.team_report_service import PBP_KEYS, TeamNotFoundError, TeamReportService
from src.utils.collection_utils import is_fbcyl

Progress = Callable[[int, int], None]


def _pbp_from_db(db: Any, collection: str) -> List[Dict[str, Any]]:
    from src.services.pbp_extended_stats_service import PBPExtendedStatsService

    return PBPExtendedStatsService(db).get_points_by_origin(collection)


def _games_from_mongo(db: Any, collection: str) -> Iterable[Dict[str, Any]]:
    from src.live_prep.eval_source import games_from_mongo

    return games_from_mongo(db, collection)


def _catalog_gender(db: Any, collection: str) -> str:
    from src.live_prep.competition_info import competition_infos
    from src.live_prep.publisher import load_config

    return competition_infos(db, [collection], load_config()["competitions"], [])[collection].get("gender") or ""


class ScoutingRivalService:
    def __init__(self, db: Any, stats: Any = None, report_service: Any = None, games: Callable[[Any, str], Iterable[Dict[str, Any]]] = _games_from_mongo,
                 pbp: Optional[Callable[[str], List[Dict[str, Any]]]] = None, gender_of: Optional[Callable[[str], str]] = None,
                 extra_games: Callable[[Any, str, str], Dict[str, Iterable[Dict[str, Any]]]] = cup_games,
                 levels_of: Callable[[Any, str], Dict[str, int]] = team_levels) -> None:
        self._db = db
        self._extra_games, self._levels_of = extra_games, levels_of
        self._pbp = pbp or (lambda collection: _pbp_from_db(db, collection))
        if stats is None:
            from src.services.team_stats_service import TeamStatsService

            stats = TeamStatsService(db)
        self._stats = stats
        self._report_service = report_service or TeamReportService(db, stats=stats)
        self._games = games
        self._gender_of = gender_of or (lambda collection: _catalog_gender(db, collection))

    def teams(self, collection: str) -> Dict[str, str]:
        """``{team id: name}`` of the teams of the competition (the ones that can be scouted)."""
        return self._names(collection)

    def _names(self, collection: str) -> Dict[str, str]:
        return {str(t["id"]): t.get("name") or str(t["id"]) for t in (self._stats.get_teams_with_ids(collection) or [])}

    def _total_games(self, collection: str) -> int:
        coll = self._db.repository.connection.get_collection(collection)
        return int(coll.count_documents({"PLAYBYPLAY.LINES": {"$exists": True, "$ne": None}}))

    def _rows(self, collection: str, *team_ids: str) -> Dict[str, Dict[str, Any]]:
        rows = (self._stats.load_season_data(collection) or {}).get("team_stats") or []
        wanted = {str(t) for t in team_ids}
        out = {str(r.get("team_id") or r.get("_id")): dict(r) for r in rows if str(r.get("team_id") or r.get("_id")) in wanted}
        try:        # the play-by-play figures of the season complete the rows (an enrichment: the matchup works without them)
            for row in self._pbp(collection) or []:
                if str(row.get("team_id")) in out:
                    out[str(row["team_id"])].update({k: row[k] for k in PBP_KEYS if row.get(k) is not None})
        except Exception:  # noqa: BLE001
            pass
        return out

    def build(self, collection: str, team_id: str, own_team_id: Optional[str] = None, progress: Optional[Progress] = None) -> Dict[str, Any]:
        """The scouting report (see ``scouting_report.build_scouting_report``) plus ``collection`` and ``own_team``."""
        team_id, own_team_id = str(team_id), str(own_team_id) if own_team_id else None
        if is_fbcyl(collection):
            raise ValueError("El scouting del rival solo está disponible para colecciones FEB por ahora")
        if own_team_id == team_id:
            raise ValueError("El equipo propio y el rival deben ser distintos")
        names = self._names(collection)
        for tid in filter(None, (team_id, own_team_id)):
            if tid not in names:
                raise TeamNotFoundError(tid)
        total = self._total_games(collection)
        data = scout_team(self._games(self._db, collection), team_id, collection,
                          progress=(lambda done: progress(done, max(total, done))) if progress else None)
        team_report, notices = self._team_report(collection, team_id)
        comparison = []
        if own_team_id:
            rows = self._rows(collection, team_id, own_team_id)
            comparison = compare_teams(rows.get(own_team_id), rows.get(team_id))
        report = build_scouting_report(data, team_report=team_report, comparison=comparison, gender=self._gender(collection))
        report["notices"] += notices
        report["collection"] = collection
        report["own_team"] = {"id": own_team_id, "name": names[own_team_id]} if own_team_id else None
        return report

    def build_scopes(self, collection: str, team_id: str, progress: Optional[Progress] = None) -> Dict[str, Dict[str, Any]]:
        """The scouting report by scope (issue #638): ``liga`` (the collection), ``copa`` (the team's games in the cups of the season) and ``todo`` (both),
        the last two only when the team has cup games. The engine replays every game once; the league context and the rule-based report are the league's.
        No matchup with our team here: it depends on a pair of teams and is computed from two profiles where it is read."""
        team_id = str(team_id)
        if is_fbcyl(collection):
            raise ValueError("El scouting del rival solo está disponible para colecciones FEB por ahora")
        if team_id not in self._names(collection):
            raise TeamNotFoundError(team_id)
        total = self._total_games(collection)
        data = scout_team_scopes(self._games(self._db, collection), team_id, collection,
                                 progress=(lambda done: progress(done, max(total, done))) if progress else None,
                                 extra=self._extra_games(self._db, collection, team_id), levels=self._levels_of(self._db, collection) or None)
        team_report, notices = self._team_report(collection, team_id)
        reports = {}
        for scope, scoped in data.items():
            of_the_league = scope in (LEAGUE, ALL)
            report = build_scouting_report(scoped, team_report=team_report if of_the_league else None, comparison=[], gender=self._gender(collection))
            report["notices"] += _scope_notices(scope, scoped) + (notices if of_the_league else [])
            report.update(scope=scope, collection=collection, own_team=None)
            reports[scope] = report
        return reports

    def _gender(self, collection: str) -> str:
        """``F``/``M`` of the competition in the catalog of the publisher; empty when it does not say (the report is then in the neutral)."""
        try:
            return self._gender_of(collection) or ""
        except Exception:  # noqa: BLE001 - an enrichment: the words fall back to the neutral
            return ""

    def _team_report(self, collection: str, team_id: str):
        try:
            return self._report_service.build(collection, team_id, "rival"), []
        except Exception:  # noqa: BLE001 - an enrichment: the scouting does not depend on it
            return None, ["No se pudo añadir el informe por reglas del equipo; el plan se basa solo en lo que ve el motor."]


def _scope_notices(scope: str, data: Dict[str, Any]) -> List[str]:
    """What a scope is made of and what in it is not like the rest: the cup games, and the games against a team of another category."""
    games = data["games"]
    cup, other = sum(1 for g in games if g.get("competition") not in (None, LEAGUE)), sum(1 for g in games if g.get("other_level"))
    notices = []
    if scope == ALL:
        notices.append(f"Agrupa la liga y la copa: {len(games) - cup} partidos de liga y {cup} de copa.")
    elif scope != LEAGUE:
        notices.append(f"Solo partidos de Copa: {len(games)} con jugada a jugada.")
    if other and scope != LEAGUE:
        notices.append(f"{other} de estos partidos son contra rivales de otra categoría: sus cifras no son comparables con las de la liga.")
    return notices
