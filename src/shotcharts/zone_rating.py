"""Rate a zone's shooting against the league average for that same zone.

Replaces fixed FG% colour thresholds: a zone is ``above`` / ``below`` the league only when
the gap is both practical (>= ``min_delta_pp`` points) and larger than sampling noise
(binomial z >= ``z_threshold``), so a few shots do not paint a zone red or green.
Pure functions; thresholds are provisional (confirm with the staff).
"""
import math
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class ZoneRatingConfig:
    z_threshold: float = 1.0
    min_delta_pp: float = 2.0
    # below this many attempts the rating is flagged as low-confidence
    min_fga: int = 10


_P_FLOOR = 0.01


def rate_zone(
    fgm: int, fga: int, league_fgm: int, league_fga: int, cfg: Optional[ZoneRatingConfig] = None
) -> Dict[str, Any]:
    """Return ``league_pct``, ``delta_pp``, ``rating`` (above|average|below|none|unknown), ``low_sample``."""
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


def rate_zones(
    zones: List[Dict[str, Any]], league: List[Dict[str, Any]], cfg: Optional[ZoneRatingConfig] = None
) -> List[Dict[str, Any]]:
    """Add rating fields to each zone dict (``zone``, ``fga``, ``fgm``) using the league's zone stats."""
    by_zone = {z["zone"]: z for z in league}
    out = []
    for z in zones:
        ref = by_zone.get(z["zone"], {})
        out.append({**z, **rate_zone(z.get("fgm", 0), z.get("fga", 0), ref.get("fgm", 0), ref.get("fga", 0), cfg)})
    return out
