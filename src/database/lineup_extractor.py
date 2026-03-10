"""Lineup extractor to identify player combinations on court from play-by-play data."""

from typing import Dict, List, Set, Tuple, FrozenSet, Optional
from collections import defaultdict
from .playbyplay_analyzer import PlayByPlayAnalyzer


class LineupExtractor:
    """Extracts lineup combinations (5, 4, or 3 players) from play-by-play data."""

    def __init__(self, analyzer: PlayByPlayAnalyzer):
        """
        Initialize the lineup extractor.

        Args:
            analyzer: PlayByPlayAnalyzer instance with parsed substitution data
        """
        self.analyzer = analyzer
        self.is_fbcyl = analyzer.is_fbcyl
        self.game_data = analyzer.game_data
        
        # Cache substitutions and segments for performance
        self._substitutions_cache = None
        self._segments_cache = {}

    def get_lineup_at_timestamp(self, team_id: str, timestamp_seconds: int) -> Set[str]:
        """
        Get set of player IDs on court for a team at specific timestamp.

        Args:
            team_id: Team identifier
            timestamp_seconds: Absolute seconds from game start

        Returns:
            Set of player IDs (maximum 5) on court at that timestamp
        """
        # Ensure substitutions are parsed (only once)
        if self._substitutions_cache is None:
            self._substitutions_cache = self.analyzer.parse_substitutions()
        
        # Build timeline of who's on court
        on_court = set()
        
        # Get all players from this team
        team_players = self._get_team_players(team_id)
        
        # For each player, check if they're on court at timestamp (use cached segments)
        for player_id in team_players:
            if player_id not in self._segments_cache:
                self._segments_cache[player_id] = self.analyzer.get_player_court_segments(player_id)
            
            segments = self._segments_cache[player_id]
            for start, end in segments:
                if start <= timestamp_seconds <= end:
                    on_court.add(player_id)
                    break
        
        return on_court if len(on_court) <= 5 else set(list(on_court)[:5])

    def get_all_lineups_for_team(
        self, 
        team_id: str, 
        combination_size: int = 5,
        min_seconds: int = 120
    ) -> List[Tuple[FrozenSet[str], int, int]]:
        """
        Get all unique lineup combinations for a team that meet minimum time threshold.

        Args:
            team_id: Team identifier
            combination_size: Number of players in combination (3, 4, or 5)
            min_seconds: Minimum seconds together to be considered valid lineup

        Returns:
            List of tuples: (frozenset of player IDs, start_time, end_time)
        """
        # Get game duration (40 minutes = 2400 seconds for regulation)
        game_duration = self._get_game_duration()
        
        # Track lineup state changes
        lineup_segments = []
        current_lineup = None
        segment_start = 0
        
        # Sample every 5 seconds to detect lineup changes (high precision)
        for timestamp in range(0, game_duration, 5):
            lineup_at_time = self.get_lineup_at_timestamp(team_id, timestamp)
            
            # Only consider lineups with exactly 5 players (full lineup)
            if len(lineup_at_time) == 5:
                lineup_key = frozenset(lineup_at_time)
                
                if lineup_key != current_lineup:
                    # Lineup changed, save previous segment
                    if current_lineup is not None:
                        segment_duration = timestamp - segment_start
                        if segment_duration >= min_seconds:
                            lineup_segments.append((current_lineup, segment_start, timestamp))
                    
                    current_lineup = lineup_key
                    segment_start = timestamp
            else:
                # Less than 5 players (substitution in progress), close current segment
                if current_lineup is not None:
                    segment_duration = timestamp - segment_start
                    if segment_duration >= min_seconds:
                        lineup_segments.append((current_lineup, segment_start, timestamp))
                    current_lineup = None
        
        # Don't forget last segment
        if current_lineup is not None:
            segment_duration = game_duration - segment_start
            if segment_duration >= min_seconds:
                lineup_segments.append((current_lineup, segment_start, game_duration))
        
        return lineup_segments

    def _get_team_players(self, team_id: str) -> Set[str]:
        """Get all player IDs for a team."""
        players = set()
        
        if self.is_fbcyl:
            # FBCYL format
            stats = self.game_data.get('stats', {})
            teams = stats.get('teams', [])
            
            for team in teams:
                # Match by teamIdIntern (used in moves) or teamIdExtern
                if team.get('teamIdIntern') == team_id or team.get('teamIdExtern') == team_id:
                    for player in team.get('players', []):
                        # Use actorId for single-game analysis
                        player_id = player.get('actorId')
                        if player_id:
                            players.add(str(player_id))
                    break
        else:
            # FEB format
            boxscore = self.game_data.get('BOXSCORE', {})
            teams = boxscore.get('TEAM', [])
            
            for team in teams:
                if team.get('id') == team_id:
                    for player in team.get('PLAYER', []):
                        player_id = player.get('id')  # FEB uses 'id' in BOXSCORE, not 'license'
                        if player_id:
                            players.add(str(player_id))
                    break
        
        return players

    def _get_game_duration(self) -> int:
        """
        Get total game duration in seconds.
        
        For regulation games, this is 2400 seconds (40 minutes).
        Handles overtime if present.
        """
        # Check for overtime by examining play-by-play
        max_quarter = 4
        
        if self.is_fbcyl:
            moves = self.game_data.get('moves', [])
            for move in moves:
                period = move.get('period', 0)
                if period > max_quarter:
                    max_quarter = period
        else:
            lines = self.analyzer.lines
            for line in lines:
                try:
                    quarter = int(line.get('quarter', 4))
                    if quarter > max_quarter:
                        max_quarter = quarter
                except (ValueError, TypeError):
                    pass
        
        # Each quarter is 600 seconds (10 minutes)
        # Overtime periods are 300 seconds (5 minutes)
        regulation_time = 2400  # 4 quarters
        if max_quarter > 4:
            overtime_periods = max_quarter - 4
            return regulation_time + (overtime_periods * 300)
        
        return regulation_time

    def detect_starting_lineup(self, team_id: str) -> Set[str]:
        """
        Detect the starting 5 players for a team.

        Args:
            team_id: Team identifier

        Returns:
            Set of 5 player IDs who started the game
        """
        # Get lineup at game start (timestamp 0)
        starting_5 = self.get_lineup_at_timestamp(team_id, 0)
        
        # If we don't detect exactly 5, try first 30 seconds
        if len(starting_5) != 5:
            for t in range(10, 60, 10):
                lineup = self.get_lineup_at_timestamp(team_id, t)
                if len(lineup) == 5:
                    return lineup
        
        return starting_5

    def get_lineup_combinations(
        self,
        team_id: str,
        combination_size: int,
        min_seconds: int = 120
    ) -> Dict[FrozenSet[str], int]:
        """
        Get all unique N-player combinations and their total time together.

        Args:
            team_id: Team identifier
            combination_size: Size of combination (3, 4, or 5)
            min_seconds: Minimum seconds to be considered valid

        Returns:
            Dict mapping frozenset of player IDs to total seconds together
        """
        from itertools import combinations
        
        # Get all 5-player lineups first
        lineups_5 = self.get_all_lineups_for_team(team_id, 5, 0)
        
        # Track time for each N-player combination
        combination_time = defaultdict(int)
        
        if combination_size == 5:
            # Direct: aggregate time for each 5-player lineup
            for lineup, start, end in lineups_5:
                duration = end - start
                combination_time[lineup] += duration
        else:
            # Generate subsets from 5-player lineups
            for lineup_5, start, end in lineups_5:
                duration = end - start
                
                # Generate all N-size combinations from this 5-player lineup
                for combo in combinations(lineup_5, combination_size):
                    combo_key = frozenset(combo)
                    combination_time[combo_key] += duration
        
        # Filter by minimum time
        filtered = {
            combo: time for combo, time in combination_time.items()
            if time >= min_seconds
        }
        
        return filtered
