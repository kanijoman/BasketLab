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
from typing import Any, Dict, Optional

from .config import RuleConfig

GAME_SECONDS = 2400
DEFAULT_PACE_PER_40 = 70.0   # possessions per 40 min when the package has no pace


def _phi(x: float) -> float:
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

    def evaluate(self, snap: Dict[str, Any], four_factors: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        score = snap.get("score") or {}
        if self._own not in score or self._rival not in score:
            return None
        margin = score[self._own] - score[self._rival]
        remaining = max(0, GAME_SECONDS - snap["elapsed"])
        fraction = remaining / GAME_SECONDS

        ff = four_factors or {}
        played = float(ff.get("possessions", 0.0))
        weight = played / (played + self._cfg.wp_n0) if played + self._cfg.wp_n0 else 0.0
        mu = weight * float(ff.get("expected_net_rtg", 0.0)) + (1 - weight) * self._prior_net(snap)

        poss_left = (ff.get("projection") or {}).get("poss_remaining")
        if poss_left is None:
            poss_left = float(self._base.get("pace_per_40") or DEFAULT_PACE_PER_40) * fraction
        mean = margin + mu * poss_left / 100
        sd = self._cfg.wp_sigma * math.sqrt(fraction)
        if sd > 0:
            p = _phi(mean / sd)
        else:
            p = 1.0 if margin > 0 else 0.0 if margin < 0 else 0.5
        return {"p": round(p, 4), "projected_margin": round(mean, 2), "sd": round(sd, 2),
                "poss_remaining": round(poss_left, 1), "mu_per_100": round(mu, 3),
                "reliable": bool(ff.get("reliable", False))}
