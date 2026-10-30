"""The rotation analysis of every team of a competition, for the web (#684).

``RotationService.get_rotation_analysis`` with its default thresholds is what the page shows; it takes a tenth of a second and a few KB per team, so it is computed once
at publication and the page reads it instead of waiting for the stream. The same function the endpoint calls: the figures cannot differ.
"""
from __future__ import annotations

import json
from typing import Any, Dict

from src.local_data.export import FORMAT
from src.utils.collection_utils import is_fbcyl


def export_rotations(handler: Any, name: str) -> Dict[str, Any]:
    """``{team_id, team_name, analysis}`` of every team of ``name`` that has games, in the order of ``get_teams_with_ids``."""
    from src.services.rotation_service import RotationService

    service = RotationService(handler)
    teams = []
    for team in handler.get_teams_with_ids(name) or []:
        analysis = service.get_rotation_analysis(name, team["id"], team["name"])
        if analysis.get("total_games"):
            teams.append({"team_id": str(team["id"]), "team_name": team["name"], "analysis": json.loads(json.dumps(analysis, default=str))})
    return {"format": FORMAT, "collection": name, "league": "fbcyl" if is_fbcyl(name) else "feb", "teams": teams}
