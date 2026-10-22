"""Lineup rules: the minimum of "formación" players on court (illegal lineup).

The competition requires at least ``formation_min_on_court`` formación players on court at all times; otherwise the
lineup is illegal. Who is a formación player comes from the FEB roster stored in the package (``tables.roster``, see
``roster_fetcher``). Two kinds of doubt, resolved in opposite ways: the ALERT fires only when the lineup is definitely
wrong (a player the roster does not know counts as formación), and the RECOMMENDER never proposes a change that might
break the minimum (an unknown player does not count). The rule watches BOTH teams (issue #322: a critical alert for whoever
breaks it, ours or the rival's); a team whose roster the package does not have is not watched.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .advice_types import Advice, RuleContext
from .config import RuleConfig
from .lexicon import other, pronoun

LINEUP_SIZE = 5
REARM_S = 180   # an unfixed illegal lineup is said again after this many game-seconds


def roster_known(roster: Dict[str, Dict[str, Any]], team_id: Optional[str]) -> bool:
    """True when the roster has entries of ``team_id`` (a roster of another team, or none, says nothing about it)."""
    return any(e.get("team_id") == team_id for e in (roster or {}).values())


def formation_counts(snap: Dict[str, Any], team_id: str, roster: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """The team's players on court (sorted ids), how many are formación, and how many the roster does not settle."""
    ids = sorted(pid for pid, p in (snap.get("players") or {}).items() if p["team_id"] == team_id and p["on_court"])
    marks = [(roster.get(pid) or {}).get("formacion") for pid in ids]
    yes = sum(1 for m in marks if m is True)
    return {"ids": ids, "players": len(ids), "yes": yes, "unknown": sum(1 for m in marks if m is None)}


def _illegal_lineup(snap: Dict[str, Any], ctx: RuleContext, team_id: Optional[str], own: bool) -> List[Advice]:
    """The alert for ``team_id`` when its lineup is definitely illegal (nothing when its roster is not in the package)."""
    minimum = ctx.config.formation_min_on_court
    if not team_id or not roster_known(ctx.roster, team_id):
        return []
    counts = formation_counts(snap, team_id, ctx.roster)
    # a substitution is two lines: with fewer than 5 on court the lineup is not complete yet
    if counts["players"] != LINEUP_SIZE or counts["yes"] + counts["unknown"] >= minimum:
        return []
    name = ((snap.get("teams") or {}).get(team_id) or {}).get("name") or ("tu equipo" if own else "el rival")
    who = f"de {name}"
    advice = "Corregirlo con el próximo cambio." if own else "Valorar avisar a la mesa."
    return [Advice(
        key=("formation:" if own else "rival_formation:") + "-".join(counts["ids"]),
        id="formation_lineup" if own else "rival_formation_lineup", severity="critical", category="alineacion",
        message=f"Alineación indebida {who}: solo {counts['yes']} de formación en pista (mínimo {minimum}). {advice}",
        evidence={"team_id": team_id, "on_court_formation": counts["yes"], "unknown": counts["unknown"], "minimum": minimum,
                  "lineup": counts["ids"]},
        rearm_s=REARM_S, confirm=ctx.config.formation_confirm_polls,
    )]


def formation_rule(snap: Dict[str, Any], ctx: RuleContext) -> List[Advice]:
    """Critical alert for EACH team whose lineup is illegal (issue #322): ours, and the rival's when the package has its roster."""
    if ctx.config.formation_min_on_court <= 0:
        return []
    return _illegal_lineup(snap, ctx, ctx.own_team_id, True) + _illegal_lineup(snap, ctx, ctx.rival_team_id, False)


def departure_note(snap: Dict[str, Any], own_team_id: str, roster: Dict[str, Dict[str, Any]], config: RuleConfig,
                   pid: str) -> Optional[str]:
    """Warning for an alert that asks to take a formación player off: without them the lineup is at the minimum."""
    minimum = config.formation_min_on_court
    player = (snap.get("players") or {}).get(pid)
    if minimum <= 0 or not roster_known(roster, own_team_id) or not player or not player["on_court"]:
        return None
    if (roster.get(pid) or {}).get("formacion") is not True:
        return None
    yes = formation_counts(snap, own_team_id, roster)["yes"]
    if yes > minimum:
        return None
    return (f"Ojo: {player['name'].strip()} es de formación y sin {pronoun(config)} en pista solo quedarían {yes - 1} de formación "
            f"(mínimo {minimum}): el cambio debe ser por {other(config)} de formación.")
