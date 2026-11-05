"""Rate a zone's shooting against how the COMPETITION shoots in that zone (issues #139, #760).

Fixed margins (2 points and z >= 1, the same in the rim and in the corner three) are replaced by the distribution of the competition: the reference of a zone is the list of
what each team (or each player, when a player is rated) shot there; ``above`` is over its upper quartile and ``below`` under its lower quartile. There is NO minimum of shots:
each entity weighs what it shot, so a player with one shot does not move the quartiles, and a zone with few shots is still painted (``low_sample`` is only a hint).
Pure functions; ``frontend/src/localdata/shots.ts`` is its twin and ``tests/local_vectors/shots_*.json`` the parity between them.
"""
import math
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


@dataclass(frozen=True)
class ZoneRatingConfig:
    # below this many attempts the rating is flagged as low-confidence (a hint only: the zone is rated anyway)
    min_fga: int = 10
    # the fixed-margin rule of ``rate_zone_vs_average`` (the server charts still use it, issue #765)
    z_threshold: float = 1.0
    min_delta_pp: float = 2.0


LOWER_QUARTILE = 0.25
UPPER_QUARTILE = 0.75


def weighted_quantile(pairs: Iterable[Tuple[float, float]], q: float) -> Optional[float]:
    """The ``q`` quantile of ``(value, weight)`` pairs by the inverse of the weighted cdf: the first value, in ascending order, whose cumulative weight reaches ``q`` of the total.

    Entries without weight are ignored; ``None`` when there is nothing to weigh.
    """
    ordered = sorted((v, w) for v, w in pairs if w > 0)
    total = sum(w for _, w in ordered)
    if total <= 0:
        return None
    target = q * total
    cumulative = 0.0
    for value, weight in ordered:
        cumulative += weight
        if cumulative >= target:
            return value
    return ordered[-1][0]


def rate_zone(fgm: int, fga: int, entities: Sequence[Tuple[int, int]], cfg: Optional[ZoneRatingConfig] = None) -> Dict[str, Any]:
    """Return ``league_pct``, ``delta_pp``, ``percentile``, ``rating`` (above|average|below|none|unknown) and ``low_sample``.

    ``entities`` are the ``(fgm, fga)`` of every team (or player) of the competition in the zone; ``league_pct`` is their combined percentage and ``percentile`` the weighted
    position of this zone among them (half of the ties count).
    """
    cfg = cfg or ZoneRatingConfig()
    low = fga < cfg.min_fga
    shooters = [(made, att) for made, att in entities if att > 0]
    total_att = sum(att for _, att in shooters)
    league_pct = (sum(made for made, _ in shooters) / total_att * 100.0) if total_att > 0 else None
    if fga <= 0:
        return {"league_pct": league_pct, "delta_pp": None, "percentile": None, "rating": "none", "low_sample": low}
    if total_att <= 0:
        return {"league_pct": None, "delta_pp": None, "percentile": None, "rating": "unknown", "low_sample": low}
    p = fgm / fga
    pairs = [(made / att, att) for made, att in shooters]
    q1, q3 = weighted_quantile(pairs, LOWER_QUARTILE), weighted_quantile(pairs, UPPER_QUARTILE)
    rating = "above" if p > q3 else "below" if p < q1 else "average"
    below = sum(att for value, att in pairs if value < p)
    equal = sum(att for value, att in pairs if value == p)
    return {"league_pct": league_pct, "delta_pp": (p - (league_pct / 100.0)) * 100.0, "percentile": 100.0 * ((below + 0.5 * equal) / total_att), "rating": rating, "low_sample": low}


def rate_zones(zones: List[Dict[str, Any]], entities: Sequence[Dict[str, Dict[str, int]]], cfg: Optional[ZoneRatingConfig] = None) -> List[Dict[str, Any]]:
    """Add the rating fields to each zone dict (``zone``, ``fga``, ``fgm``) against the competition's entities.

    ``entities`` is one zone table per team (or player): ``{zone: {"fga": n, "fgm": n}}``.
    """
    out = []
    for z in zones:
        per_entity = [(e[z["zone"]].get("fgm", 0), e[z["zone"]].get("fga", 0)) for e in entities if z["zone"] in e]
        out.append({**z, **rate_zone(z.get("fgm", 0), z.get("fga", 0), per_entity, cfg)})
    return out


# --- the rule that #760 replaces on the web, still used by the matplotlib charts of the server (issue #765) -------------------------------------------------------------

_P_FLOOR = 0.01


def rate_zone_vs_average(fgm: int, fga: int, league_fgm: int, league_fga: int, cfg: Optional[ZoneRatingConfig] = None) -> Dict[str, Any]:
    """The previous rule: against the league AVERAGE of the zone, ``above``/``below`` only if the gap is at least ``min_delta_pp`` points and the binomial ``z`` at least ``z_threshold``."""
    cfg = cfg or ZoneRatingConfig()
    low = fga < cfg.min_fga
    if fga <= 0:
        return {"league_pct": _pct(league_fgm, league_fga), "delta_pp": None, "rating": "none", "low_sample": low}
    if league_fga <= 0:
        return {"league_pct": None, "delta_pp": None, "rating": "unknown", "low_sample": low}
    p, p_league = fgm / fga, league_fgm / league_fga
    delta_pp = (p - p_league) * 100.0
    q = min(max(p_league, _P_FLOOR), 1 - _P_FLOOR)
    z = (p - p_league) / math.sqrt(q * (1 - q) / fga)
    rating = "average"
    if abs(delta_pp) >= cfg.min_delta_pp and abs(z) >= cfg.z_threshold:
        rating = "above" if delta_pp > 0 else "below"
    return {"league_pct": p_league * 100.0, "delta_pp": delta_pp, "rating": rating, "low_sample": low}


def _pct(made: int, att: int) -> Optional[float]:
    return made / att * 100.0 if att > 0 else None
