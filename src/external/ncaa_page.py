"""What the NCAA reader takes from the answers of ESPN (#888, D4 of epic #872; #966).

ESPN is read as JSON. Here only the answers that tell WHICH competitions exist and WHO plays in each: the conferences of a season and the standings of that season, which give every team the conference
it played in THAT season (a team that changes conference between two seasons has the old one in the old season: realignments do not rewrite the past). An answer whose shape is not the one
expected is a ``NcaaPageError`` and is never read as an empty season: a quiet empty list would hide that ESPN changed.
"""
from __future__ import annotations

from typing import Any, Dict, List

DIVISION_GROUP = "50"                    # «Division I», the group of all the conferences: the id ESPN asks for, not a conference


class NcaaPageError(Exception):
    """The answer is not in a format the reader knows (asking again would not change it, so it is not retried)."""


def _list(data: Any, key: str) -> List[Dict[str, Any]]:
    items = data.get(key) if isinstance(data, dict) else None
    if not isinstance(items, list) or not items or not all(isinstance(i, dict) for i in items):
        raise NcaaPageError(f"the answer has no '{key}' list")
    return items


def parse_conferences(data: Any) -> List[Dict[str, str]]:
    """``[{id, name, short}]`` of the conferences a season has (the division itself is not one). ``short`` is the name the fans use («ACC», «Big 12»), the one the catalogue and the collections carry."""
    out = []
    for item in _list(data, "conferences"):
        group, name = item.get("groupId"), item.get("name")
        if not group or not name:
            raise NcaaPageError(f"a conference lacks its id or its name: {item}")
        if str(group) != DIVISION_GROUP:
            out.append({"id": str(group), "name": str(name), "short": str(item.get("shortName") or name)})
    if not out:
        raise NcaaPageError("the answer lists no conference")
    return out


def parse_standings(data: Any) -> Dict[str, Dict[str, str]]:
    """``{team id: {name, conference_id, conference}}``: the conference each team played in, from the standings of the season."""
    teams: Dict[str, Dict[str, str]] = {}
    for conference in _list(data, "children"):
        if not conference.get("id") or not conference.get("name") or not isinstance(conference.get("standings", {}).get("entries"), list):
            raise NcaaPageError(f"a conference of the standings lacks its id, its name or its teams: {sorted(conference)}")
        for entry in conference["standings"]["entries"]:
            team = entry.get("team") or {}
            if not team.get("id"):
                raise NcaaPageError(f"a team of the standings lacks its id: {entry}")
            teams[str(team["id"])] = {"name": str(team.get("displayName") or ""), "conference_id": str(conference["id"]), "conference": str(conference["name"])}
    if not teams:
        raise NcaaPageError("the standings list no team")
    return teams
