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
from .four_factors import FT_POSSESSION_COST, possessions as estimated_possessions

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
_PPP_SPREAD = 1.15         # the points of one possession are 0, 1, 2 or 3 around ~0.9: the spread of a rating is 100 x this / sqrt(possessions)


def web_player(p: Dict[str, Any], games: int = 1) -> Dict[str, Any]:
    """A player with the keys the web calculators read: one game of the live state (``stats``, ``minutes`` in seconds, ``pts``, ``pf``), or the season totals in that shape."""
    st = p["stats"]
    return {"games_played": games, "total_minutes": p["minutes"] / 60, "total_pts": p["pts"], "total_p2m": st["fg2m"], "total_p2a": st["fg2a"], "total_p3m": st["fg3m"], "total_p3a": st["fg3a"],
            "total_p1m": st["ftm"], "total_p1a": st["fta"], "total_ro": st["orb"], "total_rd": st["drb"], "total_assist": st["ast"], "total_to": st["tov"], "total_st": st["stl"],
            "total_bs": st["blk"], "total_pf": p["pf"]}


def web_team(s: Dict[str, int], pf: int, possessions: float, games: int = 1, minutes: float = 0.0) -> Dict[str, Any]:
    """A team with the keys the web calculators read: a game in progress (``minutes`` its players have played) or a season of ``games`` (200 minutes each, as the web)."""
    return {"total_games": games, **({"team_minutes": minutes} if minutes else {}), "fg2_made": s["fg2m"], "fg2_attempted": s["fg2a"], "fg3_made": s["fg3m"],
            "fg3_attempted": s["fg3a"], "ft_made": s["ftm"], "ft_attempted": s["fta"], "rebounds_off": s["orb"], "rebounds_def": s["drb"], "total_rebounds": s["orb"] + s["drb"],
            "assists": s["ast"], "steals": s["stl"], "blocks": s["blk"], "turnovers": s["tov"] + s.get("tov_team", 0), "personal_fouls": pf, "points_scored": s["pts"],
            "possessions_per_game": possessions / games if games else possessions}


def _possessions(snapshot: Dict[str, Any], team_id: str) -> float:
    """The exact possessions of the tracker when it has them, else the estimate."""
    counted = ((snapshot.get("possessions") or {}).get("counted") or {}).get(team_id)
    return counted if counted else estimated_possessions(snapshot["teams"][team_id]["stats"])


def _web_team(snapshot: Dict[str, Any], team_id: str, players: List[Dict[str, Any]]) -> Dict[str, Any]:
    """A live team for the web calculators; its minutes are what its players have played and its possessions the exact ones when the tracker has them."""
    return web_team(snapshot["teams"][team_id]["stats"], sum(p["pf"] for p in players), _possessions(snapshot, team_id), minutes=sum(p["minutes"] for p in players) / 60)


def valuation(p: Dict[str, Any]) -> int:
    st = p["stats"]
    made, attempted = st["fg2m"] + st["fg3m"], st["fg2a"] + st["fg3a"]
    return (p["pts"] + st["orb"] + st["drb"] + st["ast"] + st["stl"] + st["blk"] + p.get("fd", 0)
            - (attempted - made) - (st["fta"] - st["ftm"]) - st["tov"] - p["pf"])


def _advanced(p: Dict[str, Any], team: Dict[str, Any], rival: Dict[str, Any], cfg: RuleConfig) -> Dict[str, Optional[float]]:
    if p["minutes"] < cfg.boxscore_min_seconds:
        return {key: None for key in ADVANCED_KEYS}
    return figures(web_player(p), team, rival)


def figures(web: Dict[str, Any], team: Dict[str, Any], rival: Dict[str, Any]) -> Dict[str, Optional[float]]:
    """The 15 advanced figures of the web for a player (``web_player``) and his team and its rival (``web_team``): of a game, or of a season (the package's reference)."""
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
            out["ftm"] = _binomial(st["ftm"], st["fta"], float(baseline["ft_pct"]), cfg)
        fga = st["fg2a"] + st["fg3a"]
        if fga:
            out["efg"] = _clamp(((st["fg2m"] + 1.5 * st["fg3m"]) / fga - float(baseline["rates"]["efg"])) / (_EFG_SPREAD / math.sqrt(fga + 1)), cfg)
            out["ftr"] = _clamp((st["fta"] / fga - float(baseline["rates"]["ftr"])) / (_EFG_SPREAD / math.sqrt(fga + 1)), cfg)
            shots = fga + FT_POSSESSION_COST * st["fta"]
            expected_ts = float(baseline["impact40"]["pts"]) / (2 * (baseline["rates"]["fg2a40"] + baseline["rates"]["fg3a40"] + FT_POSSESSION_COST * baseline["impact40"]["fta"]))
            out["ts"] = _clamp((p["pts"] / (2 * shots) - expected_ts) / (_EFG_SPREAD / math.sqrt(shots + 1)), cfg)
    except (KeyError, TypeError):
        return {}                # a baseline without what is compared: the same as having none
    return out


def _binomial(made: float, attempts: float, chance: float, cfg: RuleConfig) -> float:
    """Made against what a ``chance`` of making each attempt expects, with the binomial noise."""
    return _clamp((made - attempts * chance) / math.sqrt(attempts * chance * (1 - chance) + 1), cfg)


def _share(game: float, usual: float, n: float, cfg: RuleConfig) -> float:
    """A percentage that is a share of ``n`` things (plays, attempts) against its usual one."""
    q = min(0.99, max(0.01, usual / 100))
    return _clamp((game - usual) / 100 / math.sqrt(q * (1 - q) / (n + 1)), cfg)


def valuation_gross(p: Dict[str, Any]) -> int:
    """What adds and what subtracts in the valuation, all added up: its noise."""
    st = p["stats"]
    return (p["pts"] + st["orb"] + st["drb"] + st["ast"] + st["stl"] + st["blk"] + p.get("fd", 0) + st["fg2a"] - st["fg2m"] + st["fg3a"] - st["fg3m"] + st["fta"] - st["ftm"]
            + st["tov"] + p["pf"])


def _rating_spreads(p: Dict[str, Any], ctx: Dict[str, float]) -> Tuple[float, float]:
    """Spread of the ORtg (his plays) and of the DRtg (the rival's possessions while he is on court) of a game."""
    st, share = p["stats"], p["minutes"] / max(ctx["team_seconds"] / 5, 1.0)
    plays = st["fg2a"] + st["fg3a"] + FT_POSSESSION_COST * st["fta"] + st["tov"]
    return 100 * _PPP_SPREAD / math.sqrt(plays + 1), 100 * _PPP_SPREAD / math.sqrt(ctx["rival_poss"] * share + 1)


def _season_columns(p: Dict[str, Any], b: Dict[str, Any], adv: Dict[str, Optional[float]], ctx: Dict[str, float],
                    cfg: RuleConfig) -> Dict[str, Callable[[], Optional[float]]]:
    """The columns compared with the player's SEASON figures of the package (feedback 0.5.2; ``live_prep.season_figures``), one function each: a package of before lacks
    them, and a figure the game has not got yet (no shots, a rating without what it divides by) is None."""
    st, scale, season = p["stats"], p["minutes"] / 2400.0, b.get("adv") or {}
    share = p["minutes"] / max(ctx["team_seconds"] / 5, 1.0)                    # of the minutes of his team
    fga = st["fg2a"] + st["fg3a"]
    spread_o, spread_d = _rating_spreads(p, ctx)

    def count(actual: float, per40: float, noise40: float) -> float:
        return _clamp((actual - per40 * scale) / math.sqrt(noise40 * scale + 1), cfg)

    def known(key: str) -> bool:
        return adv.get(key) is not None and season.get(key) is not None

    return {
        "fd": lambda: count(p.get("fd", 0), b["fd_per40"], b["fd_per40"]),
        "val": lambda: count(valuation(p), b["val_per40"], b["val_gross_per40"]),
        "pm": lambda: _clamp((p["pm"] - b["pm_per40"] * scale) / math.sqrt(ctx["game_points"] * p["minutes"] / max(ctx["elapsed"], 1) + 1), cfg),
        "fg2": lambda: _binomial(st["fg2m"], st["fg2a"], b["fg2_pct"], cfg) if st["fg2a"] else None,
        "fg": lambda: _binomial(st["fg2m"] + st["fg3m"], fga, b["fg_pct"], cfg) if fga else None,
        "three_pr": lambda: _share(adv["three_pr"], season["three_pr"], fga, cfg) if known("three_pr") else None,
        "usage": lambda: _share(adv["usage"], season["usage"], ctx["team_plays"] * share, cfg) if known("usage") else None,
        "pie": lambda: _share(adv["pie"], season["pie"] * share / b["min_share"], ctx["game_poss"], cfg) if known("pie") else None,
        "orating": lambda: _clamp((adv["orating"] - season["orating"]) / spread_o, cfg) if known("orating") else None,
        "drating": lambda: _clamp((season["drating"] - adv["drating"]) / spread_d, cfg) if known("drating") else None,      # fewer points let in is good
        "net_rtg": lambda: _clamp((adv["net_rtg"] - season["net_rtg"]) / math.hypot(spread_o, spread_d), cfg) if known("net_rtg") else None,
    }


def _season_deviation(p: Dict[str, Any], baseline: Optional[Dict[str, Any]], adv: Dict[str, Optional[float]], ctx: Dict[str, float],
                      cfg: RuleConfig) -> Dict[str, float]:
    if not baseline or p["minutes"] < cfg.boxscore_min_seconds:
        return {}
    out: Dict[str, float] = {}
    for column, deviation in _season_columns(p, baseline, adv, ctx, cfg).items():
        try:
            value = deviation()
        except (KeyError, TypeError, ZeroDivisionError):
            continue             # a package without this figure of his season: the column stays without colour
        if value is not None:
            out[column] = value
    return out


def _team_deviation(own: Dict[str, int], rival: Dict[str, int], cfg: RuleConfig) -> Dict[str, Optional[float]]:
    """The totals of a team against the RIVAL's (#699; the package has no season average of a team to compare with): the same scale as a player's (sign of good,
    [-1, 1]), noise of a count sqrt(own + rival + 1); the two teams' entries are mirrored. Empty while neither has done anything."""
    if not any(own.values()) and not any(rival.values()):
        return {}
    out: Dict[str, Optional[float]] = {}
    for column, inverted in (("pts", False), ("fg3m", False), ("ftm", False), ("orb", False), ("drb", False), ("reb", False), ("ast", False), ("stl", False), ("blk", False),
                             ("fd", False), ("tov", True), ("pf", True)):
        z = (own[column] - rival[column]) / math.sqrt(own[column] + rival[column] + 1)
        out[column] = _clamp(-z if inverted else z, cfg)
    own_fga, rival_fga = own["fg2a"] + own["fg3a"], rival["fg2a"] + rival["fg3a"]
    if own_fga and rival_fga:
        gap = (own["fg2m"] + 1.5 * own["fg3m"]) / own_fga - (rival["fg2m"] + 1.5 * rival["fg3m"]) / rival_fga
        out["efg"] = _clamp(gap / (_EFG_SPREAD * math.sqrt(1 / (own_fga + 1) + 1 / (rival_fga + 1))), cfg)
    shots = {"fg2": ((own["fg2m"], own["fg2a"]), (rival["fg2m"], rival["fg2a"])),
             "fg": ((own["fg2m"] + own["fg3m"], own_fga), (rival["fg2m"] + rival["fg3m"], rival_fga))}
    for column, ((made, attempted), (theirs_made, theirs)) in shots.items():
        if attempted and theirs:            # the gap of two percentages against the noise of both (pooled)
            pooled = (made + theirs_made) / (attempted + theirs)
            noise = math.sqrt(pooled * (1 - pooled) * (1 / (attempted + 1) + 1 / (theirs + 1)))
            out[column] = _clamp((made / attempted - theirs_made / theirs) / noise, cfg) if noise else 0.0
    out["val"] = _clamp((own["val"] - rival["val"]) / math.sqrt(own["gross"] + rival["gross"] + 1), cfg)
    return out


def _team_counts(snapshot: Dict[str, Any], team_id: str, players: List[Dict[str, Any]]) -> Dict[str, int]:
    s = snapshot["teams"][team_id]["stats"]
    return {**{k: s[k] for k in ("fg2m", "fg2a", "fg3m", "fg3a", "ftm", "orb", "drb", "ast", "stl", "blk", "pts")}, "reb": s["orb"] + s["drb"],
            "tov": s["tov"] + s.get("tov_team", 0), "pf": sum(p["pf"] for p in players), "fd": sum(p.get("fd", 0) for p in players),
            "val": sum(valuation(p) for p in players), "gross": sum(valuation_gross(p) for p in players)}


def _number(player: Dict[str, Any], roster: Optional[Dict[str, Dict[str, Any]]], pid: str, baselines: Optional[Dict[str, Dict[str, Any]]] = None) -> Optional[str]:
    """The jersey number as text, from the best source that has one: the snapshot's (the document's box score, else the one read from the shot chart of the match), the
    ``dorsal`` of the package's roster (FEB's current one), the ``dorsal`` of his last match of the season (``tables.players``; it reaches the players of the reserve team who
    are not in the roster); None when nobody says it (zero is a number)."""
    for value in (player.get("no"), ((roster or {}).get(pid) or {}).get("dorsal"), ((baselines or {}).get(pid) or {}).get("dorsal")):
        if value is not None and str(value).strip() != "":
            return str(value).strip()
    return None


def _context(snapshot: Dict[str, Any], team_id: str, rival_id: str, players: List[Dict[str, Any]]) -> Dict[str, float]:
    """What the season deviations of the players of ``team_id`` measure their game against: the minutes and plays of the team, possessions and points of the game."""
    s, rival = snapshot["teams"][team_id]["stats"], snapshot["teams"][rival_id]["stats"]
    own_poss, rival_poss = _possessions(snapshot, team_id), _possessions(snapshot, rival_id)
    return {"team_seconds": sum(p["minutes"] for p in players), "team_plays": s["fg2a"] + s["fg3a"] + FT_POSSESSION_COST * s["fta"] + s["tov"] + s.get("tov_team", 0),
            "rival_poss": rival_poss, "game_poss": own_poss + rival_poss, "game_points": s["pts"] + rival["pts"], "elapsed": snapshot.get("elapsed") or 0}


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
    contexts = {tid: _context(snapshot, tid, other, by_team[tid]) for tid in teams for other in teams if other != tid} if len(teams) == 2 else {}
    out: Dict[str, Dict[str, Any]] = {}
    for pid, p in snapshot.get("players", {}).items():
        tid = p["team_id"]
        others = [t for t in teams if t != tid]
        team, rival = teams.get(tid), teams[others[0]] if len(others) == 1 and tid in teams else None
        advanced = _advanced(p, team, rival, cfg) if team is not None and rival is not None else {key: None for key in ADVANCED_KEYS}
        dev = _deviation(p, baselines.get(pid), cfg)
        if tid in contexts:
            dev.update(_season_deviation(p, baselines.get(pid), advanced, contexts[tid], cfg))
        out[pid] = {"val": valuation(p), "adv": advanced, "dev": dev, "no": _number(p, roster, pid, baselines)}
    return out


def team_totals(snapshot: Dict[str, Any], cfg: RuleConfig) -> Dict[str, Dict[str, Optional[float]]]:
    """``{team id: deviation}`` of the totals row of each team against the other's (#699); empty for a snapshot that is not the state machine's or with other than two teams."""
    ids = list(snapshot.get("teams") or {})
    if len(ids) != 2 or not all("fg2m" in (snapshot["teams"][t].get("stats") or {}) for t in ids) or not all("stats" in p for p in snapshot.get("players", {}).values()):
        return {}
    counts = {t: _team_counts(snapshot, t, [p for p in snapshot.get("players", {}).values() if p["team_id"] == t]) for t in ids}
    return {ids[0]: _team_deviation(counts[ids[0]], counts[ids[1]], cfg), ids[1]: _team_deviation(counts[ids[1]], counts[ids[0]], cfg)}
