"""Season situations per team (#354) and the effect of the timeouts (#355), summed from ``DERIVED``.

Situations: points per possession after a timeout the team called (``ato_own``) or the rival called (``ato_rival``), of the first
possession of the periods it started, and the first and last two minutes of the periods (net rating, points, turnover rate and the
difference with the rest of the period). Timeouts: the net rating of the ``TM_WINDOW_POSSESSIONS`` possessions of each team before
and after each timeout, for those the team called (``own``) and those the rival called (``rival``), with the share that improved
the caller; timeouts of the last minute of a period are not analysed. Games that are not reliable (#390: more than 10 % of their points of unknown origin, or a possession count more than 10 % off the estimate) are left out. FEB only.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from cachetools import TTLCache

from src.database.aggregation.pipeline_situation_stats import EDGE_KEYS, build_situations_pipeline, build_timeouts_pipeline

MIN_VERSION = 5     # the reliability flag of DERIVED v5 (#390)
_situations: TTLCache = TTLCache(maxsize=32, ttl=3600)
_timeouts: TTLCache = TTLCache(maxsize=32, ttl=3600)


def clear_cache() -> None:
    _situations.clear()
    _timeouts.clear()


def _ratio(numerator: float, denominator: float, scale: float = 1.0) -> Optional[float]:
    return numerator / denominator * scale if denominator else None


def _net(pts: float, opp_pts: float, poss: float, opp_poss: float) -> Optional[float]:
    return (pts / poss - opp_pts / opp_poss) * 100.0 if poss and opp_poss else None


def _block(raw: Dict[str, Any], name: str) -> Dict[str, Any]:
    n, pts = raw[f"{name}_n"], raw[f"{name}_pts"]
    return {"n": n, "pts": pts, "ppp": _ratio(pts, n)}


def _edge(raw: Dict[str, Any], values: Dict[str, float], games: int) -> Dict[str, Any]:
    return {**{k: values[k] for k in EDGE_KEYS}, "pts_per_game": values["pts"] / games,
            "net_rating": _net(values["pts"], values["opp_pts"], values["poss"], values["opp_poss"]),
            "tov_pct": _ratio(values["tov"], values["poss"], 100.0), "opp_tov_pct": _ratio(values["opp_tov"], values["opp_poss"], 100.0)}


def _situation_row(raw: Dict[str, Any]) -> Dict[str, Any]:
    games = raw["games"]
    edges = {w: _edge(raw, {k: raw[f"{w}_{k}"] for k in EDGE_KEYS}, games) for w in ("start", "end")}
    rest = {k: raw[f"tot_{k}"] - raw[f"start_{k}"] - raw[f"end_{k}"] for k in EDGE_KEYS}
    edges["rest"] = _edge(raw, rest, games)
    for w in ("start", "end"):
        a, b = edges[w]["net_rating"], edges["rest"]["net_rating"]
        edges[w]["vs_rest"] = a - b if a is not None and b is not None else None
    return {"team_id": raw["_id"], "team_name": raw.get("team_name"), "games": games, "games_unreliable": raw["games_unreliable"], "games_doubtful": raw["games_doubtful"],
            "ato_own": _block(raw, "ato_own"), "ato_rival": _block(raw, "ato_rival"), "first_poss": _block(raw, "first_poss"),
            "edges": edges}


def _timeout_group(raw: Optional[Dict[str, Any]], caller: str) -> Dict[str, Any]:
    if not raw or not raw["n"]:
        return {"n": 0, "net_rating_before": None, "net_rating_after": None, "delta_net_rating": None, "pct_caller_improves": None}
    helped = raw["improved"] if caller == "own" else raw["worsened"]       # after the rival's timeout, our fall is the caller's gain
    return {"n": raw["n"], "net_rating_before": raw["net_before"], "net_rating_after": raw["net_after"],
            "delta_net_rating": raw["net_after"] - raw["net_before"], "pct_caller_improves": helped / raw["n"] * 100.0}


class PBPSituationStatsService:
    """Aggregates the stored per-game figures; one projected pipeline per call, cached an hour per collection."""

    def __init__(self, db_handler: Any) -> None:
        self._db = db_handler

    def _collection(self, name: str) -> Any:
        return self._db.repository.connection.get_collection(name)

    def get_situations(self, collection_name: str) -> List[Dict[str, Any]]:
        cached = _situations.get(collection_name)
        if cached is not None:
            return cached
        rows = sorted((_situation_row(r) for r in self._collection(collection_name).aggregate(build_situations_pipeline(MIN_VERSION))),
                      key=lambda r: str(r["team_name"]))
        _situations[collection_name] = rows
        return rows

    def get_timeout_effects(self, collection_name: str) -> List[Dict[str, Any]]:
        cached = _timeouts.get(collection_name)
        if cached is not None:
            return cached
        teams: Dict[str, Dict[str, Any]] = {}
        for raw in self._collection(collection_name).aggregate(build_timeouts_pipeline(MIN_VERSION)):
            team = teams.setdefault(raw["_id"]["team"], {"team_id": raw["_id"]["team"], "team_name": raw.get("team_name"), "groups": {}, "doubtful": set()})
            team["doubtful"].update(g for g in raw["doubtful"] if g is not None)
            if raw["_id"].get("caller") in ("own", "rival"):
                team["groups"][raw["_id"]["caller"]] = raw
        rows = sorted(({"team_id": t["team_id"], "team_name": t["team_name"], "games_doubtful": len(t["doubtful"]),
                        "own": _timeout_group(t["groups"].get("own"), "own"), "rival": _timeout_group(t["groups"].get("rival"), "rival")}
                       for t in teams.values()), key=lambda r: str(r["team_name"]))
        _timeouts[collection_name] = rows
        return rows
