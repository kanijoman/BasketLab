"""Lineup rules: the minimum of "formación" players on court (illegal lineup).

The competition requires at least ``formation_min_on_court`` formación players on court at all times; otherwise the
lineup is illegal. Who is a formación player comes from the FEB roster stored in the package (``tables.roster``, see
``roster_fetcher``). Two kinds of doubt, resolved in opposite ways: the ALERT fires only when the lineup is definitely
wrong (a player the roster does not know counts as formación), and the RECOMMENDER never proposes a change that might
break the minimum (an unknown player does not count). Without the roster of our team nothing is said.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .advice_types import Advice, RuleContext
from .config import RuleConfig

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


def formation_rule(snap: Dict[str, Any], ctx: RuleContext) -> List[Advice]:
    minimum = ctx.config.formation_min_on_court
    if minimum <= 0 or not roster_known(ctx.roster, ctx.own_team_id):
        return []
    counts = formation_counts(snap, ctx.own_team_id, ctx.roster)
    # a substitution is two lines: with fewer than 5 on court the lineup is not complete yet
    if counts["players"] != LINEUP_SIZE or counts["yes"] + counts["unknown"] >= minimum:
        return []
    return [Advice(
        key="formation:" + "-".join(counts["ids"]), id="formation_lineup", severity="critical", category="alineacion",
        message=(f"Alineación indebida: solo {counts['yes']} de formación en pista (mínimo {minimum}). "
                 "Corregirlo con el próximo cambio."),
        evidence={"on_court_formation": counts["yes"], "unknown": counts["unknown"], "minimum": minimum,
                  "lineup": counts["ids"]},
        rearm_s=REARM_S, confirm=ctx.config.formation_confirm_polls,
    )]


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
    return (f"Ojo: {player['name'].strip()} es de formación y sin ella en pista solo quedarían {yes - 1} de formación "
            f"(mínimo {minimum}): el cambio debe ser por otra de formación.")
