"""Rates, role and percentiles of the Talent rows (B2, #878).

One call is ONE competition and season: the population of the percentiles and of the role is the players of that competition only, never mixed with another (a percentile in
LF Endesa and one in a youth championship say different things; comparing them is the job of the equivalence graph, E1). A transfer is two rows and both count in the population.

Rates and role are the live engine's (``live_core.profiles``, standard library): per-40 rates, shrinkage towards the league by playing time and z-scored role dimensions, so that a
player of Talent and one of a live package are described the same way. Only players with ``MIN_POPULATION_SECONDS`` on court make the population (the same 5 minutes as the live packages);
the others are described and ranked against it, with ``eligible: false``. A percentile is 0-100 and means how good, so for turnovers lower is better; ties share the middle rank.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from src.live_core.clock import GAME_SECONDS
from src.live_core.four_factors import FT_POSSESSION_COST
from src.live_core.profiles import ROLE_DIMS, league_distribution, raw_rates, shrink_rates, z_scores

MIN_POPULATION_SECONDS = 300
PERCENTILE_METRICS = ("pts", "orb", "drb", "ast", "tov", "stl", "blk", "fg3a", "fg2a", "usage", "efg", "ftr", "ts", "usage_pct", "pie")
LOWER_IS_BETTER = frozenset({"tov"})
_RATES = {"orb40": "orb", "drb40": "drb", "ast40": "ast", "tov40": "tov", "stl40": "stl", "blk40": "blk", "fg3a40": "fg3a", "fg2a40": "fg2a", "usage40": "usage", "efg": "efg", "ftr": "ftr"}


def _stats(row: Dict[str, Any]) -> Dict[str, int]:
    """The names ``live_core.profiles`` reads, from the names of the row."""
    return {"orb": row["ro"], "drb": row["rd"], "ast": row["assist"], "tov": row["to"], "stl": row["st"], "blk": row["bs"], "fg2a": row["p2a"], "fg3a": row["p3a"],
            "fg2m": row["p2m"], "fg3m": row["p3m"], "fta": row["p1a"], "ftm": row["p1m"]}


def _per40(row: Dict[str, Any], seconds: float) -> Optional[Dict[str, float]]:
    raw = raw_rates(_stats(row), seconds)
    if raw is None:
        return None
    fga = row["p2a"] + row["p3a"]
    scale = GAME_SECONDS / seconds
    out = {_RATES[k]: v for k, v in raw.items()}
    out["pts"] = (2 * row["p2m"] + 3 * row["p3m"] + row["p1m"]) * scale
    plays = fga + FT_POSSESSION_COST * row["p1a"]
    out["ts"] = row["pts"] / (2 * plays) if plays else 0.0
    return out


def _percentile(value: Optional[float], population: List[float], lower_is_better: bool) -> Optional[float]:
    if value is None or not population:
        return None
    below = sum(1 for x in population if x < value)
    above = sum(1 for x in population if x > value)
    equal = len(population) - below - above
    return round(((above if lower_is_better else below) + 0.5 * equal) / len(population) * 100, 1)


def add_profiles(rows: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """The rows of one competition and season with ``per40`` (rates and shooting), ``role`` (z-scored dimensions), ``pct`` (percentiles) and ``eligible``; the inputs are not changed."""
    rows = list(rows)
    seconds = [float(r.get("minutes") or 0) for r in rows]
    rates = [_per40(r, s) if s > 0 else None for r, s in zip(rows, seconds)]
    eligible = [s >= MIN_POPULATION_SECONDS and rt is not None for s, rt in zip(seconds, rates)]
    raw_population = [raw_rates(_stats(r), s) for r, s, ok in zip(rows, seconds, eligible) if ok]
    league = league_distribution([p for p in raw_population if p is not None])
    values: Dict[str, List[float]] = {m: [] for m in PERCENTILE_METRICS}
    for r, rt, ok in zip(rows, rates, eligible):
        if ok:
            for m in PERCENTILE_METRICS:
                v = {**rt, "usage_pct": r.get("usage_pct"), "pie": r.get("pie")}.get(m)
                if v is not None:
                    values[m].append(v)
    out = []
    for r, s, rt, ok in zip(rows, seconds, rates, eligible):
        if rt is None:
            out.append({**r, "per40": None, "role": None, "pct": None, "eligible": False})
            continue
        shrunk = shrink_rates(raw_rates(_stats(r), s), s, r["p2a"] + r["p3a"], league)
        z = z_scores(shrunk, league)
        mine = {**rt, "usage_pct": r.get("usage_pct"), "pie": r.get("pie")}
        out.append({**r, "eligible": ok, "per40": {k: round(v, 3) for k, v in rt.items()}, "role": {d: round(z[d], 3) for d in ROLE_DIMS},
                    "pct": {m: _percentile(mine.get(m), values[m], m in LOWER_IS_BETTER) for m in PERCENTILE_METRICS}})
    return out
