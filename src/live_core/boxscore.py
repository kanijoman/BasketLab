"""The box score of the live app (issue #593): valuation, advanced figures and how far each player is from his own average.

* ``val``: the valuation of the FEB PDF without the blocks received (they are not in the feed's lines): points + rebounds + assists + steals + blocks + fouls drawn - missed
  shots - missed free throws - turnovers - fouls committed.
* ``adv``: the 15 advanced figures of the web (``AdvancedStatsCalculator``, the same code: ``advanced_stats``), computed on the game so far: the team minutes are what its
  players have played (``team_minutes``), the opponent possessions the exact ones of the tracker (the estimate of ``four_factors`` without them). ``None`` while a player has
  less than ``boxscore_min_seconds`` of game and when the figure has nothing to be made of (a percentage of shots without shots).
* ``dev``: how far a column is from what the package says the player usually does in the minutes he has played, in [-1, 1] with the sign of GOOD (turnovers and fouls are
  inverted): expected = rate per 40 x seconds / 2400; the noise of a count is sqrt(expected + 1) (the package has the average of a player, not his spread), that of a
  percentage the binomial one; the figure saturates at ``boxscore_z_max`` noises. A column with no comparable average (minutes, plus/minus, 2-point makes, the advanced
  figures) has no entry.
Standard library only (it runs in the tablet).
"""

from __future__ import annotations

import math
from typing import Any, Callable, Dict, List, Optional, Tuple

from .advanced_stats import AdvancedStatsCalculator as Adv
from .config import RuleConfig
from .four_factors import possessions as estimated_possessions

ADVANCED_KEYS = ("usage", "orating", "drating", "net_rtg", "efg", "ts", "ftr", "three_pr", "ast_pct", "tov_pct", "stl_pct", "blk_pct", "drb_pct", "orb_pct", "pie")

# column -> (where in the player's baseline its rate per 40 minutes is, is more of it bad?)
_COUNT_RATES: Dict[str, Tuple[Callable[[Dict[str, Any]], Optional[float]], bool]] = {
    "pts": (lambda b: b["impact40"]["pts"], False),
    "fg3m": (lambda b: b["impact40"]["fg3m"], False),
    "orb": (lambda b: b["rates"]["orb40"], False),
    "drb": (lambda b: b["rates"]["drb40"], False),
    "ast": (lambda b: b["rates"]["ast40"], False),
    "stl": (lambda b: b["rates"]["stl40"], False),
    "blk": (lambda b: b["rates"]["blk40"], False),
    "tov": (lambda b: b["rates"]["tov40"], True),
    "pf": (lambda b: b["pf_per40"], True),
}
_EFG_SPREAD = 0.5          # the points per shot of one attempt are 0, 1 or 1.5 around its mean: about half a unit


def _web_player(p: Dict[str, Any]) -> Dict[str, Any]:
    """A live player with the keys the web calculators read (season totals of one game)."""
    st = p["stats"]
    return {"games_played": 1, "total_minutes": p["minutes"] / 60, "total_pts": p["pts"], "total_p2m": st["fg2m"], "total_p2a": st["fg2a"], "total_p3m": st["fg3m"], "total_p3a": st["fg3a"],
            "total_p1m": st["ftm"], "total_p1a": st["fta"], "total_ro": st["orb"], "total_rd": st["drb"], "total_assist": st["ast"], "total_to": st["tov"], "total_st": st["stl"],
            "total_bs": st["blk"], "total_pf": p["pf"]}


def _web_team(snapshot: Dict[str, Any], team_id: str, players: List[Dict[str, Any]]) -> Dict[str, Any]:
    """A live team with the keys the web calculators read; its minutes are what its players have played and its possessions the exact ones when the tracker has them."""
    s = snapshot["teams"][team_id]["stats"]
    counted = ((snapshot.get("possessions") or {}).get("counted") or {}).get(team_id)
    return {"total_games": 1, "team_minutes": sum(p["minutes"] for p in players) / 60, "fg2_made": s["fg2m"], "fg2_attempted": s["fg2a"], "fg3_made": s["fg3m"], "fg3_attempted": s["fg3a"],
            "ft_made": s["ftm"], "ft_attempted": s["fta"], "rebounds_off": s["orb"], "rebounds_def": s["drb"], "total_rebounds": s["orb"] + s["drb"], "assists": s["ast"],
            "steals": s["stl"], "blocks": s["blk"], "turnovers": s["tov"] + s.get("tov_team", 0), "personal_fouls": sum(p["pf"] for p in players), "points_scored": s["pts"],
            "possessions_per_game": counted if counted else estimated_possessions(s)}


def _valuation(p: Dict[str, Any]) -> int:
    st = p["stats"]
    made, attempted = st["fg2m"] + st["fg3m"], st["fg2a"] + st["fg3a"]
    return (p["pts"] + st["orb"] + st["drb"] + st["ast"] + st["stl"] + st["blk"] + p.get("fd", 0)
            - (attempted - made) - (st["fta"] - st["ftm"]) - st["tov"] - p["pf"])


def _advanced(p: Dict[str, Any], team: Dict[str, Any], rival: Dict[str, Any], cfg: RuleConfig) -> Dict[str, Optional[float]]:
    if p["minutes"] < cfg.boxscore_min_seconds:
        return {key: None for key in ADVANCED_KEYS}
    web = _web_player(p)
    out: Dict[str, Optional[float]] = {
        "usage": Adv.calculate_usage_percentage(web, team), "orating": Adv.calculate_offensive_rating(web, team, rival), "drating": Adv.calculate_defensive_rating(web, team, rival),
        "net_rtg": Adv.calculate_net_rating(web, team, rival), "efg": Adv.calculate_effective_fg_percentage(web), "ts": Adv.calculate_true_shooting_percentage(web),
        "ftr": Adv.calculate_ftr(web), "three_pr": Adv.calculate_3pr(web), "ast_pct": Adv.calculate_assist_percentage(web, team), "tov_pct": Adv.calculate_turnover_percentage(web),
        "stl_pct": Adv.calculate_steal_percentage(web, team, rival), "blk_pct": Adv.calculate_block_percentage(web, team, rival),
        "drb_pct": Adv.calculate_rebound_percentage(web, team, rival), "orb_pct": Adv.calculate_rebound_percentage(web, team, rival, is_offensive=True),
        "pie": Adv.calculate_pie(web, team, rival),
    }
    fga, fta, plays = web["total_p2a"] + web["total_p3a"], web["total_p1a"], web["total_p2a"] + web["total_p3a"] + web["total_p1a"] + web["total_to"]
    for key in ("efg", "ftr", "three_pr"):
        if not fga:
            out[key] = None
    if not fga and not fta:
        out["ts"] = None
    if not plays:
        out["tov_pct"] = None
    for key in ("orating", "drating"):
        if out[key] == 100.0:           # the sentinel of the formula when something it divides by is missing
            out[key] = None
    if out["orating"] is None or out["drating"] is None:
        out["net_rtg"] = None
    return out


def _clamp(z: float, cfg: RuleConfig) -> float:
    return max(-1.0, min(1.0, z / cfg.boxscore_z_max))


def _deviation(p: Dict[str, Any], baseline: Optional[Dict[str, Any]], cfg: RuleConfig) -> Dict[str, Optional[float]]:
    if not baseline or p["minutes"] < cfg.boxscore_min_seconds:
        return {}
    scale, st = p["minutes"] / 2400.0, p["stats"]
    actual = {**st, "pts": p["pts"], "pf": p["pf"]}
    out: Dict[str, Optional[float]] = {}
    try:
        for column, (rate, inverted) in _COUNT_RATES.items():
            expected = float(rate(baseline)) * scale
            z = (actual[column] - expected) / math.sqrt(expected + 1)
            out[column] = _clamp(-z if inverted else z, cfg)
        out["reb"] = _clamp((st["orb"] + st["drb"] - (baseline["rates"]["orb40"] + baseline["rates"]["drb40"]) * scale) / math.sqrt((baseline["rates"]["orb40"] + baseline["rates"]["drb40"]) * scale + 1), cfg)
        if st["fta"]:
            chance = float(baseline["ft_pct"])
            out["ftm"] = _clamp((st["ftm"] - st["fta"] * chance) / math.sqrt(st["fta"] * chance * (1 - chance) + 1), cfg)
        fga = st["fg2a"] + st["fg3a"]
        if fga:
            out["efg"] = _clamp(((st["fg2m"] + 1.5 * st["fg3m"]) / fga - float(baseline["rates"]["efg"])) / (_EFG_SPREAD / math.sqrt(fga + 1)), cfg)
    except (KeyError, TypeError):
        return {}                # a baseline without what is compared: the same as having none
    return out


def _number(player: Dict[str, Any], roster: Optional[Dict[str, Dict[str, Any]]], pid: str, baselines: Optional[Dict[str, Dict[str, Any]]] = None) -> Optional[str]:
    """The jersey number as text, from the best source that has one: the snapshot's (the document's box score, else the one read from the shot chart of the match), the
    ``dorsal`` of the package's roster (FEB's current one), the ``dorsal`` of his last match of the season (``tables.players``; it reaches the players of the reserve team who
    are not in the roster); None when nobody says it (zero is a number)."""
    for value in (player.get("no"), ((roster or {}).get(pid) or {}).get("dorsal"), ((baselines or {}).get(pid) or {}).get("dorsal")):
        if value is not None and str(value).strip() != "":
            return str(value).strip()
    return None


def build(snapshot: Dict[str, Any], baselines: Dict[str, Dict[str, Any]], cfg: RuleConfig, roster: Optional[Dict[str, Dict[str, Any]]] = None) -> Dict[str, Dict[str, Any]]:
    """``{player id: {"val", "adv", "dev", "no"}}`` for every player of the snapshot. ``baselines``: player id -> season baseline of the package (own and rival players together);
    ``roster``: the package's roster (jersey numbers)."""
    if not all("fg2m" in (team.get("stats") or {}) for team in snapshot["teams"].values()) or not all("stats" in p for p in snapshot.get("players", {}).values()):
        return {}            # not a snapshot of the state machine (a hand-written one): there is nothing to count
    by_team: Dict[str, List[Dict[str, Any]]] = {tid: [] for tid in snapshot["teams"]}
    for p in snapshot.get("players", {}).values():
        if p["team_id"] in by_team:
            by_team[p["team_id"]].append(p)
    teams = {tid: _web_team(snapshot, tid, players) for tid, players in by_team.items()}
    out: Dict[str, Dict[str, Any]] = {}
    for pid, p in snapshot.get("players", {}).items():
        tid = p["team_id"]
        others = [t for t in teams if t != tid]
        team, rival = teams.get(tid), teams[others[0]] if len(others) == 1 and tid in teams else None
        advanced = _advanced(p, team, rival, cfg) if team is not None and rival is not None else {key: None for key in ADVANCED_KEYS}
        out[pid] = {"val": _valuation(p), "adv": advanced, "dev": _deviation(p, baselines.get(pid), cfg), "no": _number(p, roster, pid, baselines)}
    return out
