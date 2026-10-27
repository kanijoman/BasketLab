"""Comparative reports of the teams on the web (issue #607): the comparisons of the weekly report, asked on demand.

Home vs away, won vs lost, and a stretch of the season vs the rest of it: each side is a call of ``TeamStatsService.load_season_data`` with its own filters, so a figure means the
same here as in every other table. Per team the row has both groups and the REAL difference (group 1 minus group 2, in the unit of the figure: points for a percentage), for the team
(``team``) and for what its rivals did against it (``opponent``). The weekly report said the same with an arrow of the percentage change; the arrow is gone (issue #608).
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from .team_stats_service import TeamStatsService

# The numeric figures of the tables of the web (basic and advanced), and the games that say how much each group weighs.
COMPARED_FIELDS = (
    "total_games", "games_home", "games_away",
    "points_per_game", "points_against_per_game", "fg2_percentage", "fg3_percentage", "ft_percentage",
    "rebounds_per_game", "offensive_rebounds_per_game", "defensive_rebounds_per_game", "assists_per_game", "steals_per_game", "turnovers_per_game", "blocks_per_game",
    "possessions_per_game", "offensive_rating", "defensive_rating", "net_rating", "efg_percentage", "true_shooting", "three_point_rate", "free_throw_rate",
    "assist_fg_rate", "assist_rate", "turnover_rate", "steal_rate", "block_rate", "offensive_rebound_rate", "defensive_rebound_rate",
)
LABELS = {"venue": ("Local", "Visitante"), "result": ("Ganados", "Perdidos"), "period": ("Tramo", "Resto de la temporada")}


def _number(value: Any) -> Optional[float]:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _figures(row: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    return None if row is None else {key: row[key] for key in COMPARED_FIELDS if key in row and row[key] is not None}


def _row(name: str, a: Optional[Dict[str, Any]], b: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """One team: both groups, their games and the difference of every figure the two have."""
    fa, fb = _figures(a), _figures(b)
    diff = {}
    for key in COMPARED_FIELDS:
        x, y = _number((fa or {}).get(key)), _number((fb or {}).get(key))
        if x is not None and y is not None:
            diff[key] = round(x - y, 4)
    source = a or b or {}
    return {"team_id": source.get("team_id", source.get("_id")), "team_name": name, "games_a": int((fa or {}).get("total_games") or 0),
            "games_b": int((fb or {}).get("total_games") or 0), "a": fa, "b": fb, "diff": diff}


def _rows(first: List[Dict[str, Any]], second: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Teams are matched by name: it works for FEB (scalar ``_id``) and FBCYL (``_id`` is a dict)."""
    by_a = {str(r.get("team_name") or r.get("_id", "")): r for r in first or []}
    by_b = {str(r.get("team_name") or r.get("_id", "")): r for r in second or []}
    return [_row(name, by_a.get(name), by_b.get(name)) for name in sorted(set(by_a) | set(by_b))]


class TeamComparisonService:
    def __init__(self, db_handler: Any) -> None:
        self._stats = TeamStatsService(db_handler)

    def compare(self, collection: str, by: str, date_from: Optional[datetime] = None, date_to: Optional[datetime] = None) -> Dict[str, Any]:
        if by not in LABELS:
            raise ValueError(f"comparación desconocida: {by!r} (venue, result o period)")
        if by == "venue":
            a = self._stats.load_season_data(collection, venue_filter=True)
            b = self._stats.load_season_data(collection, venue_filter=False)
        elif by == "result":
            a = self._stats.load_season_data(collection, result_filter="won")
            b = self._stats.load_season_data(collection, result_filter="lost")
        else:
            if date_from is None and date_to is None:
                raise ValueError("Un tramo necesita al menos una fecha (desde o hasta)")
            stretch = {**({"$gte": date_from} if date_from else {}), **({"$lte": date_to} if date_to else {})}
            a = self._stats.load_season_data(collection, date_filter=stretch)
            b = self._stats.load_season_data(collection, date_filter={"$not": stretch})        # before it and after it
        label_a, label_b = LABELS[by]
        return {"by": by, "label_a": label_a, "label_b": label_b,
                "team": _rows(a["team_stats"], b["team_stats"]), "opponent": _rows(a["opponent_stats"], b["opponent_stats"])}
