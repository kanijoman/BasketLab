"""The rich part of ``DERIVED.TEAM`` for the fixture leagues (#676): what the pbp tables sum (points by origin, periods, situations, timeouts).

``games.py`` and ``fbcyl_games.py`` give their ``DERIVED`` games the exact possessions, rebounds and turnovers the season rows read; ``enrich`` adds the rest on top, without
touching those, so the rows of the contract (and every vector made from them) stay as they were. Deterministic: the numbers come from the game's number.

Three kinds of game cover the branches of the tables: a reliable one at the current version, one that is NOT reliable (left out of every sum, only counted), and an older
version (v5: it has the periods and the situations but not the fast break, so the origin tables leave it out) that is doubtful (used, but flagged) and has an overtime.
"""
import random
from typing import Any, Dict, List

# game number -> (DERIVED version, quality_level, reliable, periods played)
KINDS = {2: (6, "ok", True, 4), 5: (6, "unreliable", False, 4), 9: (5, "doubtful", True, 5)}
ORIGINS = ("period_start", "made_basket", "turnover", "steal", "def_rebound", "team_def_rebound", "trip", "unknown", "technical")
COUNTERS = ("pts", "poss", "fga", "fgm", "fg3m", "fta", "ftm", "tov", "orb", "drb", "fouls")


def _counters(rng: random.Random, minutes: int) -> Dict[str, int]:
    scale = minutes / 10
    fga = round(rng.randint(12, 22) * scale)
    return {"pts": round(rng.randint(14, 30) * scale), "poss": round(rng.randint(16, 24) * scale), "fga": fga, "fgm": round(fga * rng.uniform(0.35, 0.55)),
            "fg3m": round(rng.randint(0, 4) * scale), "fta": round(rng.randint(2, 9) * scale), "ftm": round(rng.randint(1, 7) * scale), "tov": round(rng.randint(1, 6) * scale),
            "orb": round(rng.randint(1, 5) * scale), "drb": round(rng.randint(3, 9) * scale), "fouls": round(rng.randint(2, 7) * scale)}


def _window(rng: random.Random) -> Dict[str, int]:
    return {"pts": rng.randint(2, 9), "opp_pts": rng.randint(2, 9), "poss": rng.randint(3, 6), "opp_poss": rng.randint(3, 6), "tov": rng.randint(0, 2), "opp_tov": rng.randint(0, 2)}


def _timeouts(rng: random.Random, n: int) -> List[Dict[str, Any]]:
    out = []
    for _ in range(n):
        side = lambda: {"pts": rng.randint(2, 8), "poss": rng.randint(3, 5), "opp_pts": rng.randint(2, 8), "opp_poss": rng.randint(3, 5)}   # noqa: E731
        out.append({"caller": rng.choice(("own", "rival")), "pre": side(), "post": side()})
    return out


def enrich(teams: List[Dict[str, Any]], n: int) -> int:
    """Add the pbp figures to the two ``DERIVED.TEAM`` entries of game ``n`` in place and return the version the game carries."""
    version, quality, reliable, periods = KINDS[n]
    rng = random.Random(7000 + n)
    per_period = [(p, 10 if p <= 4 else 5) for p in range(1, periods + 1)]
    sides = [[{"p": p, "minutes": minutes, **_counters(rng, minutes)} for p, minutes in per_period] for _ in teams]
    for index, team in enumerate(teams):
        mine, other = sides[index], sides[1 - index]
        origin = {k: rng.randint(0, 14) for k in ORIGINS}
        team.update({
            "reliable": reliable, "quality_level": quality, "unknown_pts_pct": 2.0 if reliable else 31.5,
            "pts": sum(p["pts"] for p in mine), "pts_by_origin": origin,
            "pts_off_tov": rng.randint(8, 20), "poss_off_tov": rng.randint(8, 16), "pts_off_steal": rng.randint(2, 8), "poss_off_steal": rng.randint(2, 7),
            "pts_second_chance": rng.randint(4, 14), "poss_second_chance": rng.randint(5, 12), "pts_bench": rng.randint(10, 35),
            "pts_paint": None if (n == 2 and index == 1) else rng.randint(18, 44),            # a game without SHOTCHART: no paint points
            "periods": [{**p, **{f"opp_{k}": other[i][k] for k in COUNTERS}} for i, p in enumerate(mine)],
            "ato_own": {"n": rng.randint(0, 4), "pts": rng.randint(0, 8)}, "ato_rival": {"n": rng.randint(0, 4), "pts": rng.randint(0, 8)},
            "first_poss": {"n": rng.randint(0, periods), "pts": rng.randint(0, 6)},
            "edges": {"start": _window(rng), "end": _window(rng)},
            "timeouts": _timeouts(rng, 0 if (n == 5 and index == 0) else rng.randint(1, 3)),     # a team with no timeouts to analyse
        })
        if version >= 6:
            team.update({"pts_fastbreak": rng.randint(2, 12), "poss_transition": rng.randint(3, 10)})
    return version
