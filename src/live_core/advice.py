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
from .recent_timeout import adapt_for_recent_timeout
from .win_prob import WinProbabilityModel
from .game_context import adjust_for_phase, game_phase, kept_when_decided
from .pace import PaceModel
from .proposals import timeout_proposal
from .lineups import lineup_key
from .recommender import Recommender
from .rules_four_factors import four_factors_rule
from .rules_lineup import departure_note, formation_counts, formation_rule, roster_known
from .rules_closing import advantage_rule, closing_rule, comeback_rule, pace_rule
from .rules_discipline import disqualification_rule, key_fouls_rule, rival_pair_rule
from .rules_flow import after_timeout_rule, drought_rule, long_run_rule, static_rule, window_rule
from .rules_plusminus import lineup_rule, player_rule
from .rules_players import own_orb_rule, own_player_rule, rival_player_rule as rival_form_rule, rival_star_rule
from .rules_rest import rest_rule
from .rules_zones import own_zone_rule, paint_rule, rival_defence_rule, rival_player_zone_rule
from .rules_summary import edges_rule, summary_rule
from .rules_timeouts import timeout_budget_rule
from .rules_winflip import win_flip_rule
from .rules_streaks import cold_shooting_rule, free_throw_rule, rival_hot_rule
from .rules_rival import rival_player_rule, rival_zone_rule
from .rules_rotation import fatigue_rule
from .rules_run import run_rule, turnover_rule
from .rules_team import foul_rule, rival_foul_rule, team_fouls_rule
from .timeouts import timeouts_left

Rule = Callable[[Dict[str, Any], RuleContext], List[Advice]]
# (id, rule) in evaluation order; the ids are config.RULE_IDS and can be switched off with RuleConfig.rules_off.
RULES: List[Tuple[str, Rule]] = [
    ("foul_trouble", foul_rule), ("rival_foul_trouble", rival_foul_rule), ("formation_lineup", formation_rule),
    ("team_fouls", team_fouls_rule),
    ("rival_run", run_rule), ("turnover_streak", turnover_rule), ("fatigue_high", fatigue_rule),
    ("four_factors_lever", four_factors_rule), ("rival_hot_player", rival_player_rule), ("rival_zone", rival_zone_rule),
    ("rest_starters", rest_rule),
    ("cold_shooting", cold_shooting_rule), ("rival_hot_shooting", rival_hot_rule), ("free_throw_cold", free_throw_rule),
    ("scoring_drought", drought_rule), ("long_run", long_run_rule), ("game_flow_windows", window_rule),
    ("rival_player_form", rival_form_rule), ("own_player_form", own_player_rule), ("rival_star_bench", rival_star_rule),
    ("disqualification", disqualification_rule), ("timeout_budget", timeout_budget_rule),
    ("key_fouls_close", key_fouls_rule), ("rival_foul_pair", rival_pair_rule),
    ("closing_briefing", closing_rule), ("period_summary", summary_rule), ("advantage_management", advantage_rule),
    ("pace_control", pace_rule), ("lineup_net", lineup_rule), ("player_plus_minus", player_rule),
    ("own_zones", own_zone_rule), ("rival_defence_zones", rival_defence_rule), ("rival_zone_player", rival_player_zone_rule),
    ("paint_battle", paint_rule), ("after_timeout_scoring", after_timeout_rule),
    ("own_orb_player", own_orb_rule), ("static_offense", static_rule),
    ("period_edges", edges_rule), ("comeback_plan", comeback_rule), ("win_flip", win_flip_rule),
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
        roster: Optional[Dict[str, Dict[str, Any]]] = None,
        lineups: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        cfg = config or RuleConfig()
        self._model = FourFactorsModel(own_team_id, rival_team_id, team_baselines, cfg) if own_team_id else None
        self._pace = PaceModel(own_team_id, rival_team_id, team_baselines, cfg) if own_team_id else None
        self._win_prob = WinProbabilityModel(own_team_id, rival_team_id, team_baselines, cfg) if own_team_id and rival_team_id else None
        lineup_table = {lineup_key(row["players"]): row for row in (lineups or [])}
        games_played = ((team_baselines or {}).get("sample_games") or {}).get("own")
        self._recommender = (Recommender(own_team_id, baselines, cfg, roster=roster, lineups=lineup_table, games_played=games_played)
                             if own_team_id and baselines else None)
        self._ctx = (
            RuleContext(own_team_id, rival_team_id, cfg, baselines or {}, self._model,
                        rival_baselines or {}, impact_league or {}, zone_ref or {}, roster or {}, self._recommender,
                        pace=self._pace, team_baselines=team_baselines or {}, win_prob=self._win_prob,
                        lineups=lineup_table)
            if own_team_id else None
        )
        self._last: Dict[str, int] = {}
        self._streak: Dict[str, int] = {}   # key -> consecutive evaluations it has appeared in (alerts that ask to confirm)
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
            roster=(package.tables or {}).get("roster"),
            lineups=(package.tables or {}).get("lineups"),
        )

    def analyze(self, snapshot: Dict[str, Any]) -> Dict[str, Any]:
        """Non-alert insights for the UI cards (Four Factors, lever, projection, game pace)."""
        analysis: Dict[str, Any] = {}
        result = self._model.evaluate(snapshot) if self._model else None
        if result:
            analysis["four_factors"] = result
        win_prob = self._win_prob.evaluate(snapshot, result) if self._win_prob else None
        if win_prob:
            analysis["win_prob"] = win_prob
            analysis["win_levers"] = self._win_levers(snapshot, result)
        pace = self._pace.evaluate(snapshot) if self._pace else None
        if pace:
            analysis["pace"] = pace
        if self._ctx is not None:
            own, rival = self._ctx.own_team_id, self._ctx.rival_team_id
            analysis["context"] = {**game_phase(snapshot, own, rival, self._ctx.config), "timeouts": {
                "own": timeouts_left(snapshot, own), "rival": timeouts_left(snapshot, rival) if rival else None}}
            if self._ctx.config.formation_min_on_court > 0:
                analysis["formation"] = self._formation_status(snapshot)
        return analysis

    def _win_levers(self, snapshot: Dict[str, Any], four_factors: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Levers of the win probability; each factor lever carries the recommender's swaps for it (issue #256)."""
        levers = self._win_prob.levers(snapshot, four_factors)
        if self._recommender is None:
            return levers
        return [{**lv, "proposal": self._recommender.suggest_for_lever(snapshot, lv["id"])} if lv["id"] != "pace" else lv for lv in levers]

    def _formation_status(self, snapshot: Dict[str, Any]) -> Dict[str, Any]:
        """For the app: the minimum, whether the roster tells who is formación, and how many are on court now."""
        ctx = self._ctx
        known = roster_known(ctx.roster, ctx.own_team_id)
        counts = formation_counts(snapshot, ctx.own_team_id, ctx.roster)
        rival = ctx.rival_team_id
        rival_known = bool(rival) and roster_known(ctx.roster, rival)
        rival_counts = formation_counts(snapshot, rival, ctx.roster) if rival_known else None
        return {"min": ctx.config.formation_min_on_court, "known": known, "on_court": counts["yes"] if known else None,
                "unknown": counts["unknown"] if known else 0, "players": counts["players"],
                "rival": {"known": rival_known, "on_court": rival_counts["yes"] if rival_counts else None,
                          "unknown": rival_counts["unknown"] if rival_counts else 0, "players": rival_counts["players"] if rival_counts else 0}}

    def evaluate(self, snapshot: Dict[str, Any]) -> List[Advice]:
        if self._ctx is None:
            return []
        cfg, now, emitted = self._ctx.config, snapshot["elapsed"], []
        context = (game_phase(snapshot, self._ctx.own_team_id, self._ctx.rival_team_id, cfg)
                   if cfg.enabled("game_context") else None)
        streaks: Dict[str, int] = {}
        for rule_id, rule in RULES:
            if not cfg.enabled(rule_id):
                continue
            for raw in rule(snapshot, self._ctx):
                advice = adjust_for_phase(raw, context) if context else raw
                if context and context["phase"] == "decided" and cfg.decided_only_rotation and not kept_when_decided(advice):
                    continue     # silenced, not recorded: it comes back if the game reopens (#320)
                if advice.confirm > 1:
                    streaks[advice.key] = self._streak.get(advice.key, 0) + 1
                    if streaks[advice.key] < advice.confirm:
                        continue
                if self._is_new(advice, raw.key, now):
                    self._last[advice.key] = now
                    emitted.append(adapt_for_recent_timeout(self._with_proposal(self._numbered(advice), snapshot), snapshot,
                                                            self._ctx.own_team_id, self._ctx.config))
        self._streak = streaks   # an alert that was not there this time starts again
        return sorted(emitted, key=lambda a: SEVERITY_RANK[a.severity])  # stable: critical first

    def _is_new(self, advice: Advice, base_key: str, now: int) -> bool:
        """Never said, or a re-armed alert whose interval has passed.

        An alert the phase lowered (``key~phase``) counts what was already said under its plain key, so a change of phase
        does not repeat it; the other way round it does (the plain key was never said), as the game reopened.
        """
        last = self._last.get(advice.key)
        if last is None and advice.key != base_key:
            last = self._last.get(base_key)
        return last is None or (advice.rearm_s is not None and now - last >= advice.rearm_s)

    def _numbered(self, advice: Advice) -> Advice:
        """The first emission keeps its key; the n-th repeat of a re-armed alert becomes ``key#n``."""
        n = self._count[advice.key] = self._count.get(advice.key, 0) + 1
        return advice if n == 1 else dataclasses.replace(advice, key=f"{advice.key}#{n}")

    def _with_proposal(self, advice: Advice, snapshot: Dict[str, Any]) -> Advice:
        """Complete the advice's proposals: timeouts get their count, substitutions come after the rule's own."""
        advice = self._with_timeout_count(advice, snapshot)
        if advice.id in ("foul_trouble", "fatigue_high"):
            note = departure_note(snapshot, self._ctx.own_team_id, self._ctx.roster, self._ctx.config,
                                  advice.evidence["player_id"])
            if note:
                advice = dataclasses.replace(advice, message=f"{advice.message} {note}")
        if self._recommender is None:
            return advice
        proposal: List[Dict[str, Any]]
        if advice.id in ("foul_trouble", "fatigue_high"):
            proposal = self._relief(snapshot, advice)
        elif advice.id == "win_flip" and advice.evidence["lever"] not in (None, "pace"):
            proposal = self._recommender.suggest_for_lever(snapshot, advice.evidence["lever"])
        elif advice.id == "four_factors_lever":
            proposal = self._recommender.suggest_for_lever(snapshot, advice.evidence["lever"])
        elif advice.id == "rival_orb_window":
            proposal = self._recommender.suggest_for_lever(snapshot, "def_reb")
        elif advice.id == "turnover_streak":
            proposal = self._recommender.suggest_for_lever(snapshot, "tov")
        elif advice.id == "rival_hot_player" and advice.evidence["metric"] in _RIVAL_LEVER:
            proposal = self._recommender.suggest_for_lever(snapshot, _RIVAL_LEVER[advice.evidence["metric"]])
        else:
            return advice
        return dataclasses.replace(advice, proposal=[*advice.proposal, *proposal])

    def _relief(self, snapshot: Dict[str, Any], advice: Advice) -> List[Dict[str, Any]]:
        """Who comes in for a tired or fouled player: the closest role, but in a decided game the bench goes first (issue #320)."""
        pid = advice.evidence["player_id"]
        if advice.id == "fatigue_high" and self._ctx.config.decided_only_rotation:
            phase = game_phase(snapshot, self._ctx.own_team_id, self._ctx.rival_team_id, self._ctx.config)["phase"]
            rested = self._recommender.suggest_rest(snapshot, pid) if phase == "decided" else []
            if rested:
                return rested
        return self._recommender.suggest_swaps(snapshot, pid, lever=self._current_lever(snapshot))

    def _with_timeout_count(self, advice: Advice, snapshot: Dict[str, Any]) -> Advice:
        """A timeout proposal that does not say how many timeouts are left gets the own team's count."""
        if not any(p.get("type") == "timeout" and "left" not in p for p in advice.proposal):
            return advice
        left = timeouts_left(snapshot, self._ctx.own_team_id)
        return dataclasses.replace(advice, proposal=[
            timeout_proposal(left) if p.get("type") == "timeout" and "left" not in p else p for p in advice.proposal])

    def _current_lever(self, snapshot: Dict[str, Any]) -> Optional[str]:
        result = self._model.evaluate(snapshot) if self._model else None
        return result["lever"] if result and result["reliable"] else None
