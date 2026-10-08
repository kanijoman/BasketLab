"""Advice engine: evaluates the rules on each snapshot and emits only NEW advice.

Perspective is the OWN team (``own_team_id``); without it nothing team-specific can be
said. An advice key is emitted once, unless the rule sets ``rearm_s`` (persistent
conditions such as fatigue are repeated after that many game-seconds).
"""

from __future__ import annotations

import dataclasses
from typing import Any, Callable, Dict, List, Optional

from .advice_types import SEVERITY_RANK, Advice, RuleContext
from .config import RuleConfig
from .four_factors import FourFactorsModel
from .recommender import Recommender
from .rules_four_factors import four_factors_rule
from .rules_rival import rival_player_rule, rival_zone_rule
from .rules_rotation import fatigue_rule
from .rules_team import foul_rule, run_rule, team_fouls_rule, turnover_rule

Rule = Callable[[Dict[str, Any], RuleContext], List[Advice]]
RULES: List[Rule] = [foul_rule, team_fouls_rule, run_rule, turnover_rule, fatigue_rule, four_factors_rule,
                     rival_player_rule, rival_zone_rule]

# Rival threats we can answer with own-team data: offensive rebounds -> defensive rebounders,
# steals -> ball security. Scoring/assists/threes/FTA have no matchup data: tactical text only.
_RIVAL_LEVER = {"orb": "def_reb", "stl": "tov"}

__all__ = ["Advice", "AdviceEngine"]


class AdviceEngine:
    def __init__(
        self,
        own_team_id: Optional[str],
        rival_team_id: Optional[str] = None,
        baselines: Optional[Dict[str, Dict[str, Any]]] = None,
        config: Optional[RuleConfig] = None,
        team_baselines: Optional[Dict[str, Any]] = None,
        rival_baselines: Optional[Dict[str, Dict[str, Any]]] = None,
        impact_league: Optional[Dict[str, float]] = None,
        zone_ref: Optional[Dict[str, Any]] = None,
    ) -> None:
        cfg = config or RuleConfig()
        self._model = FourFactorsModel(own_team_id, rival_team_id, team_baselines, cfg) if own_team_id else None
        self._ctx = (
            RuleContext(own_team_id, rival_team_id, cfg, baselines or {}, self._model,
                        rival_baselines or {}, impact_league or {}, zone_ref or {})
            if own_team_id else None
        )
        self._recommender = Recommender(own_team_id, baselines, cfg) if own_team_id and baselines else None
        self._last: Dict[str, int] = {}

    @classmethod
    def from_package(cls, package: Any) -> "AdviceEngine":
        return cls(
            own_team_id=str(package.team["id"]),
            rival_team_id=str(package.rival["id"]),
            baselines=(package.tables or {}).get("players", {}),
            config=RuleConfig.from_dict(package.rule_config),
            team_baselines=package.baselines,
            rival_baselines=(package.tables or {}).get("rival_players", {}),
            impact_league=(package.baselines or {}).get("impact_league"),
            zone_ref=(package.tables or {}).get("zones"),
        )

    def analyze(self, snapshot: Dict[str, Any]) -> Dict[str, Any]:
        """Non-alert insights for the UI cards (Four Factors, lever, projection)."""
        result = self._model.evaluate(snapshot) if self._model else None
        return {"four_factors": result} if result else {}

    def evaluate(self, snapshot: Dict[str, Any]) -> List[Advice]:
        if self._ctx is None:
            return []
        now, emitted = snapshot["elapsed"], []
        for rule in RULES:
            for advice in rule(snapshot, self._ctx):
                last = self._last.get(advice.key)
                if last is None or (advice.rearm_s is not None and now - last >= advice.rearm_s):
                    self._last[advice.key] = now
                    emitted.append(self._with_proposal(advice, snapshot))
        return sorted(emitted, key=lambda a: SEVERITY_RANK[a.severity])  # stable: critical first

    def _with_proposal(self, advice: Advice, snapshot: Dict[str, Any]) -> Advice:
        """Attach the recommender's substitution proposals to the advice that calls for them."""
        if self._recommender is None:
            return advice
        if advice.id in ("foul_trouble", "fatigue_high"):
            proposal = self._recommender.suggest_swaps(
                snapshot, advice.evidence["player_id"], lever=self._current_lever(snapshot))
        elif advice.id == "four_factors_lever":
            proposal = self._recommender.suggest_for_lever(snapshot, advice.evidence["lever"])
        elif advice.id == "turnover_streak":
            proposal = self._recommender.suggest_for_lever(snapshot, "tov")
        elif advice.id == "rival_hot_player" and advice.evidence["metric"] in _RIVAL_LEVER:
            proposal = self._recommender.suggest_for_lever(snapshot, _RIVAL_LEVER[advice.evidence["metric"]])
        else:
            return advice
        return dataclasses.replace(advice, proposal=proposal)

    def _current_lever(self, snapshot: Dict[str, Any]) -> Optional[str]:
        result = self._model.evaluate(snapshot) if self._model else None
        return result["lever"] if result and result["reliable"] else None
