"""The id of the team on every row of team stats.

The FEB team pipelines group by the team id and leave it in ``_id``; the web draws the crest of a team from ``team_id`` (TeamCell). One
place for both services that hand team rows to the web: the team stats and the sum of several phases (Multifase).
"""
from typing import Dict, List, Optional


def with_team_id(rows: Optional[List[Dict]]) -> List[Dict]:
    """Give every row its ``team_id`` (from ``_id`` when the pipeline left it there), in place; ``None`` is an empty list."""
    for row in rows or []:
        if not row.get("team_id"):
            row["team_id"] = row.get("_id")
    return rows or []
