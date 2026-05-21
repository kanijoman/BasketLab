"""Utility functions for team data extraction from MongoDB documents.

Moved from src/ui/team_utils.py (Qt UI layer removed).
Used by services that need to identify teams within match documents.
"""

from typing import List, Dict, Optional, Any

from src.utils.collection_utils import is_fbcyl as _is_fbcyl

# Minimal projections for team-discovery queries — exclude large PBP / box-score arrays.
_TEAM_PROJECTION_FEB = {
    "BOXSCORE.TEAM.TOTAL.teamCode": 1,
    "BOXSCORE.TEAM.TOTAL.name": 1,
    "BOXSCORE.TEAM.TOTAL.id": 1,
    "HEADER.TEAM.teamCode": 1,
    "HEADER.TEAM.name": 1,
    "HEADER.TEAM.id": 1,
    "_id": 0,
}
_TEAM_PROJECTION_FBCYL = {
    "stats.teams.name": 1,
    "stats.teams.teamIdExtern": 1,
    "stats.teams.teamIdIntern": 1,
    "_id": 0,
}


def _collect_fbcyl_teams(documents: List[Dict], teams_dict: Dict) -> None:
    """Populate *teams_dict* from FBCYL-format game documents (in-place)."""
    for doc in documents:
        stats = doc.get("stats", {})
        for team in stats.get("teams", []):
            if not isinstance(team, dict):
                continue
            team_name = team.get("name", "")
            team_id = team.get("teamIdExtern", team.get("teamIdIntern", ""))
            if team_name and team_name not in teams_dict:
                teams_dict[team_name] = {
                    "name": team_name,
                    "code": str(team_id),
                    "id": team_id,
                    "team_index": None,
                }


def _collect_feb_teams(documents: List[Dict], teams_dict: Dict) -> None:
    """Populate *teams_dict* from FEB-format game documents (in-place)."""
    for doc in documents:
        if "BOXSCORE" in doc and "TEAM" in doc["BOXSCORE"]:
            for team in doc["BOXSCORE"]["TEAM"]:
                if not (isinstance(team, dict) and "TOTAL" in team):
                    continue
                td = team["TOTAL"]
                code, name, tid = td.get("teamCode", ""), td.get("name", ""), td.get("id", "")
                if code and name and code not in teams_dict:
                    teams_dict[code] = {"name": name, "code": code, "id": tid, "team_index": None}
        elif "HEADER" in doc and "TEAM" in doc["HEADER"]:
            for team in doc["HEADER"]["TEAM"]:
                if not isinstance(team, dict):
                    continue
                code, name, tid = team.get("teamCode", ""), team.get("name", ""), team.get("id", "")
                if code and name and code not in teams_dict:
                    teams_dict[code] = {"name": name, "code": code, "id": tid, "team_index": None}


def resolve_team_by_id(coll: Any, team_id: str, is_fbcyl: bool) -> Optional[Dict[str, str]]:
    """Return ``{id, name}`` for a team given its stable ID, or ``None`` if not found.

    Uses one indexed ``find_one`` query — safe to call per-request.

    Args:
        coll: PyMongo collection object.
        team_id: Stable team identifier (``HEADER.TEAM.id`` for FEB,
            ``stats.teams.teamIdExtern`` for FBCYL).
        is_fbcyl: True for FBCYL collections.

    Returns:
        ``{"id": str, "name": str}`` or ``None``.
    """
    try:
        if is_fbcyl:
            tid = int(team_id) if isinstance(team_id, str) and team_id.isdigit() else team_id
            doc = coll.find_one(
                {"stats.teams.teamIdExtern": tid},
                {"stats.teams": 1, "_id": 0},
            )
            if not doc:
                return None
            for t in doc.get("stats", {}).get("teams", []):
                if str(t.get("teamIdExtern", "")) == str(team_id):
                    return {"id": str(t["teamIdExtern"]), "name": t.get("name", "")}
        else:
            doc = coll.find_one(
                {"HEADER.TEAM.id": team_id},
                {"HEADER.TEAM": 1, "_id": 0},
            )
            if not doc:
                return None
            for t in doc.get("HEADER", {}).get("TEAM", []):
                if str(t.get("id", "")) == str(team_id):
                    return {"id": str(t["id"]), "name": t.get("name", "")}
    except Exception:
        pass
    return None


def get_available_teams_from_collection(db_handler, collection_name: str) -> List[Dict]:
    """Extract available teams from a MongoDB collection.

    Searches both BOXSCORE.TEAM and HEADER.TEAM nodes (FEB) or teams (FBCYL)
    to find unique teams in the collection.

    Returns:
        List of team dicts with keys: name, code, id, team_index — sorted by name.
    """
    try:
        collection = db_handler.connection.get_collection(collection_name)
        if collection is None:
            return []

        is_fbcyl = _is_fbcyl(collection_name)
        projection = _TEAM_PROJECTION_FBCYL if is_fbcyl else _TEAM_PROJECTION_FEB
        documents = list(collection.find({}, projection))
        teams_dict: Dict = {}

        if is_fbcyl:
            _collect_fbcyl_teams(documents, teams_dict)
        else:
            _collect_feb_teams(documents, teams_dict)

        return sorted(teams_dict.values(), key=lambda x: x["name"])

    except Exception:
        return []


def get_team_index_in_document(doc: Dict, team_code: str) -> Optional[int]:
    """Determine team index (0 or 1) in a match document by team code or ID."""
    team_code_str = str(team_code)

    if "BOXSCORE" in doc and "TEAM" in doc["BOXSCORE"]:
        teams = doc["BOXSCORE"]["TEAM"]
        if isinstance(teams, list):
            for idx, team_data in enumerate(teams):
                if isinstance(team_data, dict) and "TOTAL" in team_data:
                    total = team_data["TOTAL"]
                    if (
                        str(total.get("teamCode", "")) == team_code_str
                        or str(total.get("id", "")) == team_code_str
                    ):
                        return idx

    if "HEADER" in doc and "TEAM" in doc["HEADER"]:
        teams = doc["HEADER"]["TEAM"]
        if isinstance(teams, list):
            for idx, team_data in enumerate(teams):
                if isinstance(team_data, dict):
                    if (
                        str(team_data.get("teamCode", "")) == team_code_str
                        or str(team_data.get("id", "")) == team_code_str
                    ):
                        return idx

    return None


def extract_player_names_from_boxscore(doc: Dict, team_index: int) -> Dict[str, str]:
    """Extract player names from BOXSCORE for a specific team index.

    Returns:
        Dict mapping dorsal number to player name.
    """
    players_info = {}
    if "BOXSCORE" in doc and "TEAM" in doc["BOXSCORE"]:
        teams = doc["BOXSCORE"]["TEAM"]
        if isinstance(teams, list) and len(teams) > team_index:
            team_data = teams[team_index]
            if "PLAYER" in team_data:
                for player in team_data["PLAYER"]:
                    dorsal = str(player.get("no", "")).lstrip("0") or player.get("no", "")
                    name = player.get("name", "")
                    if dorsal and name:
                        players_info[dorsal] = name
    return players_info


def get_team_data_by_name(
    doc: Dict, team_name: str
) -> "tuple[Optional[Dict], Optional[int]]":
    """Find team data and its index in a match document by team name.

    Returns:
        Tuple of (team_data, team_index) or (None, None) if not found.
    """
    if "stats" in doc and "teams" in doc["stats"]:
        teams = doc["stats"]["teams"]
        if isinstance(teams, list):
            for idx, team in enumerate(teams):
                if isinstance(team, dict) and team.get("name", "") == team_name:
                    return team, idx
        return None, None

    if "BOXSCORE" in doc and "TEAM" in doc["BOXSCORE"]:
        teams = doc["BOXSCORE"]["TEAM"]
        if isinstance(teams, list):
            for idx, team_data in enumerate(teams):
                if isinstance(team_data, dict) and "TOTAL" in team_data:
                    if team_data["TOTAL"].get("name", "") == team_name:
                        return team_data["TOTAL"], idx

    if "HEADER" in doc and "TEAM" in doc["HEADER"]:
        teams = doc["HEADER"]["TEAM"]
        if isinstance(teams, list):
            for idx, team_data in enumerate(teams):
                if isinstance(team_data, dict):
                    if team_data.get("name", "") == team_name:
                        return team_data, idx

    return None, None
