"""Advice engine: evaluates the rules on each snapshot and emits only NEW advice.

Perspective is the OWN team (``own_team_id``); without it nothing team-specific can be
said. An advice key is emitted once, unless the rule sets ``rearm_s`` (persistent
conditions such as fatigue are repeated after that many game-seconds).
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from .advice_types import SEVERITY_RANK, Advice, RuleContext
from .config import RuleConfig
from .rules_rotation import fatigue_rule
from .rules_team import foul_rule, run_rule, team_fouls_rule, turnover_rule

Rule = Callable[[Dict[str, Any], RuleContext], List[Advice]]
RULES: List[Rule] = [foul_rule, team_fouls_rule, run_rule, turnover_rule, fatigue_rule]

__all__ = ["Advice", "AdviceEngine"]


class AdviceEngine:
    def __init__(
        self,
        own_team_id: Optional[str],
        rival_team_id: Optional[str] = None,
        baselines: Optional[Dict[str, Dict[str, Any]]] = None,
        config: Optional[RuleConfig] = None,
    ) -> None:
        self._own = own_team_id
        self._ctx = (
            RuleContext(own_team_id, rival_team_id, config or RuleConfig(), baselines or {})
            if own_team_id else None
        )
        self._last: Dict[str, int] = {}

    @classmethod
    def from_package(cls, package: Any) -> "AdviceEngine":
        return cls(
            own_team_id=str(package.team["id"]),
            rival_team_id=str(package.rival["id"]),
            baselines=(package.tables or {}).get("players", {}),
            config=RuleConfig.from_dict(package.rule_config),
        )

    def evaluate(self, snapshot: Dict[str, Any]) -> List[Advice]:
        if self._ctx is None:
            return []
        now, emitted = snapshot["elapsed"], []
        for rule in RULES:
            for advice in rule(snapshot, self._ctx):
                last = self._last.get(advice.key)
                if last is None or (advice.rearm_s is not None and now - last >= advice.rearm_s):
                    self._last[advice.key] = now
                    emitted.append(advice)
        return sorted(emitted, key=lambda a: SEVERITY_RANK[a.severity])  # stable: critical first
