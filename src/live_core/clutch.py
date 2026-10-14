"""Clutch analytics (issue #274): what a player does in a close finish (standard library only).

The window is the one of ``game_context``'s ``close_late``: a margin of ``close_margin`` (6) or less in the last
``close_remaining_s`` (4:00) of the 4th period, or in overtime. ``state.LiveGame`` adds up, per player and per game, the field-goal
attempts, free throws, turnovers, points and seconds on court inside the window (``empty()`` is one set of totals), and the same for
the whole 4th period, which is the fallback when the clutch sample is too small.

``summarize`` turns the season totals into the two things the staff wants (the package carries it as ``tables.players[pid].clutch``):

* **Responsibility**: (shots + turnovers) per 10 minutes, where a free throw is a 0.44 shot, shrunk to the player's normal usage with a
  prior of ``SHRINK_SECONDS`` (10 minutes). It is the stable one: a close finish is a few minutes a game.
* **Accuracy**: points per shot, shrunk to the season's with a much stronger prior (``PPS_PRIOR_SHOTS`` shots), and the free-throw
  percentage shrunk to the season's. Noisy: it is always shown with its sample. ``effective`` only if the shrunk accuracy is above the
  season's.

Below ``MIN_SECONDS`` of clutch time it uses the 4th period (``basis: "q4"``, ``sample: "small"``); without that either, nothing.
"""

from __future__ import annotations

from typing import Any, Dict

from .clock import period_length, period_start
from .config import RuleConfig

FIELDS = ("fga", "fta", "ftm", "tov", "pts", "sec")
MIN_SECONDS = 240          # clutch (or 4th-period) seconds needed to say anything
SHRINK_SECONDS = 600       # responsibility: prior weight of 10 minutes
PPS_PRIOR_SHOTS = 60       # accuracy: a much stronger prior than the 30 attempts of the efficiency rates
FT_PRIOR_ATTEMPTS = 10     # free-throw percentage: prior weight in attempts
FT_POSSESSION_COST = 0.44
LAST_REGULATION_PERIOD = 4

_CFG = RuleConfig()


def empty() -> Dict[str, int]:
    return {k: 0 for k in FIELDS}


def window_start(period: int) -> int:
    """First game-second of the clutch window in ``period`` (None-like large number if the period never has one)."""
    if period > LAST_REGULATION_PERIOD:
        return period_start(period)
    if period == LAST_REGULATION_PERIOD:
        return period_start(period) + period_length(period) - _CFG.close_remaining_s
    return 10 ** 9


def in_window_margin() -> int:
    """The largest margin that still counts as a close game."""
    return _CFG.close_margin


def in_window(period: int, elapsed: int, margin: int) -> bool:
    """Is a moment of the game (period, game-second, score margin) inside the clutch window?"""
    return abs(margin) <= _CFG.close_margin and period >= LAST_REGULATION_PERIOD and elapsed >= window_start(period)


def summarize(clutch: Dict[str, int], q4: Dict[str, int], usage_per10: float, pps_season: float,
              ft_pct_season: float) -> Dict[str, Any]:
    """Responsibility and accuracy of a player from his season totals (see the module doc)."""
    basis, data = "clutch", clutch
    if clutch["sec"] < MIN_SECONDS:
        basis, data = "q4", q4
        if q4["sec"] < MIN_SECONDS:
            return {"basis": "none", "sample": "none", "sec": clutch["sec"]}
    sec = data["sec"]
    shots = data["fga"] + FT_POSSESSION_COST * data["fta"]
    w_time = sec / (sec + SHRINK_SECONDS)
    usage = w_time * ((shots + data["tov"]) / sec * 600) + (1 - w_time) * usage_per10
    w_shots = shots / (shots + PPS_PRIOR_SHOTS) if shots else 0.0
    pps = w_shots * (data["pts"] / shots if shots else 0.0) + (1 - w_shots) * pps_season
    ft_pct = (data["ftm"] + FT_PRIOR_ATTEMPTS * ft_pct_season) / (data["fta"] + FT_PRIOR_ATTEMPTS)
    return {
        "basis": basis, "sample": "ok" if basis == "clutch" else "small", "sec": sec,
        "fga": data["fga"], "fta": data["fta"], "ftm": data["ftm"], "tov": data["tov"], "pts": data["pts"],
        "usage": round(usage, 2), "pps": round(pps, 3), "pps_season": round(pps_season, 3),
        "effective": bool(pps_season > 0 and pps > pps_season), "ft_pct": round(ft_pct, 3),
    }
