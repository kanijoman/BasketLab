"""Timeout budget at the end of the game (issue #245, F2).

FIBA: three timeouts in the second half, at most two of them in the last 2:00 of the 4th period (``timeouts``). If the own team
still has all three when the last two minutes are near, one of them will be lost unless it is used before: warn and propose
it. If the rival has none left in a close finish, the last minutes can be pressed without fear of a timeout.

``first_half_timeouts`` (issue #427) is the same at the break: the two timeouts of the first half are not carried over, and the
coaches of the LF Challenge spend them in the last 2:00 of the 2nd period (516 of 1.139) while 37 % of the halves use none.
"""

from __future__ import annotations

from typing import Any, Dict, List

from .advice_types import Advice, RuleContext
from .proposals import tactic_proposal, timeout_proposal
from .timeouts import FIRST_HALF, LAST_WINDOW_S, SECOND_HALF, timeouts_left

LAST_PERIOD = 4
FIRST_HALF_END = 2


def timeout_budget_rule(snap: Dict[str, Any], ctx: RuleContext) -> List[Advice]:
    if snap["period"] != LAST_PERIOD:
        return []
    cfg, remaining, out = ctx.config, snap["remaining"], []
    left = timeouts_left(snap, ctx.own_team_id)
    if LAST_WINDOW_S < remaining <= cfg.timeout_budget_s and left >= SECOND_HALF:
        out.append(Advice(
            key=f"timeout_budget:{LAST_PERIOD}", id="timeout_budget", severity="warning", category="gestion",
            message=(f"Quedan {left} tiempos muertos y en el último {LAST_WINDOW_S // 60}:{LAST_WINDOW_S % 60:02d} solo se pueden "
                     "pedir 2: usar uno antes de entonces o se pierde."),
            evidence={"timeouts_left": left, "remaining_s": remaining}, proposal=[timeout_proposal(left)]))
    score, rival = snap.get("score") or {}, ctx.rival_team_id
    if rival and rival in score and ctx.own_team_id in score and remaining <= cfg.timeout_budget_s:
        margin = score[ctx.own_team_id] - score[rival]
        if timeouts_left(snap, rival) == 0 and abs(margin) <= cfg.timeout_pressure_margin:
            out.append(Advice(
                key=f"rival_no_timeouts:{LAST_PERIOD}", id="rival_no_timeouts", severity="info", category="rival",
                message="El rival se ha quedado sin tiempos muertos en un final igualado.",
                evidence={"margin": margin, "remaining_s": remaining, "team_id": rival},
                proposal=[tactic_proposal("Presionar: el rival no puede parar el partido")]))
    return out


def first_half_timeouts_rule(snap: Dict[str, Any], ctx: RuleContext) -> List[Advice]:
    """Timeouts of the first half that are still there when it is about to end: they are lost at the break."""
    if snap["period"] != FIRST_HALF_END or snap["remaining"] > ctx.config.half_close_s:
        return []
    left = timeouts_left(snap, ctx.own_team_id)
    if left <= 0:
        return []
    clock = f"{snap['remaining'] // 60}:{snap['remaining'] % 60:02d}"
    return [Advice(
        key=f"first_half_timeouts:{FIRST_HALF_END}", id="first_half_timeouts", severity="warning" if left >= FIRST_HALF else "info",
        category="gestion",
        message=(f"Quedan {left} tiempos muertos y no pasan al descanso" if left > 1 else "Queda 1 tiempo muerto y no pasa al descanso")
                + f" ({clock}): usar uno para preparar la última posesión de la parte.",
        evidence={"timeouts_left": left, "remaining_s": snap["remaining"]}, proposal=[timeout_proposal(left)])]
