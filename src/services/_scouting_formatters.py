"""Pure formatting helpers for individual scouting reports."""
from __future__ import annotations

from typing import Any, Dict


def safe(val: Any, decimals: int = 1, suffix: str = "") -> str:
    if val is None:
        return "-"
    try:
        return f"{float(val):.{decimals}f}{suffix}"
    except (TypeError, ValueError):
        return str(val)


def fmt_min(val: Any) -> str:
    """Format float minutes (e.g. 350.5) as MM:SS string."""
    if val is None:
        return "-"
    try:
        m = float(val)
        return f"{int(m)}:{int(round((m % 1) * 60)):02d}"
    except (TypeError, ValueError):
        return str(val)


def prep_player_for_radar(p: Dict) -> Dict:
    """Add field aliases expected by RadarChart.calculate_metrics_from_stats()."""
    d = dict(p)
    d.setdefault("ts",      d.get("true_shooting", 0))
    d.setdefault("usage",   d.get("usage_pct", 0))
    d.setdefault("tov_pct", d.get("tov_pct_adv", 0))
    return d
