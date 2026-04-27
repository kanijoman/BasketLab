"""Utility functions for team data extraction from MongoDB documents.

Moved from src/ui/team_utils.py (Qt UI layer removed).
Used by services that need to identify teams within match documents.
"""

from typing import List, Dict, Optional

from src.utils.collection_utils import is_fbcyl as _is_fbcyl


def get_available_teams_from_collection(db_handler, collection_name: str) -> List[Dict]:
    """
    Extract available teams from a MongoDB collection.

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
        documents = list(collection.find({}))
        teams_dict = {}

        if is_fbcyl:
            for doc in documents:
                if "stats" in doc and "teams" in doc["stats"]:
                    teams = doc["stats"]["teams"]
                    if isinstance(teams, list):
                        for team in teams:
                            if isinstance(team, dict):
                                team_name = team.get("name", "")
                                team_id = team.get(
                                    "teamIdExtern", team.get("teamIdIntern", "")
                                )
                                if team_name and team_name not in teams_dict:
                                    teams_dict[team_name] = {
                                        "name": team_name,
                                        "code": str(team_id),
                                        "id": team_id,
                                        "team_index": None,
                                    }
        else:
            for doc in documents:
                if "BOXSCORE" in doc and "TEAM" in doc["BOXSCORE"]:
                    teams = doc["BOXSCORE"]["TEAM"]
                    if isinstance(teams, list):
                        for team in teams:
                            if isinstance(team, dict) and "TOTAL" in team:
                                team_data = team["TOTAL"]
                                team_code = team_data.get("teamCode", "")
                                team_name = team_data.get("name", "")
                                team_id = team_data.get("id", "")
                                if team_code and team_name and team_code not in teams_dict:
                                    teams_dict[team_code] = {
                                        "name": team_name,
                                        "code": team_code,
                                        "id": team_id,
                                        "team_index": None,
                                    }
                elif "HEADER" in doc and "TEAM" in doc["HEADER"]:
                    teams = doc["HEADER"]["TEAM"]
                    if isinstance(teams, list):
                        for team in teams:
                            if isinstance(team, dict):
                                team_code = team.get("teamCode", "")
                                team_name = team.get("name", "")
                                team_id = team.get("id", "")
                                if team_code and team_name and team_code not in teams_dict:
                                    teams_dict[team_code] = {
                                        "name": team_name,
                                        "code": team_code,
                                        "id": team_id,
                                        "team_index": None,
                                    }

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
