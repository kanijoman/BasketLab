"""The model of the Four Factors for the live game (split from ``four_factors`` in #945).

``FourFactorsModel.evaluate`` takes the snapshot of the game and says, per factor, the differential (own minus rival, positive is
good for the own team) shrunk towards the season expectation with ``RuleConfig``'s prior weights, standardised against the league
spread and mixed with Oliver's weights; the factor with the largest weighted deficit is the "main lever", and the projection of the
margin over the possessions left. It lives apart from the formulas (``four_factors``) because it reads ``RuleConfig``, the thresholds
of the live rules: the formulas are also what the season pipelines and the published sections of the web are made of, and a
section of ``web-data`` depends on every module it imports, so tuning a rule recomputed all of them (16/11/2026, #934).
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from .clock import GAME_SECONDS
from .config import RuleConfig
from .four_factors import DEFAULT_SD, WEIGHTS, differentials, factors, lever_sides, points_per_unit, possessions, shrink

_REQUIRED_STATS = ("fg2m", "fg2a", "fg3m", "fg3a", "ftm", "fta", "orb", "drb", "tov", "pts")


class FourFactorsModel:
    def __init__(self, own_team_id: Optional[str], rival_team_id: Optional[str],
                 baselines: Optional[Dict[str, Any]] = None, config: Optional[RuleConfig] = None) -> None:
        self._own, self._rival = own_team_id, rival_team_id
        self._base = baselines or {}
        self._cfg = config or RuleConfig()

    def _n0(self) -> Dict[str, float]:
        c = self._cfg
        return {"efg": c.ff_n0_efg, "tov": c.ff_n0_tov, "orb": c.ff_n0_orb, "ftr": c.ff_n0_ftr}

    def evaluate(self, snap: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        teams = snap["teams"]
        if not self._own or not self._rival or self._own not in teams or self._rival not in teams:
            return None
        own, rival = teams[self._own].get("stats") or {}, teams[self._rival].get("stats") or {}
        if any(k not in own or k not in rival for k in _REQUIRED_STATS):
            return None  # partial snapshot: nothing sensible to say yet
        n = (possessions(own) + possessions(rival)) / 2

        raw = differentials(own, rival)
        prior = self._base.get("four_factors_prior", {})
        mean = self._base.get("four_factors_mean", {})
        sd = {**DEFAULT_SD, **self._base.get("four_factors_sd", {})}
        n0 = self._n0()

        shrunk = {k: shrink(raw[k], prior.get(k, 0.0), n, n0[k]) for k in WEIGHTS}
        z = {k: (shrunk[k] - mean.get(k, 0.0)) / sd[k] for k in WEIGHTS}
        contributions = {k: WEIGHTS[k] * z[k] for k in WEIGHTS}
        score = sum(contributions.values())
        pts100 = {k: points_per_unit(own)[k] * shrunk[k] for k in WEIGHTS}
        pts100_raw = {k: points_per_unit(own)[k] * raw[k] for k in WEIGHTS}   # without the shrinkage towards the prior

        deficits = {k: v for k, v in contributions.items() if v < 0 and pts100[k] < 0}
        lever = min(deficits, key=deficits.get) if deficits else None

        return {
            "reliable": n >= self._cfg.ff_min_possessions,
            "possessions": round(n, 1),
            "factors_own": _round(factors(own, rival)),
            "factors_rival": _round(factors(rival, own)),
            "diffs": _round(raw), "shrunk": _round(shrunk), "z": _round(z),
            "contributions": _round(contributions), "pts100": _round(pts100), "pts100_raw": _round(pts100_raw),
            "sides": lever_sides(self._base.get("team_levels"), factors(own, rival), factors(rival, own), points_per_unit(own)),
            "score": round(score, 4), "lever": lever,
            "expected_net_rtg": round(self._cfg.ff_beta * score, 3),
            "projection": self._project(snap, n, score),
        }

    def _project(self, snap: Dict[str, Any], n: float, score: float) -> Dict[str, Any]:
        margin_now = snap["score"][self._own] - snap["score"][self._rival]
        elapsed = snap["elapsed"]
        remaining = max(0, GAME_SECONDS - elapsed)
        observed_pace40 = n / elapsed * GAME_SECONDS if elapsed else 0.0
        prior_pace40 = self._base.get("pace_per_40")
        w = min(1.0, elapsed / GAME_SECONDS)
        pace40 = w * observed_pace40 + (1 - w) * prior_pace40 if prior_pace40 else observed_pace40
        poss_remaining = pace40 * remaining / GAME_SECONDS
        projected = margin_now + self._cfg.ff_beta * score * poss_remaining / 100
        return {"margin_now": margin_now, "pace40": round(pace40, 1),
                "poss_remaining": round(poss_remaining, 1), "projected_margin": round(projected, 2)}


def _round(values: Dict[str, float]) -> Dict[str, float]:
    return {k: round(v, 4) for k, v in values.items()}
