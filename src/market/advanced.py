"""Advanced figures of the Talent rows (B2, #878): usage, ORtg, DRtg, net rating, AST%, TOV%, STL%, BLK%, REB% and PIE of a player in the context of HIS team.

The formulas are the ones of the Players page (``live_core.advanced_stats``, standard library, which the browser reproduces with parity vectors) and the rounding is the service's
(``PlayerStatsService._enrich_with_advanced_stats``): one decimal, two for PIE. What this module adds is the context from the contract rows that ``local_data.export`` already makes:
the team's season totals and what its opponents did against it, summed over the games of the competition, as ``frontend/src/localdata/aggregateTeams.ts`` does. A transfer is two rows, each
with its own team's context; a team with no context gives the zeros of the page (#647).
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, Iterable, List, Mapping, Tuple

from src.live_core.advanced_stats import AdvancedStatsCalculator

ADVANCED_FIELDS = ("usage_pct", "orating", "drating", "net_rtg", "ast_pct", "tov_pct_adv", "stl_pct", "blk_pct", "drb_pct", "orb_pct", "pie")
_PLAYER_KEYS = ("pts", "p1m", "p1a", "p2m", "p2a", "p3m", "p3a", "assist", "ro", "rd", "rt", "st", "to", "bs", "pf", "rf", "val", "pllss")
_SUMMED = ("points", "received", "fg2m", "fg2a", "fg3m", "fg3a", "ftm", "fta", "def", "off", "oppDef", "oppOff", "assists", "steals", "turnovers", "blocks", "possessions", "oppPossessions", "reb")

Context = Tuple[Dict[str, Any], Dict[str, Any]]


def _own(r: Mapping[str, Any]) -> Dict[str, float]:
    return {"points": r["points"], "received": r["opponent_points"], "fg2m": r["fg2_made"], "fg2a": r["fg2_attempts"], "fg3m": r["fg3_made"], "fg3a": r["fg3_attempts"],
            "ftm": r["ft_made"], "fta": r["ft_attempts"], "def": r["def_rebounds"], "off": r["off_rebounds"], "oppDef": r["opponent_def_rebounds"], "oppOff": r["opponent_off_rebounds"],
            "assists": r["assists"], "steals": r["steals"], "turnovers": r["turnovers"], "blocks": r["blocks"], "possessions": r["possessions"],
            "oppPossessions": r["opponent_possessions"], "reb": r.get("total_rebounds") or 0}


def _rival(r: Mapping[str, Any]) -> Dict[str, float]:
    """What the opponents did against the team: its figures are the measured ones and the team's own become the references (the web's ``rival``)."""
    return {"points": r["opponent_points"], "received": r["points"], "fg2m": r["opponent_fg2_made"], "fg2a": r["opponent_fg2_attempts"], "fg3m": r["opponent_fg3_made"],
            "fg3a": r["opponent_fg3_attempts"], "ftm": r["opponent_ft_made"], "fta": r["opponent_ft_attempts"], "def": r["opponent_def_rebounds"], "off": r["opponent_off_rebounds"],
            "oppDef": r["def_rebounds"], "oppOff": r["off_rebounds"], "assists": r["opponent_assists"], "steals": r["opponent_steals"], "turnovers": r["opponent_turnovers"],
            "blocks": r["opponent_blocks"], "possessions": r["opponent_possessions"], "oppPossessions": r["possessions"], "reb": r.get("opponent_total_rebounds") or 0}


def _derive(games: int, s: Mapping[str, float], fbcyl: bool) -> Dict[str, Any]:
    """The keys of the season table of a team that the calculator reads (``aggregateTeams.ts`` ``derive``)."""
    return {"total_games": games, "points_scored": s["points"], "fg2_made": s["fg2m"], "fg2_attempted": s["fg2a"], "fg3_made": s["fg3m"], "fg3_attempted": s["fg3a"],
            "ft_made": s["ftm"], "ft_attempted": s["fta"], "rebounds_def": s["def"], "rebounds_off": s["off"], "assists": s["assists"], "steals": s["steals"],
            "turnovers": s["turnovers"], "blocks": s["blocks"], "total_rebounds": s["reb"] if fbcyl else s["def"] + s["off"],
            "possessions_per_game": s["possessions"] / games if games else 0}


def team_context(team_rows: Iterable[Mapping[str, Any]]) -> Dict[str, Context]:
    """``{team_id: (team season table, opponents' season table)}`` from the team rows of the games of one competition."""
    by_team: Dict[str, List[Mapping[str, Any]]] = defaultdict(list)
    for row in team_rows:
        by_team[str(row["team_id"])].append(row)
    out: Dict[str, Context] = {}
    for team, rows in sorted(by_team.items()):
        fbcyl = rows[0].get("fouls") is not None                              # FBCYL reports its own total of rebounds and fouls
        tables = []
        for side in (_own, _rival):
            sums = {k: 0.0 for k in _SUMMED}
            for r in rows:
                for k, v in side(r).items():
                    sums[k] += v
            tables.append(_derive(len(rows), sums, fbcyl))
        out[team] = (tables[0], tables[1])
    return out


def _player(row: Mapping[str, Any]) -> Dict[str, Any]:
    return {"games_played": row["games"], "total_minutes": row["minutes"] / 60, **{f"total_{k}": row.get(k, 0) for k in _PLAYER_KEYS}}


def add_advanced(rows: Iterable[Mapping[str, Any]], context: Mapping[str, Context]) -> List[Dict[str, Any]]:
    """The rows with the advanced figures of their team's context; the inputs are not changed."""
    out = []
    for row in rows:
        ctx = context.get(str(row["team_id"]))
        if not ctx:
            out.append({**row, **{f: 0.0 for f in ADVANCED_FIELDS}})
            continue
        adv = AdvancedStatsCalculator.calculate_all_advanced_stats(_player(row), ctx[0], ctx[1])
        out.append({**row, "usage_pct": round(adv["usage"], 1), "orating": round(adv["orating"], 1), "drating": round(adv["drating"], 1), "net_rtg": round(adv["net_rtg"], 1),
                    "ast_pct": round(adv["ast_pct"], 1), "tov_pct_adv": round(adv["tov_pct"], 1), "stl_pct": round(adv["stl_pct"], 1), "blk_pct": round(adv["blk_pct"], 1),
                    "drb_pct": round(adv["drb_pct"], 1), "orb_pct": round(adv["orb_pct"], 1), "pie": round(adv["pie"], 2)})
    return out
