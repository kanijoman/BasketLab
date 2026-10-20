"""Season points by origin, bench and paint per team (#352), summed from the ``DERIVED`` field of each match.

Per team: points per game after turnovers (steals included), after steals, second chance, bench (+ its share of the
points) and in the paint; the efficiency of each origin (points per 100 possessions that started that way) and the same
figures for the rivals (``opp_``: what the team concedes). Games that are not reliable (#390: more than 10 % of their points of unknown origin, or a possession count more than 10 % off the estimate) are left out
(``games_unreliable``); ``games_doubtful`` counts the games used whose feed has alternation breaks (stored, not shown, #392). FEB and FBCYL (#432); fast-break points are not derived (the FEB definition is not reproducible from the pbp).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from cachetools import TTLCache

from src.database.aggregation.pipeline_period_stats import build_period_pipeline
from src.database.aggregation.pipeline_points_origin import build_points_origin_pipeline
from src.live_core.four_factors import FT_POSSESSION_COST

# First DERIVED version that carries each group of figures (the backfill brings the older games up to date)
ORIGIN_MIN_VERSION = 6     # every group needs the reliability flag of v5 (#390); the fast break (our own estimate, #398) is v6
PERIOD_MIN_VERSION = 5
_cache: TTLCache = TTLCache(maxsize=32, ttl=3600)
_period_cache: TTLCache = TTLCache(maxsize=32, ttl=3600)
_ORIGINS = {"off_tov": "poss_off_tov", "off_steal": "poss_off_steal", "second_chance": "poss_second_chance", "fastbreak": "poss_transition"}
_POINTS = ("pts_off_tov", "pts_off_steal", "pts_second_chance", "pts_bench", "pts_paint", "pts_fastbreak")


def clear_cache() -> None:
    _cache.clear()
    _period_cache.clear()


def _ratio(numerator: float, denominator: float, scale: float = 1.0) -> Optional[float]:
    return numerator / denominator * scale if denominator else None


def _team_row(raw: Dict[str, Any]) -> Dict[str, Any]:
    games = raw["games"]
    row: Dict[str, Any] = {"team_id": raw["_id"], "team_name": raw.get("team_name"), "games": games,
                           "games_unreliable": raw["games_unreliable"], "games_doubtful": raw["games_doubtful"],
                           "games_paint": raw["games_paint"]}
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


def _period_row(raw: Dict[str, Any], games: int) -> Dict[str, Any]:
    """The figures of one team in one period bucket, summed over ``games`` games (``raw`` holds the sums)."""
    fga, fta, opp_fga, opp_fta = raw["fga"], raw["fta"], raw["opp_fga"], raw["opp_fta"]
    efg = lambda p, fgm, three, att: _ratio(raw[p + fgm] + 0.5 * raw[p + three], att, 100.0)   # noqa: E731
    tov_pct = lambda p, att, ft: _ratio(raw[p + "tov"], att + FT_POSSESSION_COST * ft + raw[p + "tov"], 100.0)   # noqa: E731
    return {
        "games": games, "minutes": raw["minutes"],
        "pts": raw["pts"], "opp_pts": raw["opp_pts"],
        "pts_per_game": raw["pts"] / games, "opp_pts_per_game": raw["opp_pts"] / games,
        "poss": raw["poss"], "opp_poss": raw["opp_poss"],
        "ortg": _ratio(raw["pts"], raw["poss"], 100.0), "drtg": _ratio(raw["opp_pts"], raw["opp_poss"], 100.0),
        "net_rating": (raw["pts"] / raw["poss"] - raw["opp_pts"] / raw["opp_poss"]) * 100.0 if raw["poss"] and raw["opp_poss"] else None,
        "pace": _ratio(raw["poss"] * 40.0, raw["minutes"]),
        "efg_pct": efg("", "fgm", "fg3m", fga), "opp_efg_pct": efg("opp_", "fgm", "fg3m", opp_fga),
        "tov_pct": tov_pct("", fga, fta), "opp_tov_pct": tov_pct("opp_", opp_fga, opp_fta),
        "orb_pct": _ratio(raw["orb"], raw["orb"] + raw["opp_drb"], 100.0), "drb_pct": _ratio(raw["drb"], raw["drb"] + raw["opp_orb"], 100.0),
        "ftr": _ratio(fta, fga, 100.0), "opp_ftr": _ratio(opp_fta, opp_fga, 100.0),
        "fouls_per_game": raw["fouls"] / games, "opp_fouls_per_game": raw["opp_fouls"] / games,
    }


class PBPExtendedStatsService:
    """Aggregates the stored per-game figures; one pass over a projected pipeline, cached for an hour per collection."""

    def __init__(self, db_handler: Any) -> None:
        self._db = db_handler

    def get_points_by_origin(self, collection_name: str) -> List[Dict[str, Any]]:
        cached = _cache.get(collection_name)
        if cached is not None:
            return cached
        collection = self._db.repository.connection.get_collection(collection_name)
        raw = collection.aggregate(build_points_origin_pipeline(ORIGIN_MIN_VERSION))
        rows = sorted((_team_row(r) for r in raw), key=lambda r: str(r["team_name"]))
        _cache[collection_name] = rows
        return rows

    def get_by_period(self, collection_name: str) -> List[Dict[str, Any]]:
        """Per team, its figures in Q1-Q4 and OT (every overtime together) with the rival's (``opp_``); cached an hour."""
        cached = _period_cache.get(collection_name)
        if cached is not None:
            return cached
        collection = self._db.repository.connection.get_collection(collection_name)
        teams: Dict[str, Dict[str, Any]] = {}
        for raw in collection.aggregate(build_period_pipeline(PERIOD_MIN_VERSION)):
            team = teams.setdefault(raw["_id"]["team"], {"team_id": raw["_id"]["team"], "team_name": raw.get("team_name"),
                                                         "games": 0, "games_unreliable": 0, "games_doubtful": 0, "periods": {}})
            games = len([g for g in raw["games"] if g is not None])
            if raw["_id"]["bucket"] == "1":
                team["games"], team["games_unreliable"] = games, len([g for g in raw["unreliable"] if g is not None])
                team["games_doubtful"] = len([g for g in raw["doubtful"] if g is not None])
            if games:
                team["periods"][raw["_id"]["bucket"]] = _period_row(raw, games)
        for team in teams.values():
            team["periods"] = dict(sorted(team["periods"].items(), key=lambda kv: 99 if kv[0] == "OT" else int(kv[0])))
        rows = sorted(teams.values(), key=lambda r: str(r["team_name"]))
        _period_cache[collection_name] = rows
        return rows
