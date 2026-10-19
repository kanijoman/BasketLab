"""Rival scouting report service (issue #299): the engine's view of a team, the rule-based team report and the matchup.

``ScoutingRivalService(db).build(collection, team_id, own_team_id=None, progress=None)`` replays every game of the competition
to learn the season and the games of the chosen team "as live" (``live_prep.scouting_collect``), adds the rule-based team report
in rival mode (``TeamReportService``) and, given our team, the stat-by-stat matchup (``live_prep.scouting_compare``), and puts it
into words (``live_prep.scouting_report``). The team is a parameter: any team of any FEB collection. Heavy (CPU) and meant to run
as a background task; games are read one at a time (memory). The rule report is an enrichment: if it fails the scouting goes on.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Iterable, List, Optional

from src.live_prep.scouting_collect import scout_team
from src.live_prep.scouting_compare import compare_teams
from src.live_prep.scouting_report import build_scouting_report
from src.services.team_report_service import PBP_KEYS, TeamNotFoundError, TeamReportService
from src.utils.collection_utils import is_fbcyl

Progress = Callable[[int, int], None]


def _pbp_from_db(db: Any, collection: str) -> List[Dict[str, Any]]:
    from src.services.pbp_extended_stats_service import PBPExtendedStatsService

    return PBPExtendedStatsService(db).get_points_by_origin(collection)


def _games_from_mongo(db: Any, collection: str) -> Iterable[Dict[str, Any]]:
    from src.live_prep.eval_source import games_from_mongo

    return games_from_mongo(db, collection)


class ScoutingRivalService:
    def __init__(self, db: Any, stats: Any = None, report_service: Any = None, games: Callable[[Any, str], Iterable[Dict[str, Any]]] = _games_from_mongo,
                 pbp: Optional[Callable[[str], List[Dict[str, Any]]]] = None) -> None:
        self._db = db
        self._pbp = pbp or (lambda collection: _pbp_from_db(db, collection))
        if stats is None:
            from src.services.team_stats_service import TeamStatsService

            stats = TeamStatsService(db)
        self._stats = stats
        self._report_service = report_service or TeamReportService(db, stats=stats)
        self._games = games

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
        report = build_scouting_report(data, team_report=team_report, comparison=comparison)
        report["notices"] += notices
        report["collection"] = collection
        report["own_team"] = {"id": own_team_id, "name": names[own_team_id]} if own_team_id else None
        return report

    def _team_report(self, collection: str, team_id: str):
        try:
            return self._report_service.build(collection, team_id, "rival"), []
        except Exception:  # noqa: BLE001 - an enrichment: the scouting does not depend on it
            return None, ["No se pudo añadir el informe por reglas del equipo; el plan se basa solo en lo que ve el motor."]
