"""Data processing for boxscore and match data."""

from typing import Dict, Optional


class DataProcessor:
    """Processes and enriches match data."""

    @staticmethod
    def process_boxscore(data: Dict, match_code: str) -> Optional[Dict]:
        """
        Process boxscore data to add games_played and win_lose.

        Args:
            data: Raw boxscore data
            match_code: Match identifier

        Returns:
            Processed data dictionary or None if invalid
        """
        if not DataProcessor._validate_boxscore_structure(data, match_code):
            return data

        # Add game_code to header
        data["HEADER"] = data.get("HEADER", {})
        data["HEADER"]["game_code"] = int(match_code)

        team_list = data["BOXSCORE"]["TEAM"]

        # Process players
        DataProcessor._add_games_played_to_players(team_list, match_code)

        # Process teams
        DataProcessor._add_win_lose_to_teams(team_list, match_code)

        return data

    @staticmethod
    def _validate_boxscore_structure(data: Dict, match_code: str) -> bool:
        """Validate that boxscore has the expected structure."""
        if not isinstance(data, dict) or "BOXSCORE" not in data:
            print(f"[DataProcessor] Invalid or missing BOXSCORE for match {match_code}")
            return False

        if "TEAM" not in data["BOXSCORE"]:
            print(f"[DataProcessor] Invalid or missing BOXSCORE.TEAM for match {match_code}")
            return False

        team_list = data["BOXSCORE"]["TEAM"]
        if not isinstance(team_list, list) or len(team_list) != 2:
            print(f"[DataProcessor] Invalid TEAM structure for match {match_code}: Expected list of 2 teams")
            return False

        return True

    @staticmethod
    def _add_games_played_to_players(team_list: list, match_code: str):
        """
        Add games_played field to each player based on minutes played.

        Args:
            team_list: List of team dictionaries
            match_code: Match identifier
        """
        for team in team_list:
            if not isinstance(team, dict) or "PLAYER" not in team:
                print(f"[DataProcessor] Invalid PLAYER structure for team {team.get('name', 'Unknown')} in match {match_code}")
                continue

            if not isinstance(team["PLAYER"], list):
                print(f"[DataProcessor] PLAYER is not a list for team {team.get('name', 'Unknown')} in match {match_code}")
                continue

            for player in team["PLAYER"]:
                if not isinstance(player, dict):
                    continue

                if "min" not in player or not isinstance(player["min"], str):
                    print(f"[DataProcessor] Invalid or missing min for player {player.get('name', 'Unknown')} in match {match_code}")
                    player["games_played"] = 0
                    continue

                try:
                    minutes = int(player["min"])
                    player["games_played"] = 1 if minutes != 0 else 0
                except ValueError:
                    print(f"[DataProcessor] Invalid min value for player {player.get('name', 'Unknown')} in match {match_code}: {player['min']}")
                    player["games_played"] = 0

    @staticmethod
    def _add_win_lose_to_teams(team_list: list, match_code: str):
        """
        Add win_lose field to teams based on final score.

        Args:
            team_list: List of team dictionaries (must have exactly 2 teams)
            match_code: Match identifier
        """
        team1, team2 = team_list

        # Validate team structure
        if not DataProcessor._validate_team_total(team1, match_code) or \
           not DataProcessor._validate_team_total(team2, match_code):
            team1["win_lose"] = team2["win_lose"] = "E"
            return

        # Calculate win/lose
        try:
            pts1 = int(team1["TOTAL"]["pts"])
            pts2 = int(team2["TOTAL"]["pts"])

            if pts1 > pts2:
                team1["win_lose"], team2["win_lose"] = "W", "L"
            elif pts1 < pts2:
                team1["win_lose"], team2["win_lose"] = "L", "W"
            else:
                team1["win_lose"], team2["win_lose"] = "E", "E"  # Tie (Empate)
        except ValueError:
            print(f"[DataProcessor] Invalid pts value for match {match_code}: "
                  f"Team1 pts={team1['TOTAL'].get('pts', 'Missing')}, "
                  f"Team2 pts={team2['TOTAL'].get('pts', 'Missing')}")
            team1["win_lose"] = team2["win_lose"] = "E"

    @staticmethod
    def _validate_team_total(team: Dict, match_code: str) -> bool:
        """Validate that team has TOTAL.pts field."""
        if not isinstance(team, dict):
            return False
        if "TOTAL" not in team or not isinstance(team["TOTAL"], dict):
            return False
        if "pts" not in team["TOTAL"]:
            print(f"[DataProcessor] Missing pts for team in match {match_code}")
            return False
        return True
