"""Advice engine: evaluates the rules on each snapshot and emits only NEW advice.

Perspective is the OWN team (``own_team_id``); without it nothing team-specific can be
said. An advice key is emitted once, unless the rule sets ``rearm_s`` (persistent
conditions such as fatigue are repeated after that many game-seconds). A repeat is emitted
as ``key#n`` so every emission of a game has a distinct key: the app drops keys it has
already shown (#234).
"""

from __future__ import annotations

import dataclasses
from typing import Any, Callable, Dict, List, Optional, Tuple

from .advice_types import SEVERITY_RANK, Advice, RuleContext
from .config import RuleConfig
from .four_factors import FourFactorsModel
from .pace import PaceModel
from .recommender import Recommender
from .rules_four_factors import four_factors_rule
from .rules_rival import rival_player_rule, rival_zone_rule
from .rules_rotation import fatigue_rule
from .rules_team import foul_rule, rival_foul_rule, run_rule, team_fouls_rule, turnover_rule

Rule = Callable[[Dict[str, Any], RuleContext], List[Advice]]
# (id, rule) in evaluation order; the ids are config.RULE_IDS and can be switched off with RuleConfig.rules_off.
RULES: List[Tuple[str, Rule]] = [
    ("foul_trouble", foul_rule), ("rival_foul_trouble", rival_foul_rule), ("team_fouls", team_fouls_rule),
    ("rival_run", run_rule), ("turnover_streak", turnover_rule), ("fatigue_high", fatigue_rule),
    ("four_factors_lever", four_factors_rule), ("rival_hot_player", rival_player_rule), ("rival_zone", rival_zone_rule),
]

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
        self._pace = PaceModel(own_team_id, rival_team_id, team_baselines, cfg) if own_team_id else None
        self._ctx = (
            RuleContext(own_team_id, rival_team_id, cfg, baselines or {}, self._model,
                        rival_baselines or {}, impact_league or {}, zone_ref or {})
            if own_team_id else None
        )
        self._recommender = Recommender(own_team_id, baselines, cfg) if own_team_id and baselines else None
        self._last: Dict[str, int] = {}
        self._count: Dict[str, int] = {}

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
        """Non-alert insights for the UI cards (Four Factors, lever, projection, game pace)."""
        analysis: Dict[str, Any] = {}
        result = self._model.evaluate(snapshot) if self._model else None
        if result:
            analysis["four_factors"] = result
        pace = self._pace.evaluate(snapshot) if self._pace else None
        if pace:
            analysis["pace"] = pace
        return analysis

    def evaluate(self, snapshot: Dict[str, Any]) -> List[Advice]:
        if self._ctx is None:
            return []
        now, emitted = snapshot["elapsed"], []
        for rule_id, rule in RULES:
            if not self._ctx.config.enabled(rule_id):
                continue
            for advice in rule(snapshot, self._ctx):
                last = self._last.get(advice.key)
                if last is None or (advice.rearm_s is not None and now - last >= advice.rearm_s):
                    self._last[advice.key] = now
                    emitted.append(self._with_proposal(self._numbered(advice), snapshot))
        return sorted(emitted, key=lambda a: SEVERITY_RANK[a.severity])  # stable: critical first

    def _numbered(self, advice: Advice) -> Advice:
        """The first emission keeps its key; the n-th repeat of a re-armed alert becomes ``key#n``."""
        n = self._count[advice.key] = self._count.get(advice.key, 0) + 1
        return advice if n == 1 else dataclasses.replace(advice, key=f"{advice.key}#{n}")

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
