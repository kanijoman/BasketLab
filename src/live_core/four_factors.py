"""Dean Oliver's Four Factors for the live game.

Weights: eFG% 40, TOV% 25, ORB% 20, FT 15. For each factor we take the DIFFERENTIAL
(own minus rival, signed so that positive is good for the own team), shrink it towards the
season expectation with weight proportional to the possessions played, standardise it
against the league spread and mix it with Oliver's weights. The factor with the largest
weighted deficit is the "main lever": it triggers advice and drives recommendations.

Project conventions: possessions = FGA - ORB + TOV + 0.44*FTA; TOV% = TOV/(FGA + 0.44*FTA + TOV);
FTr = FTA/FGA (Oliver uses FT/FGA); team turnovers (no player) count as turnovers.
Everything is O(1) over the snapshot and standard library only.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from .config import RuleConfig

WEIGHTS = {"efg": 0.40, "tov": 0.25, "orb": 0.20, "ftr": 0.15}
FT_POSSESSION_COST = 0.44
GAME_SECONDS = 2400

# Spread (standard deviation) of single-game differentials. Placeholders until calibrated
# with history by ``live_prep`` (they travel in the package baselines).
DEFAULT_SD = {"efg": 0.08, "tov": 0.05, "orb": 0.10, "ftr": 0.12}

_REQUIRED_STATS = ("fg2m", "fg2a", "fg3m", "fg3a", "ftm", "fta", "orb", "drb", "tov", "pts")

# Fallback rates when too few possessions to estimate them from the game itself.
_FGA_PER_POSS, _PPP, _MISS_PER_POSS, _FT_PCT = 0.88, 1.0, 0.50, 0.72
_MIN_POSS_FOR_RATES = 10


def _fga(s: Dict[str, int]) -> int:
    return s["fg2a"] + s["fg3a"]


def _fgm(s: Dict[str, int]) -> int:
    return s["fg2m"] + s["fg3m"]


def _tov(s: Dict[str, int]) -> int:
    return s["tov"] + s.get("tov_team", 0)


def possessions(s: Dict[str, int]) -> float:
    return _fga(s) - s["orb"] + _tov(s) + FT_POSSESSION_COST * s["fta"]


def _ratio(num: float, den: float) -> float:
    return num / den if den else 0.0


def factors(own: Dict[str, int], opp: Dict[str, int]) -> Dict[str, float]:
    """Offensive four factors of ``own`` (the rival's defensive rebounds feed ORB%)."""
    fga = _fga(own)
    return {
        "efg": _ratio(_fgm(own) + 0.5 * own["fg3m"], fga),
        "tov": _ratio(_tov(own), fga + FT_POSSESSION_COST * own["fta"] + _tov(own)),
        "orb": _ratio(own["orb"], own["orb"] + opp["drb"]),
        "ftr": _ratio(own["fta"], fga),
    }


def differentials(own: Dict[str, int], opp: Dict[str, int]) -> Dict[str, float]:
    """Own minus rival per factor, positive = good for own (turnovers inverted)."""
    mine, theirs = factors(own, opp), factors(opp, own)
    return {
        "efg": mine["efg"] - theirs["efg"],
        "tov": theirs["tov"] - mine["tov"],
        "orb": mine["orb"] - theirs["orb"],
        "ftr": mine["ftr"] - theirs["ftr"],
    }


def shrink(obs: float, prior: float, n: float, n0: float) -> float:
    """Blend an observation with its prior; ``n`` possessions played vs ``n0`` prior weight."""
    return (n * obs + n0 * prior) / (n + n0) if (n + n0) else prior


def _points_per_unit(own: Dict[str, int]) -> Dict[str, float]:
    """Points per 100 possessions per 1.0 of each factor differential (analytic marginals)."""
    poss = possessions(own)
    reliable = poss >= _MIN_POSS_FOR_RATES
    fga_rate = _fga(own) / poss if reliable else _FGA_PER_POSS
    ppp = own["pts"] / poss if reliable and own["pts"] else _PPP
    miss_rate = (_fga(own) - _fgm(own)) / poss if reliable else _MISS_PER_POSS
    ft_pct = own["ftm"] / own["fta"] if own["fta"] >= 5 else _FT_PCT
    return {
        "efg": 2 * fga_rate * 100,
        "tov": ppp * 100,
        "orb": miss_rate * ppp * 100,
        "ftr": fga_rate * ft_pct * 100,
    }


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
        pts100 = {k: _points_per_unit(own)[k] * shrunk[k] for k in WEIGHTS}

        deficits = {k: v for k, v in contributions.items() if v < 0 and pts100[k] < 0}
        lever = min(deficits, key=deficits.get) if deficits else None

        return {
            "reliable": n >= self._cfg.ff_min_possessions,
            "possessions": round(n, 1),
            "factors_own": _round(factors(own, rival)),
            "factors_rival": _round(factors(rival, own)),
            "diffs": _round(raw), "shrunk": _round(shrunk), "z": _round(z),
            "contributions": _round(contributions), "pts100": _round(pts100),
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
