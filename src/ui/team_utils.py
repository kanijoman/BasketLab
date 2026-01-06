"""Utility functions for team management across UI modules."""

from typing import List, Dict, Optional


def get_available_teams_from_collection(db_handler, collection_name: str) -> List[Dict]:
    """
    Extract available teams from a MongoDB collection.

    This function searches both BOXSCORE.TEAM and HEADER.TEAM nodes (FEB)
    or teams (FBCYL) to find unique teams in the collection.

    Args:
        db_handler: MongoDBHandler instance
        collection_name: Name of the MongoDB collection

    Returns:
        List of team dictionaries with keys: name, code, id, team_index
        Sorted alphabetically by team name
    """
    try:
        collection = db_handler.connection.get_collection(collection_name)
        if collection is None:
            return []

        # Detect if this is FBCYL format
        is_fbcyl = collection_name.startswith('FBCYL_')

        documents = list(collection.find({}))
        teams_dict = {}

        if is_fbcyl:
            # FBCYL format: stats.teams[]
            for doc in documents:
                if 'stats' in doc and 'teams' in doc['stats']:
                    teams = doc['stats']['teams']
                    if isinstance(teams, list):
                        for team in teams:
                            if isinstance(team, dict):
                                team_name = team.get('name', '')
                                team_id = team.get('teamIdExtern', team.get('teamIdIntern', ''))

                                if team_name and team_name not in teams_dict:
                                    teams_dict[team_name] = {
                                        'name': team_name,
                                        'code': str(team_id),  # Use team ID as code for FBCYL
                                        'id': team_id,
                                        'team_index': None
                                    }
        else:
            # FEB format
            for doc in documents:
                # Primary source: BOXSCORE.TEAM list
                if 'BOXSCORE' in doc and 'TEAM' in doc['BOXSCORE']:
                    teams = doc['BOXSCORE']['TEAM']
                    if isinstance(teams, list):
                        for team in teams:
                            if isinstance(team, dict) and 'TOTAL' in team:
                                team_data = team['TOTAL']
                                team_code = team_data.get('teamCode', '')
                                team_name = team_data.get('name', '')
                                team_id = team_data.get('id', '')

                                if team_code and team_name and team_code not in teams_dict:
                                    teams_dict[team_code] = {
                                        'name': team_name,
                                        'code': team_code,
                                        'id': team_id,
                                        'team_index': None
                                    }

                # Fallback: HEADER.TEAM
                elif 'HEADER' in doc and 'TEAM' in doc['HEADER']:
                    teams = doc['HEADER']['TEAM']
                    if isinstance(teams, list):
                        for team in teams:
                            if isinstance(team, dict):
                                team_code = team.get('teamCode', '')
                                team_name = team.get('name', '')
                                team_id = team.get('id', '')

                                if team_code and team_name and team_code not in teams_dict:
                                    teams_dict[team_code] = {
                                        'name': team_name,
                                        'code': team_code,
                                        'id': team_id,
                                        'team_index': None
                                    }

        return sorted(teams_dict.values(), key=lambda x: x['name'])

    except Exception:
        return []


def get_team_index_in_document(doc: Dict, team_code: str) -> Optional[int]:
    """
    Determine team index (0 or 1) in a match document.

    Args:
        doc: Match document from MongoDB
        team_code: Team code or ID to search for

    Returns:
        Team index (0 or 1) or None if not found
    """
    # Normalize team_code to string for comparison
    team_code_str = str(team_code)
    
    # Check BOXSCORE.TEAM array
    if 'BOXSCORE' in doc and 'TEAM' in doc['BOXSCORE']:
        teams = doc['BOXSCORE']['TEAM']
        if isinstance(teams, list):
            for idx, team_data in enumerate(teams):
                if isinstance(team_data, dict) and 'TOTAL' in team_data:
                    total = team_data['TOTAL']
                    # Check both teamCode and id
                    if (str(total.get('teamCode', '')) == team_code_str or 
                        str(total.get('id', '')) == team_code_str):
                        return idx

    # Fallback: check HEADER.TEAM
    if 'HEADER' in doc and 'TEAM' in doc['HEADER']:
        teams = doc['HEADER']['TEAM']
        if isinstance(teams, list):
            for idx, team_data in enumerate(teams):
                if isinstance(team_data, dict):
                    # Check both teamCode and id
                    if (str(team_data.get('teamCode', '')) == team_code_str or
                        str(team_data.get('id', '')) == team_code_str):
                        return idx

    return None


def extract_player_names_from_boxscore(doc: Dict, team_index: int) -> Dict[str, str]:
    """
    Extract player names from BOXSCORE for a specific team.

    Args:
        doc: Match document from MongoDB
        team_index: Team index (0 or 1)

    Returns:
        Dictionary mapping dorsal number to player name
    """
    players_info = {}

    if 'BOXSCORE' in doc and 'TEAM' in doc['BOXSCORE']:
        teams = doc['BOXSCORE']['TEAM']
        if isinstance(teams, list) and len(teams) > team_index:
            team_data = teams[team_index]
            if 'PLAYER' in team_data:
                for player in team_data['PLAYER']:
                    dorsal = str(player.get('no', '')).lstrip('0') or player.get('no', '')
                    name = player.get('name', '')
                    if dorsal and name:
                        players_info[dorsal] = name

    return players_info


def get_team_data_by_name(doc: Dict, team_name: str) -> tuple[Optional[Dict], Optional[int]]:
    """
    Find team data in a match document by team name.

    Args:
        doc: Match document from MongoDB
        team_name: Name of the team to find

    Returns:
        Tuple of (team_data, team_index) or (None, None) if not found
    """
    # Check if this is FBCYL format
    if 'stats' in doc and 'teams' in doc['stats']:
        # FBCYL format: stats.teams[]
        teams = doc['stats']['teams']
        if isinstance(teams, list):
            for idx, team in enumerate(teams):
                if isinstance(team, dict) and team.get('name', '') == team_name:
                    return team, idx
        return None, None

    # FEB format: Check BOXSCORE.TEAM array
    if 'BOXSCORE' in doc and 'TEAM' in doc['BOXSCORE']:
        teams = doc['BOXSCORE']['TEAM']
        if isinstance(teams, list):
            for idx, team_data in enumerate(teams):
                if isinstance(team_data, dict) and 'TOTAL' in team_data:
                    if team_data['TOTAL'].get('name', '') == team_name:
                        return team_data['TOTAL'], idx

    # Fallback: check HEADER.TEAM
    if 'HEADER' in doc and 'TEAM' in doc['HEADER']:
        teams = doc['HEADER']['TEAM']
        if isinstance(teams, list):
            for idx, team_data in enumerate(teams):
                if isinstance(team_data, dict):
                    if team_data.get('name', '') == team_name:
                        return team_data, idx

    return None, None
