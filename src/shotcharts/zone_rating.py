"""Rate a zone's shooting against how the COMPETITION shoots in that zone (issues #139, #760).

Fixed margins (2 points and z >= 1, the same in the rim and in the corner three) are replaced by the distribution of the competition: the reference of a zone is the list of
what each team (or each player, when a player is rated) shot there; ``above`` is over its upper quartile and ``below`` under its lower quartile. There is NO minimum of shots:
each entity weighs what it shot, so a player with one shot does not move the quartiles, and a zone with few shots is still painted (``low_sample`` is only a hint).
Pure functions; ``frontend/src/localdata/shots.ts`` is its twin and ``tests/local_vectors/shots_*.json`` the parity between them.
"""
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


@dataclass(frozen=True)
class ZoneRatingConfig:
    # below this many attempts the rating is flagged as low-confidence (a hint only: the zone is rated anyway)
    min_fga: int = 10


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
