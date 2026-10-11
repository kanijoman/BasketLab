"""Game pace (possessions per 40 min) for the live game.

Pace = average possessions of both teams per 40 game-minutes (possessions = FGA - ORB + TOV + 0.44*FTA, the
project-wide formula). It is compared with the HABITUAL pace of our team and of the rival (season means that
travel in the package baselines: ``pace_own_per_40`` / ``pace_rival_per_40``).
The projection is a plain extrapolation: the possessions seen so far plus the pace so far times the game time
left (so in regulation the projected total per team equals the current pace per 40 min). It does not use the
habits, which keeps it transparent and valid with old packages; the first minutes are noisy, hence
``RuleConfig.pace_min_elapsed_s``.
Standard library only, O(1) over the snapshot.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from .config import RuleConfig
from .four_factors import GAME_SECONDS, possessions


def _round(value: Optional[float]) -> Optional[float]:
    return None if value is None else round(value, 2)


class PaceModel:
    def __init__(self, own_team_id: Optional[str], rival_team_id: Optional[str],
                 baselines: Optional[Dict[str, Any]] = None, config: Optional[RuleConfig] = None) -> None:
        self._own, self._rival = own_team_id, rival_team_id
        self._base = baselines or {}
        self._cfg = config or RuleConfig()

    def _mean_possessions(self, snap: Dict[str, Any]) -> Optional[float]:
        teams = snap.get("teams") or {}
        ids = [t for t in (self._own, self._rival) if t]
        if not self._own or any(t not in teams for t in ids):
            return None
        try:
            return sum(possessions(teams[t].get("stats") or {}) for t in ids) / len(ids)
        except KeyError:  # partial snapshot: nothing sensible to say yet
            return None

    def evaluate(self, snap: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        elapsed = snap.get("elapsed") or 0
        n = self._mean_possessions(snap)
        if n is None or elapsed <= 0:
            return None
        current = n / elapsed * GAME_SECONDS
        habit_own = self._base.get("pace_own_per_40")
        habit_rival = self._base.get("pace_rival_per_40") if self._rival else None  # no rival, no comparison
        remaining = max(0, GAME_SECONDS - elapsed)
        sample = self._base.get("sample_games") or {}
        return {
            "reliable": elapsed >= self._cfg.pace_min_elapsed_s,
            "possessions": _round(n),
            "current40": _round(current),
            "habit_own40": habit_own, "habit_rival40": habit_rival,
            "delta_own": _round(current - habit_own) if habit_own else None,
            "delta_rival": _round(current - habit_rival) if habit_rival else None,
            "projected_possessions": _round(n + current * remaining / GAME_SECONDS),
            "sample_games": {"own": sample.get("own"), "rival": sample.get("rival")},
        }
