"""League-wide zone stats (same structure as ``ZoneAnalyzer`` ``zone_stats``) for relative colouring."""
from typing import Any, Dict, Optional

from src.shotcharts.feb_zones import extract_shots_feb


def league_zone_stats(analyzer, coll: Any) -> Optional[Dict]:
    """All FEB shots of the collection analysed with ``analyzer``; None if unavailable."""
    try:
        shots = extract_shots_feb(coll, team_id=None, player_filter=None)
        return analyzer.analyze_zone_performance(shots)["zone_stats"] if shots else None
    except Exception:  # noqa: BLE001 - callers fall back to the legacy colouring
        return None
