"""Live win probability (issue #254).

The final margin is modelled as Normal(margin now + mu * possessions left / 100, sd^2 * fraction of the game left):
``mu`` is the expected net rating per 100 possessions for the rest of the game, ``sd`` the spread of a whole game's
margin. P(win) = Phi(mean / sd); a tie at the end splits the overtime 50/50. ``mu`` blends the pre-game prior (the
matchup's net rating from the package plus home court) with what the game shows (the Four Factors' expected net
rating), the latter weighted by the possessions played against ``wp_n0``.

Overtime is not modelled: once the 40 minutes are played the result is the sign of the margin (a tie is 50 %).
Everything is O(1) and standard library only.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

from .config import RuleConfig
from .four_factors import WEIGHTS, points_per_unit

GAME_SECONDS = 2400
DEFAULT_PACE_PER_40 = 70.0   # possessions per 40 min when the package has no pace


def phi(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


class WinProbabilityModel:
    def __init__(self, own_team_id: Optional[str], rival_team_id: Optional[str],
                 baselines: Optional[Dict[str, Any]] = None, config: Optional[RuleConfig] = None) -> None:
        self._own, self._rival = own_team_id, rival_team_id
        self._base = baselines or {}
        self._cfg = config or RuleConfig()

    def _prior_net(self, snap: Dict[str, Any]) -> float:
        """Pre-game expectation per 100 possessions: matchup strength plus home court (zero when nobody is local)."""
        home = snap.get("home_id")
        court = self._cfg.wp_home_adv if home == self._own else -self._cfg.wp_home_adv if home == self._rival else 0.0
        return float(self._base.get("net_rtg_prior", 0.0)) + court

    def _state(self, snap: Dict[str, Any], four_factors: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        score = snap.get("score") or {}
        if self._own not in score or self._rival not in score:
            return None
        margin = score[self._own] - score[self._rival]
        fraction = max(0, GAME_SECONDS - snap["elapsed"]) / GAME_SECONDS
        ff = four_factors or {}
        played = float(ff.get("possessions", 0.0))
        weight = played / (played + self._cfg.wp_n0) if played + self._cfg.wp_n0 else 0.0
        mu = weight * float(ff.get("expected_net_rtg", 0.0)) + (1 - weight) * self._prior_net(snap)
        poss_left = (ff.get("projection") or {}).get("poss_remaining")
        if poss_left is None:
            poss_left = float(self._base.get("pace_per_40") or DEFAULT_PACE_PER_40) * fraction
        return {"margin": margin, "mu": mu, "poss_left": poss_left, "sd": self._cfg.wp_sigma * math.sqrt(fraction),
                "reliable": bool(ff.get("reliable", False))}

    @staticmethod
    def _p(margin: float, mean: float, sd: float) -> float:
        if sd > 0:
            return phi(mean / sd)
        return 1.0 if margin > 0 else 0.0 if margin < 0 else 0.5

    def evaluate(self, snap: Dict[str, Any], four_factors: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        st = self._state(snap, four_factors)
        if st is None:
            return None
        mean = st["margin"] + st["mu"] * st["poss_left"] / 100
        return {"p": round(self._p(st["margin"], mean, st["sd"]), 4), "projected_margin": round(mean, 2), "sd": round(st["sd"], 2),
                "poss_remaining": round(st["poss_left"], 1), "mu_per_100": round(st["mu"], 3), "reliable": st["reliable"]}

    def levers(self, snap: Dict[str, Any], four_factors: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """What moves the probability in our favour (issue #256), best first; nothing until the game is reliable.

        Per Four Factors factor: if for the rest of the game the differential goes back from what the model expects now
        (shrunk) to the team's usual level (the package prior), it is worth ``gain_pts`` and ``gain`` of probability. Pace:
        who is behind gains from more possessions (more variance), who is ahead from fewer. Gains under
        ``wp_lever_min_gain`` are noise and are not listed.
        """
        st = self._state(snap, four_factors)
        if st is None or not st["reliable"] or not four_factors or "shrunk" not in four_factors:
            return []
        margin, mu, left, sd = st["margin"], st["mu"], st["poss_left"], st["sd"]
        mean = margin + mu * left / 100
        base = self._p(margin, mean, sd)
        prior = self._base.get("four_factors_prior") or {}
        per_unit = points_per_unit(snap["teams"][self._own]["stats"])
        rows: List[Dict[str, Any]] = []
        for factor in WEIGHTS:
            shortfall = prior.get(factor, 0.0) - four_factors["shrunk"][factor]
            if shortfall > 0:
                pts = per_unit[factor] * shortfall * left / 100
                rows.append({"id": factor, "gain": self._p(margin, mean + pts, sd) - base, "gain_pts": pts})
        c = self._cfg.wp_pace_change
        if mean != 0:
            up = mean < 0
            factor = 1 + c if up else 1 - c
            pace_mean = margin + mu * left * factor / 100
            rows.append({"id": "pace", "direction": "up" if up else "down", "gain": self._p(margin, pace_mean, sd * math.sqrt(factor)) - base,
                         "gain_pts": pace_mean - mean})
        rows = [r for r in rows if r["gain"] >= self._cfg.wp_lever_min_gain]
        return [{**r, "gain": round(r["gain"], 4), "gain_pts": round(r["gain_pts"], 2)} for r in sorted(rows, key=lambda r: -r["gain"])]

    def lever_gains(self, snap: Dict[str, Any], four_factors: Optional[Dict[str, Any]]) -> Dict[str, float]:
        """Lever id -> probability gain, for the alerts' evidence."""
        return {r["id"]: r["gain"] for r in self.levers(snap, four_factors)}
