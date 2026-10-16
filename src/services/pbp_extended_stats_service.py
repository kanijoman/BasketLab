"""Season points by origin, bench and paint per team (#352), summed from the ``DERIVED`` field of each match.

Per team: points per game after turnovers (steals included), after steals, second chance, bench (+ its share of the
points) and in the paint; the efficiency of each origin (points per 100 possessions that started that way) and the same
figures for the rivals (``opp_``: what the team concedes). Games whose play-by-play is ``unreliable`` are left out
(``games_unreliable``). FEB only; fast-break points are not derived (the FEB definition is not reproducible from the pbp).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from cachetools import TTLCache

from src.database.aggregation.pipeline_points_origin import build_points_origin_pipeline
from src.pbp.game_derived import DERIVED_VERSION

_cache: TTLCache = TTLCache(maxsize=32, ttl=3600)
_ORIGINS = {"off_tov": "poss_off_tov", "off_steal": "poss_off_steal", "second_chance": "poss_second_chance"}
_POINTS = ("pts_off_tov", "pts_off_steal", "pts_second_chance", "pts_bench", "pts_paint")


def clear_cache() -> None:
    _cache.clear()


def _ratio(numerator: float, denominator: float, scale: float = 1.0) -> Optional[float]:
    return numerator / denominator * scale if denominator else None


def _team_row(raw: Dict[str, Any]) -> Dict[str, Any]:
    games = raw["games"]
    row: Dict[str, Any] = {"team_id": raw["_id"], "team_name": raw.get("team_name"), "games": games,
                           "games_unreliable": raw["games_unreliable"], "games_paint": raw["games_paint"]}
    for prefix in ("", "opp_"):
        for field in _POINTS:
            key = prefix + field
            has_data = games and (field != "pts_paint" or raw["games_paint"])
            row[key] = raw[key] if has_data else None
            row[f"{key}_per_game"] = _ratio(raw[key], games) if has_data else None
        for origin, possessions in _ORIGINS.items():
            row[f"{prefix}oer_{origin}"] = _ratio(raw[f"{prefix}pts_{origin}"], raw[prefix + possessions], 100.0)
        row[f"{prefix}bench_pct"] = _ratio(raw[prefix + "pts_bench"], raw[prefix + "pts"], 100.0)
    return row


class PBPExtendedStatsService:
    """Aggregates the stored per-game figures; one pass over a projected pipeline, cached for an hour per collection."""

    def __init__(self, db_handler: Any) -> None:
        self._db = db_handler

    def get_points_by_origin(self, collection_name: str) -> List[Dict[str, Any]]:
        cached = _cache.get(collection_name)
        if cached is not None:
            return cached
        collection = self._db.repository.connection.get_collection(collection_name)
        raw = collection.aggregate(build_points_origin_pipeline(DERIVED_VERSION))
        rows = sorted((_team_row(r) for r in raw), key=lambda r: str(r["team_name"]))
        _cache[collection_name] = rows
        return rows
