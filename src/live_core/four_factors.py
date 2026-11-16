"""Dean Oliver's Four Factors for the live game.

Weights: eFG% 40, TOV% 25, ORB% 20, FT 15. For each factor we take the DIFFERENTIAL
(own minus rival, signed so that positive is good for the own team), shrink it towards the
season expectation with weight proportional to the possessions played, standardise it
against the league spread and mix it with Oliver's weights. The factor with the largest
weighted deficit is the "main lever": it triggers advice and drives recommendations. The model of the live game that
does it is ``four_factors_model`` (#945): this module holds the formulas only, which the season pipelines and the
published sections of the web use too, so that tuning a threshold of the live rules (``RuleConfig``) changes nothing of them.

Project conventions: possessions = FGA - ORB + TOV + 0.44*FTA; TOV% = TOV/(FGA + 0.44*FTA + TOV);
FTr = FTA/FGA (Oliver uses FT/FGA); team turnovers (no player) count as turnovers.
Everything is O(1) over the snapshot and standard library only.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from .clock import GAME_SECONDS  # noqa: F401  (re-exported: pace and summary_cause import it from here)

WEIGHTS = {"efg": 0.40, "tov": 0.25, "orb": 0.20, "ftr": 0.15}
FT_POSSESSION_COST = 0.44

# Spread (standard deviation) of single-game differentials. Placeholders until calibrated
# with history by ``live_prep`` (they travel in the package baselines).
DEFAULT_SD = {"efg": 0.08, "tov": 0.05, "orb": 0.10, "ftr": 0.12}

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


def points_per_unit(own: Dict[str, int]) -> Dict[str, float]:
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


# +1: a higher value of the factor is good for the team that makes it (turnovers: -1)
_GOOD = {"efg": 1, "tov": -1, "orb": 1, "ftr": 1}
SIDE_SHARE = 0.7      # a side is «the» problem when it carries this share of what is lost in the factor


def lever_sides(levels: Optional[Dict[str, Any]], own_game: Dict[str, float], rival_game: Dict[str, float], per_unit: Dict[str, float]) -> Optional[Dict[str, Dict[str, float]]]:
    """Per factor, points per 100 possessions the game costs (negative) or gives us (positive) in our ATTACK and in our DEFENCE (issue #586), and what each team was expected to make.

    Each team is expected to make what it usually makes plus what the other usually lets (both measured against the league): our attack is what we make against that
    expectation, our defence is what the rival makes against its own. A diagnosis of what the game shows, not a forecast. ``levels`` is ``baselines.team_levels``."""
    if not levels or not all(k in levels for k in ("league", "own", "rival")):
        return None
    league, own, rival = levels["league"], levels["own"], levels["rival"]
    out: Dict[str, Dict[str, float]] = {}
    for f, good in _GOOD.items():
        expected_own = own["attack"][f] + rival["defence"][f] - league[f]
        expected_rival = rival["attack"][f] + own["defence"][f] - league[f]
        out[f] = {"attack": round(per_unit[f] * (own_game[f] - expected_own) * good, 3), "defence": round(per_unit[f] * (expected_rival - rival_game[f]) * good, 3),
                  "expected_own": round(expected_own, 4), "expected_rival": round(expected_rival, 4)}
    return out


def side_of(sides: Optional[Dict[str, Dict[str, float]]], factor: str) -> Optional[str]:
    """``attack``, ``defence`` or ``both``: where the game loses points in ``factor`` (None when nothing is lost or there is no diagnosis)."""
    if not sides or factor not in sides:
        return None
    attack, defence = sides[factor]["attack"], sides[factor]["defence"]
    lost = -min(attack, 0.0) - min(defence, 0.0)
    if lost <= 0:
        return None
    if -min(attack, 0.0) >= SIDE_SHARE * lost:
        return "attack"
    if -min(defence, 0.0) >= SIDE_SHARE * lost:
        return "defence"
    return "both"
