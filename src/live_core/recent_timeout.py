"""No timeout right after one (issue #318): when the own team called a timeout a moment ago, an alert that proposes another one
gives a tactical or a rotation change instead. The alert itself stays (the problem is still there); what changes is what it proposes:
the ``timeout`` proposal is dropped, a tactic proposal takes its place and the message says that there was one (issue #421: the message is
the situation, the proposals are the actions). Standard library only."""

from __future__ import annotations

import dataclasses
from typing import Any, Dict

from .advice_types import Advice
from .config import RuleConfig
from .proposals import tactic_proposal
from .timeouts import timeout_within

NOTE = "Ya hubo un tiempo muerto propio hace poco."
TACTIC = "Probar un cambio táctico o de rotación"


def adapt_for_recent_timeout(advice: Advice, snapshot: Dict[str, Any], own_team_id: str, config: RuleConfig) -> Advice:
    """``advice`` without a timeout proposal when the own team called one in the last ``config.timeout_recent_s`` game-seconds."""
    if config.timeout_recent_s <= 0 or not timeout_within(snapshot, own_team_id, config.timeout_recent_s):
        return advice
    if not any(p.get("type") == "timeout" for p in advice.proposal):
        return advice
    proposal = [p for p in advice.proposal if p.get("type") != "timeout"] + [tactic_proposal(TACTIC)]
    return dataclasses.replace(advice, message=f"{advice.message} {NOTE}", proposal=proposal)
