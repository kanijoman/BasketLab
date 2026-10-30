"""The possessions page of a competition, for the web (#679).

``GET /possessions/{collection}`` takes no filter (the client sends some, the router ignores them): it is a table per competition, computed from the play-by-play of every
game (9 s for the biggest league), together with the consistency of the teams (CV of their games, 0.1 s) and the two CSV exports of the page. All of it is computed once at
publication with the code the endpoints run. The per-possession CSV (0.4 MB compressed) is the heavy part and goes in a payload of its own: it is read only when the button is
pressed. The files carry no BOM: the browser adds it once at the start of the download, as the endpoints do.
"""
from __future__ import annotations

import json
from typing import Any, Dict

from src.local_data.export import FORMAT
from src.utils.collection_utils import is_fbcyl


def _base(name: str) -> Dict[str, Any]:
    return {"format": FORMAT, "collection": name, "league": "fbcyl" if is_fbcyl(name) else "feb"}


def export_possessions(handler: Any, name: str) -> Dict[str, Any]:
    """The table of the page, the consistency of the teams and the quality CSV."""
    from src.services import team_stats_service
    from src.services.pbp_quality_service import PBPQualityService
    from src.services.team_stats_service import TeamStatsService

    team_stats_service._possession_cache.clear()                 # the table is cached an hour per collection: a publication needs the games as they are now
    service = TeamStatsService(handler)
    payload = {**_base(name), "table": service.get_possession_stats(name), "consistency": service.get_consistency(name),
               "quality_csv": "".join(PBPQualityService.csv_chunks(handler, name))}
    return json.loads(json.dumps(payload, default=str))


def export_possession_csv(handler: Any, name: str) -> Dict[str, Any]:
    """The per-possession CSV of the competition (one row per possession of every game with play-by-play) and the games it comes from."""
    from src.services.possession_export_service import PossessionExportService

    text = "".join(PossessionExportService.csv_chunks(handler, name))
    games = sum(1 for _ in PossessionExportService.iter_collection(handler, name, None)) if text else 0
    return {**_base(name), "games": games, "csv": text}
