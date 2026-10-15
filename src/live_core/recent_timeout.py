"""No timeout right after one (issue #318): when the own team called a timeout a moment ago, an alert that proposes another one
gives a tactical or a rotation change instead. The alert itself stays (the problem is still there); only what it recommends changes:
the ``timeout`` proposal is dropped, the wording that says "valorar tiempo muerto" says that there was one, and a tactic proposal
takes its place. Standard library only."""

from __future__ import annotations

import dataclasses
from typing import Any, Dict

from .advice_types import Advice
from .config import RuleConfig
from .proposals import tactic_proposal
from .timeouts import timeout_within

# the sentences of the rules (rules_run, rules_flow) that recommend a timeout, and what they say after a recent one
_REWRITES = (
    ("Valorar tiempo muerto o cambio de sistema.", "Ya hubo un tiempo muerto hace poco: valorar un cambio de sistema o de rotación."),
    ("Valorar tiempo muerto.", "Ya hubo un tiempo muerto hace poco: valorar un cambio táctico o de rotación."),
)
TACTIC = "Hace poco que se pidió tiempo muerto: probar un cambio táctico o de rotación"


def adapt_for_recent_timeout(advice: Advice, snapshot: Dict[str, Any], own_team_id: str, config: RuleConfig) -> Advice:
    """``advice`` without a timeout proposal when the own team called one in the last ``config.timeout_recent_s`` game-seconds."""
    if config.timeout_recent_s <= 0 or not timeout_within(snapshot, own_team_id, config.timeout_recent_s):
        return advice
    message = advice.message
    for old, new in _REWRITES:
        message = message.replace(old, new)
    had_timeout = any(p.get("type") == "timeout" for p in advice.proposal)
    if not had_timeout and message == advice.message:
        return advice
    proposal = [p for p in advice.proposal if p.get("type") != "timeout"]
    if had_timeout:
        proposal.append(tactic_proposal(TACTIC))
    return dataclasses.replace(advice, message=message, proposal=proposal)
