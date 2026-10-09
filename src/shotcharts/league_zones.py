"""League-wide zone stats (same structure as ``ZoneAnalyzer`` ``zone_stats``) for relative colouring."""
from typing import Any, Dict, Optional

from src.shotcharts.fbcyl_zones import iter_shot_dicts_fbcyl
from src.shotcharts.feb_zones import iter_shots_feb


def league_zone_stats(analyzer, coll: Any, fbcyl: bool = False) -> Optional[Dict]:
    """All shots of the collection (FEB or FBCYL) analysed with ``analyzer``; None if unavailable.

    The shots are streamed: a league has tens of thousands, too many to hold in a list on a
    512 MB instance.
    """
    try:
        shots = (iter_shot_dicts_fbcyl if fbcyl else iter_shots_feb)(coll, team_id=None, player_filter=None)
        stats = analyzer.analyze_zone_performance(shots)
        return stats["zone_stats"] if stats.get("total_shots") != 0 else None
    except Exception:  # noqa: BLE001 - callers fall back to the legacy colouring
        return None
