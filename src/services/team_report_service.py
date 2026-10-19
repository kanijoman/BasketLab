"""Gathers season data for the rule-based team report."""
from typing import Any, Dict, List, Optional

from src.report_engine import build_team_report
from src.report_engine.catalog import CATALOG

PBP_GROUP = "Origen de los puntos"
PBP_KEYS = tuple(stat.key for stat in CATALOG if stat.group == PBP_GROUP)
MIN_TEAMS_FOR_QUARTILES = 4


def _quantile(sorted_values: List[float], p: float) -> float:
    idx = (len(sorted_values) - 1) * p
    lo, hi = int(idx), min(int(idx) + 1, len(sorted_values) - 1)
    return sorted_values[lo] + (sorted_values[hi] - sorted_values[lo]) * (idx - lo)


def pbp_quartiles(rows: List[Dict[str, Any]]) -> Dict[str, Dict[str, float]]:
    """League quartiles of the play-by-play figures over the teams that have them (none below ``MIN_TEAMS_FOR_QUARTILES``)."""
    out: Dict[str, Dict[str, float]] = {}
    for key in PBP_KEYS:
        values = sorted(float(r[key]) for r in rows if isinstance(r.get(key), (int, float)))
        if len(values) >= MIN_TEAMS_FOR_QUARTILES:
            out[key] = {"min": values[0], "q1": _quantile(values, 0.25), "q2": _quantile(values, 0.5), "q3": _quantile(values, 0.75),
                        "max": values[-1], "count": len(values)}
    return out


class TeamNotFoundError(LookupError):
    """The team id is not part of the collection."""


class TeamReportService:
    def __init__(self, db, stats=None, zones=None, pbp=None):
        self._db = db
        self._zones = zones or self._load_zones
        self._pbp = pbp or self._load_pbp
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
        quartiles = dict(self._stats.get_quartiles(collection) or {})
        row = self._with_pbp(collection, team_id, row, quartiles)
        return build_team_report(
            name, row, quartiles, self._consistency(collection, name), mode,
            zones=self._zone_rows(collection, team_id),
        )

    def _with_pbp(self, collection: str, team_id: str, row: Dict[str, Any], quartiles: Dict[str, Any]) -> Dict[str, Any]:
        """Adds the team's play-by-play figures to its season row and their league quartiles to ``quartiles`` (optional enrichment)."""
        try:
            rows = self._pbp(collection) or []
        except Exception:  # noqa: BLE001 - never break the report for them
            return row
        quartiles.update(pbp_quartiles(rows))
        mine = next((r for r in rows if str(r.get("team_id")) == str(team_id)), None)
        return {**row, **{k: mine[k] for k in PBP_KEYS if mine and mine.get(k) is not None}} if mine else row

    def _load_pbp(self, collection: str) -> List[Dict[str, Any]]:
        from src.services.pbp_extended_stats_service import PBPExtendedStatsService

        return PBPExtendedStatsService(self._db).get_points_by_origin(collection)

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

    def _zone_rows(self, collection: str, team_id: str) -> List[Dict[str, Any]]:
        try:
            return self._zones(collection, team_id) or []
        except Exception:  # noqa: BLE001 - optional enrichment
            return []

    def _load_zones(self, collection: str, team_id: str) -> List[Dict[str, Any]]:
        """Team shot zones rated against the league average (FEB and FBCYL)."""
        from src.shotcharts.fbcyl_zones import stream_zone_counts_fbcyl
        from src.shotcharts.feb_zones import aggregate_zones, stream_zone_counts_feb
        from src.shotcharts.zone_rating import rate_zones
        from utils.collection_utils import is_fbcyl

        stream = stream_zone_counts_fbcyl if is_fbcyl(collection) else stream_zone_counts_feb
        coll = self._db.connection.get_collection(collection)
        team = aggregate_zones(stream(coll, team_id=team_id, player_filter=None))
        league = aggregate_zones(stream(coll, team_id=None, player_filter=None))
        return rate_zones(team, league)
