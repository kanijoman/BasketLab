"""Derived basketball stats computation — extracted from historical_ingestion_service.py."""
from __future__ import annotations

from typing import Any, Dict


def _efg(fgm: int, fg3m: int, fga: int) -> float:
    if fga <= 0:
        return 0.0
    return round((fgm + 0.5 * fg3m) / fga * 100.0, 2)


def _efg_ftr(raw: Dict[str, Any]) -> float:
    """FT rate for a team (FTA / FGA)."""
    fga = raw["fg2a"] + raw["fg3a"]
    return raw["fta"] / fga * 100.0 if fga > 0 else 0.0


def compute_derived(
    pts: int,
    opp_pts: int,
    fg2m: int,
    fg2a: int,
    fg3m: int,
    fg3a: int,
    ftm: int,
    fta: int,
    oreb: int,
    dreb: int,
    ast: int,
    stl: int,
    tov: int,
    blk: int,
    opp_fg2a: int,
    opp_fg3a: int,
    opp_fta: int,
    opp_oreb: int,
    opp_tov: int,
    opp_pts_check: int,
) -> Dict[str, float]:
    """Compute possession-based derived stats.

    All formulas are identical to those in ``StatsCalculator`` so both layers
    stay consistent.  Uses the same 0.45 FT coefficient.
    ``efg_pct`` and ``opp_efg_pct`` are initialised to 0.0 and must be
    overwritten by the caller using :func:`_efg` on the actual field-goal data.
    """
    fga = fg2a + fg3a
    opp_fga = opp_fg2a + opp_fg3a

    poss = fga + 0.45 * fta + tov - oreb
    poss = max(poss, 1.0)

    opp_poss = opp_fga + 0.45 * opp_fta + opp_tov - opp_oreb
    opp_poss = max(opp_poss, 1.0)

    pace = (poss + opp_poss) / 2.0
    ortg = pts / poss * 100.0
    drtg = opp_pts / opp_poss * 100.0
    net_rtg = ortg - drtg

    tov_rate = tov / poss * 100.0
    oreb_pct = oreb / (oreb + dreb) * 100.0 if (oreb + dreb) > 0 else 0.0
    ftr = fta / fga * 100.0 if fga > 0 else 0.0
    fg3a_rate = fg3a / fga * 100.0 if fga > 0 else 0.0

    return {
        "poss":        round(poss, 2),
        "opp_poss":    round(opp_poss, 2),
        "pace":        round(pace, 2),
        "ortg":        round(ortg, 2),
        "drtg":        round(drtg, 2),
        "net_rtg":     round(net_rtg, 2),
        "efg_pct":     0.0,      # filled by caller
        "opp_efg_pct": 0.0,      # filled by caller
        "tov_rate":    round(tov_rate, 2),
        "oreb_pct":    round(oreb_pct, 2),
        "ftr":         round(ftr, 2),
        "fg3a_rate":   round(fg3a_rate, 2),
    }
