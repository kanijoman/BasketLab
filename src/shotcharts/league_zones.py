"""League-wide zone stats (same structure as ``ZoneAnalyzer`` ``zone_stats``) for relative colouring."""
from typing import Any, Dict, Optional

from src.shotcharts.fbcyl_zones import extract_shots_fbcyl
from src.shotcharts.feb_zones import extract_shots_feb


def league_zone_stats(analyzer, coll: Any, fbcyl: bool = False) -> Optional[Dict]:
    """All shots of the collection (FEB or FBCYL) analysed with ``analyzer``; None if unavailable."""
    try:
        extract = extract_shots_fbcyl if fbcyl else extract_shots_feb
        shots = extract(coll, team_id=None, player_filter=None)
        return analyzer.analyze_zone_performance(shots)["zone_stats"] if shots else None
    except Exception:  # noqa: BLE001 - callers fall back to the legacy colouring
        return None
