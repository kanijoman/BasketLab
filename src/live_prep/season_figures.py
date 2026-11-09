"""The season of a player for the columns of the live box score that had no reference (feedback of the 0.5.2, after #699).

``SeasonAccumulator`` (``package_builder``) adds ``season_figures`` to each row of ``tables.players`` / ``tables.rival_players``:

* ``fd_per40``, ``pm_per40``, ``val_per40`` (fouls drawn, plus/minus and the valuation of the box score) and ``val_gross_per40`` (what adds and what subtracts in the valuation,
  all added up: its noise in the box score);
* ``fg2_pct`` and ``fg_pct`` shrunk to the league with the weight of ``SHOT_PRIOR_ATTEMPTS`` attempts, like ``ft_pct``;
* ``min_share``: the share of the minutes of his team he plays (the PIE of a game depends on it);
* ``adv``: Usg%, ORtg, DRtg, NetRtg, 3Pr and PIE% of the season with the web's formulas (``live_core.boxscore.figures``, the same code as the box score of the game) over his
  season totals and those of his team and of its opponents (200 team minutes per game, as the web).

``live_core.boxscore`` compares the game with them; a package without them leaves those columns without colour.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, Optional

from src.live_core.boxscore import figures, valuation, valuation_gross, web_player, web_team
from src.live_core.four_factors import possessions

SEASON_ADV_KEYS = ("usage", "orating", "drating", "net_rtg", "three_pr", "pie")
SHOT_PRIOR_ATTEMPTS = 10                      # attempts of weight the league percentage has when shrinking a player's (as the free throws)
DEFAULT_SHOOTING = {"fg2": 0.48, "fg": 0.42}  # league percentages when nobody has shot yet (placeholders)


def league_shooting(stats: Iterable[Dict[str, int]]) -> Dict[str, float]:
    """Two-point and field-goal percentages of the league's players (``DEFAULT_SHOOTING`` without attempts)."""
    made = {"fg2": 0, "fg": 0}
    attempted = {"fg2": 0, "fg": 0}
    for s in stats:
        made["fg2"] += s["fg2m"]
        attempted["fg2"] += s["fg2a"]
        made["fg"] += s["fg2m"] + s["fg3m"]
        attempted["fg"] += s["fg2a"] + s["fg3a"]
    return {k: made[k] / attempted[k] if attempted[k] else DEFAULT_SHOOTING[k] for k in made}


def season_context(sums: Optional[Dict[str, Dict[str, int]]], games: int, league: Dict[str, float]) -> Dict[str, Any]:
    """What the season figures of the players of a team need: its season totals and its opponents' as the web reads them (``web_team``), its games and the league."""
    if not sums or not games or "fg2m" not in sums.get("for", {}) or "fg2m" not in sums.get("against", {}):
        return {"games": games, "league": league}
    teams = {side: web_team(sums[side], sums[side].get("pf", 0), possessions(sums[side]), games=games) for side in ("for", "against")}
    return {"games": games, "league": league, "team": teams["for"], "rival": teams["against"]}


def _shrunk(made: int, attempted: int, league: float) -> float:
    return round((made + SHOT_PRIOR_ATTEMPTS * league) / (attempted + SHOT_PRIOR_ATTEMPTS), 4)


def season_figures(stats: Dict[str, int], seconds: int, pf: int, fd: int, pm: int, games: int, context: Dict[str, Any]) -> Dict[str, Any]:
    """The reference of the box score for a player with ``stats`` in ``seconds`` of ``games`` matches (``context``: ``season_context`` of his team)."""
    if seconds <= 0:
        return {}
    p = {"stats": stats, "minutes": seconds, "pts": 2 * stats["fg2m"] + 3 * stats["fg3m"] + stats["ftm"], "pf": pf, "fd": fd}
    scale, league = 2400 / seconds, context["league"]
    out: Dict[str, Any] = {
        "fd_per40": round(fd * scale, 3), "pm_per40": round(pm * scale, 3),
        "val_per40": round(valuation(p) * scale, 3), "val_gross_per40": round(valuation_gross(p) * scale, 3),
        "fg2_pct": _shrunk(stats["fg2m"], stats["fg2a"], league["fg2"]),
        "fg_pct": _shrunk(stats["fg2m"] + stats["fg3m"], stats["fg2a"] + stats["fg3a"], league["fg"]),
    }
    if context.get("games"):
        out["min_share"] = round(seconds / (context["games"] * 2400), 4)
    if "team" in context:
        adv = figures(web_player(p, games), context["team"], context["rival"])
        out["adv"] = {k: (round(adv[k], 2) if adv[k] is not None else None) for k in SEASON_ADV_KEYS}
    return out
