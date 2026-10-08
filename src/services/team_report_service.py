"""Gathers season data for the rule-based team report."""
from typing import Any, Dict, Optional

from src.report_engine import build_team_report


class TeamNotFoundError(LookupError):
    """The team id is not part of the collection."""


class TeamReportService:
    def __init__(self, db, stats=None):
        if stats is None:
            from src.services.team_stats_service import TeamStatsService

            stats = TeamStatsService(db)
        self._stats = stats

    def build(self, collection: str, team_id: str, mode: str = "own") -> Dict[str, Any]:
        rows = (self._stats.load_season_data(collection) or {}).get("team_stats") or []
        row = next((r for r in rows if str(r.get("team_id") or r.get("_id")) == str(team_id)), None)
        if row is None:
            raise TeamNotFoundError(team_id)
        name = self._team_name(collection, team_id, row)
        quartiles = self._stats.get_quartiles(collection) or {}
        return build_team_report(name, row, quartiles, self._consistency(collection, name), mode)

    def _team_name(self, collection: str, team_id: str, row: Dict[str, Any]) -> str:
        for t in self._stats.get_teams_with_ids(collection) or []:
            if str(t.get("id")) == str(team_id):
                return t.get("name") or str(team_id)
        return str(row.get("team_name") or row.get("name") or team_id)

    def _consistency(self, collection: str, team_name: str) -> Optional[Dict[str, Any]]:
        try:
            raw = self._stats.get_consistency(collection) or {}
        except Exception:  # noqa: BLE001 - optional enrichment, never break the report
            return None
        return (raw.get("own") or {}).get(team_name)
