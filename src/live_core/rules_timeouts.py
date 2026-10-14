"""Timeout budget at the end of the game (issue #245, F2).

FIBA: three timeouts in the second half, at most two of them in the last 2:00 of the 4th period (``timeouts``). If the own team
still has all three when the last two minutes are near, one of them will be lost unless it is used before: warn and propose
it. If the rival has none left in a close finish, the last minutes can be pressed without fear of a timeout.
"""

from __future__ import annotations

from typing import Any, Dict, List

from .advice_types import Advice, RuleContext
from .proposals import tactic_proposal, timeout_proposal
from .timeouts import LAST_WINDOW_S, SECOND_HALF, timeouts_left

LAST_PERIOD = 4


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
                message="El rival se ha quedado sin tiempos muertos en un final igualado: presionar hasta el final.",
                evidence={"margin": margin, "remaining_s": remaining, "team_id": rival},
                proposal=[tactic_proposal("Presionar: el rival no puede parar el partido")]))
    return out
