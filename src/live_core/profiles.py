"""Player rates, shrinkage and z-scored role profiles (standard library only).

The feed has no position or height, so a player's ROLE is inferred from what they do:
rebounding, passing, shot mix, blocks and usage, standardised against the league. Role
dimensions describe behaviour, not quality; quality metrics (eFG, turnovers, free-throw
rate) are kept apart and used to rank candidates once the role is matched.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

League = Dict[str, Dict[str, float]]  # metric -> {"mean", "sd"}

GAME_SECONDS = 2400
FT_POSSESSION_COST = 0.44

METRICS = ("orb40", "drb40", "ast40", "tov40", "stl40", "blk40", "fg3a40", "fg2a40", "usage40", "efg", "ftr")
ROLE_DIMS = ("orb40", "drb40", "ast40", "blk40", "fg3a40", "fg2a40", "usage40")

# Used when the league has too few players to estimate a distribution (placeholders).
DEFAULT_LEAGUE: Dict[str, Dict[str, float]] = {
    "orb40": {"mean": 1.5, "sd": 1.2}, "drb40": {"mean": 4.0, "sd": 2.5},
    "ast40": {"mean": 3.5, "sd": 2.5}, "tov40": {"mean": 2.8, "sd": 1.2},
    "stl40": {"mean": 1.4, "sd": 0.8}, "blk40": {"mean": 0.4, "sd": 0.5},
    "fg3a40": {"mean": 5.5, "sd": 3.5}, "fg2a40": {"mean": 7.0, "sd": 3.5},
    "usage40": {"mean": 15.0, "sd": 4.0}, "efg": {"mean": 0.50, "sd": 0.08},
    "ftr": {"mean": 0.28, "sd": 0.15},
}

MIN_PLAYERS_FOR_DISTRIBUTION = 8
SHRINK_SECONDS = 600       # volume rates: prior weight of 10 minutes
SHRINK_ATTEMPTS = 30       # efficiency rates: prior weight of 30 field-goal attempts
SD_FLOOR_FRACTION = 0.25  # never trust a spread below a quarter of the default one
_PER_ATTEMPT = ("efg", "ftr")


def raw_rates(stats: Dict[str, int], seconds: float) -> Optional[Dict[str, float]]:
    """Per-40 volume rates plus eFG and FTr; None when the player has no minutes."""
    if seconds <= 0:
        return None
    scale = GAME_SECONDS / seconds
    fga = stats["fg2a"] + stats["fg3a"]
    return {
        "orb40": stats["orb"] * scale, "drb40": stats["drb"] * scale, "ast40": stats["ast"] * scale,
        "tov40": stats["tov"] * scale, "stl40": stats["stl"] * scale, "blk40": stats["blk"] * scale,
        "fg3a40": stats["fg3a"] * scale, "fg2a40": stats["fg2a"] * scale,
        "usage40": (fga + FT_POSSESSION_COST * stats["fta"] + stats["tov"]) * scale,
        "efg": (stats["fg2m"] + 1.5 * stats["fg3m"]) / fga if fga else 0.0,
        "ftr": stats["fta"] / fga if fga else 0.0,
    }


def shrink_rates(rates: Dict[str, float], seconds: float, fga: float,
                 league: Dict[str, Dict[str, float]]) -> Dict[str, float]:
    """Blend each rate with the league mean: little playing time -> close to the league."""
    w_volume = seconds / (seconds + SHRINK_SECONDS) if seconds > 0 else 0.0
    w_attempts = fga / (fga + SHRINK_ATTEMPTS) if fga > 0 else 0.0
    out = {}
    for metric in METRICS:
        w = w_attempts if metric in _PER_ATTEMPT else w_volume
        out[metric] = w * rates[metric] + (1 - w) * league[metric]["mean"]
    return out


def z_scores(rates: Dict[str, float], league: Dict[str, Dict[str, float]]) -> Dict[str, float]:
    return {m: (rates[m] - league[m]["mean"]) / max(league[m]["sd"], SD_FLOOR_FRACTION * DEFAULT_LEAGUE[m]["sd"])
            for m in METRICS}


def league_distribution(players: List[Dict[str, float]]) -> Dict[str, Dict[str, float]]:
    """Mean and standard deviation per metric over the league's players (defaults if too few)."""
    if len(players) < MIN_PLAYERS_FOR_DISTRIBUTION:
        return {m: dict(v) for m, v in DEFAULT_LEAGUE.items()}
    out = {}
    for metric in METRICS:
        values = [p[metric] for p in players]
        mean = sum(values) / len(values)
        sd = math.sqrt(sum((v - mean) ** 2 for v in values) / len(values))
        out[metric] = {"mean": mean, "sd": max(sd, SD_FLOOR_FRACTION * DEFAULT_LEAGUE[metric]["sd"])}
    return out


def role_distance(a: Dict[str, float], b: Dict[str, float]) -> float:
    """Euclidean distance between two z-profiles over the role dimensions."""
    return math.sqrt(sum((a[d] - b[d]) ** 2 for d in ROLE_DIMS))


# --- impact rates (rival scouting: who is producing far above their usual) ------------

IMPACT_METRICS = ("pts", "orb", "stl", "ast", "fg3m", "fta")

# Per-40 league means used when the league population is too small (placeholders).
DEFAULT_IMPACT_LEAGUE: Dict[str, float] = {
    "pts": 14.0, "orb": 1.5, "stl": 1.4, "ast": 3.5, "fg3m": 1.7, "fta": 3.5,
}


def impact_rates(stats: Dict[str, int], seconds: float) -> Optional[Dict[str, float]]:
    """Per-40 production (points, offensive rebounds, steals, assists, threes made, FTA)."""
    if seconds <= 0:
        return None
    scale = GAME_SECONDS / seconds
    points = 2 * stats["fg2m"] + 3 * stats["fg3m"] + stats["ftm"]
    return {"pts": points * scale, "orb": stats["orb"] * scale, "stl": stats["stl"] * scale,
            "ast": stats["ast"] * scale, "fg3m": stats["fg3m"] * scale, "fta": stats["fta"] * scale}


def shrink_impact(rates: Dict[str, float], seconds: float, league: Dict[str, float]) -> Dict[str, float]:
    """Blend a player's per-40 production with the league mean by playing time."""
    w = seconds / (seconds + SHRINK_SECONDS) if seconds > 0 else 0.0
    return {m: w * rates[m] + (1 - w) * league[m] for m in IMPACT_METRICS}


def impact_league(players: List[Dict[str, float]]) -> Dict[str, float]:
    """League mean per metric (defaults when there are too few players)."""
    if len(players) < MIN_PLAYERS_FOR_DISTRIBUTION:
        return dict(DEFAULT_IMPACT_LEAGUE)
    return {m: sum(p[m] for p in players) / len(players) for m in IMPACT_METRICS}
