"""Helper methods for IN/OUT repository operations."""

from typing import Dict, List, Tuple, Optional, NamedTuple


class PlayerGameInfo(NamedTuple):
    """Container for player information in a specific game."""
    player1_actor_id: Optional[str]
    player2_actor_id: Optional[str]
    team_id: Optional[str]
    all_found: bool


class InOutRepositoryHelper:
    """Helper methods to reduce complexity in BasketballRepository IN/OUT operations."""

    @staticmethod
    def find_players_in_game(game: Dict, player1_id: str, player2_id: str,
                            is_fbcyl: bool) -> PlayerGameInfo:
        """
        Find both players and their team in a specific game.

        Args:
            game: Game document
            player1_id: First player's ID
            player2_id: Second player's ID
            is_fbcyl: Whether this is FBCYL format

        Returns:
            PlayerGameInfo with actor IDs and team ID
        """
        if is_fbcyl:
            return InOutRepositoryHelper._find_players_fbcyl(game, player1_id, player2_id)
        else:
            return InOutRepositoryHelper._find_players_feb(game, player1_id, player2_id)

    @staticmethod
    def _find_players_fbcyl(game: Dict, player1_id: str, player2_id: str) -> PlayerGameInfo:
        """Find players in FBCYL format game."""
        player1_actor_id = None
        player2_actor_id = None
        team_id = None

        stats = game.get('stats', {})
        for team in stats.get('teams', []):
            for player in team.get('players', []):
                player_uuid = player.get('uuid')
                
                if player_uuid == player1_id:
                    player1_actor_id = player.get('actorId')
                    team_id = team.get('teamIdIntern') or team.get('teamIdExtern')
                elif player_uuid == player2_id:
                    player2_actor_id = player.get('actorId')
                    if not team_id:
                        team_id = team.get('teamIdIntern') or team.get('teamIdExtern')

        all_found = bool(player1_actor_id and player2_actor_id and team_id)
        return PlayerGameInfo(player1_actor_id, player2_actor_id, team_id, all_found)

    @staticmethod
    def _find_players_feb(game: Dict, player1_id: str, player2_id: str) -> PlayerGameInfo:
        """Find players in FEB format game."""
        player1_found = False
        player2_found = False
        team_id = None

        boxscore = game.get('BOXSCORE', {})
        teams = boxscore.get('TEAM', [])

        for team in teams:
            players = team.get('PLAYER', [])
            for player in players:
                if player.get('id') == player1_id:
                    player1_found = True
                    team_id = team.get('id')
                elif player.get('id') == player2_id:
                    player2_found = True
                    if not team_id:
                        team_id = team.get('id')

        all_found = bool(player1_found and player2_found and team_id)
        return PlayerGameInfo(player1_id, player2_id, team_id, all_found)

    @staticmethod
    def calculate_overlap_segments(segments1: List[Tuple[int, int]],
                                  segments2: List[Tuple[int, int]]) -> List[Tuple[int, int]]:
        """
        Calculate time segments when both players are on court together.

        Args:
            segments1: Time segments for player 1
            segments2: Time segments for player 2

        Returns:
            List of overlapping time segments
        """
        together_segments = []
        
        for s1_start, s1_end in segments1:
            for s2_start, s2_end in segments2:
                overlap_start = max(s1_start, s2_start)
                overlap_end = min(s1_end, s2_end)
                if overlap_start < overlap_end:
                    together_segments.append((overlap_start, overlap_end))
        
        return together_segments

    @staticmethod
    def filter_actions_by_segments(analyzer, segments: List[Tuple[int, int]],
                                   is_fbcyl: bool) -> List[Dict]:
        """
        Filter actions that occurred during specified time segments.

        Args:
            analyzer: PlayByPlayAnalyzer instance
            segments: List of (start, end) time segments in seconds
            is_fbcyl: Whether this is FBCYL format

        Returns:
            List of actions that occurred during segments
        """
        actions = []
        lines = analyzer.lines or []

        if is_fbcyl:
            for move in lines:
                period = move.get('period')
                min_val = move.get('min')
                sec_val = move.get('sec')

                if period is None or min_val is None or sec_val is None:
                    continue

                timestamp = analyzer._fbcyl_time_to_seconds(period, min_val, sec_val)

                if InOutRepositoryHelper._is_in_segments(timestamp, segments):
                    actions.append(move)
        else:
            for line in reversed(lines):
                quarter = line.get('quarter')
                time_str = line.get('time')

                if not quarter or not time_str:
                    continue

                timestamp = analyzer._time_to_seconds(quarter, time_str)

                if InOutRepositoryHelper._is_in_segments(timestamp, segments):
                    actions.append(line)

        return actions

    @staticmethod
    def _is_in_segments(timestamp: int, segments: List[Tuple[int, int]]) -> bool:
        """Check if timestamp falls within any segment."""
        for start, end in segments:
            if start <= timestamp <= end:
                return True
        return False

    @staticmethod
    def find_opponent_team_id(game: Dict, team_id: str, is_fbcyl: bool) -> Optional[str]:
        """
        Find the opponent team ID in a game.

        Args:
            game: Game document
            team_id: Known team ID
            is_fbcyl: Whether this is FBCYL format

        Returns:
            Opponent team ID or None
        """
        if is_fbcyl:
            stats = game.get('stats', {})
            for team in stats.get('teams', []):
                tid = team.get('teamIdIntern') or team.get('teamIdExtern')
                if tid != team_id:
                    return tid
        else:
            teams = game.get('HEADER', {}).get('TEAM', [])
            for team in teams:
                tid = team.get('id')
                if tid != team_id:
                    return tid
        
        return None

    @staticmethod
    def calculate_total_time(segments: List[Tuple[int, int]]) -> float:
        """
        Calculate total time in minutes from segments.

        Args:
            segments: List of (start, end) time segments in seconds

        Returns:
            Total time in minutes
        """
        total_seconds = sum(end - start for start, end in segments)
        return total_seconds / 60.0
