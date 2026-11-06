"""The assist connections of every team of a competition, for the web (#773).

``AssistConnectionService.get_all_teams`` reads the games of the competition once and adds them up per team (who passes, who receives, from which zones the receiver scores,
assisted against not assisted). It is a few KB per team, so it is computed at publication and the page reads it; the same service the endpoint calls, so the figures cannot differ.
"""
from __future__ import annotations

from typing import Any, Dict

from src.local_data.export import FORMAT
from src.utils.collection_utils import is_fbcyl


def export_assist_connections(handler: Any, name: str) -> Dict[str, Any]:
    """``{team_id, team_name, analysis}`` of every team of ``name`` with at least one made basket, in the order of ``get_teams_with_ids``."""
    from src.services.assist_connection_service import AssistConnectionService

    teams = AssistConnectionService(handler).get_all_teams(name)
    return {"format": FORMAT, "collection": name, "league": "fbcyl" if is_fbcyl(name) else "feb", "teams": teams}
