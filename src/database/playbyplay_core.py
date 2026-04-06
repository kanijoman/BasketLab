"""Play-by-play analyzer to track player court time and calculate IN/OUT statistics."""

from typing import Dict, List, Set, Tuple, Optional, Any
from collections import defaultdict
import re


class PlayByPlayAnalyzer:
    """Analyzes play-by-play data to determine when players are on/off court."""

    def __init__(self, game_data: Dict, is_fbcyl: bool = False):
        """
        Initialize the play-by-play analyzer.

        Args:
            game_data: The complete game JSON data including PLAYBYPLAY (FEB) or moves (FBCYL)
            is_fbcyl: Whether this is FBCYL data format
        """
        self.game_data = game_data
        self.is_fbcyl = is_fbcyl

        if is_fbcyl:
            # FBCYL: moves are directly in 'moves' key (list)
            self.lines = game_data.get('moves', [])
            # Build actorId → licenseId map for stable cross-game player identity.
            # actorId is game-scoped (changes every game); licenseId is the
            # persistent FEB player identifier and must be used as lineup keys.
            self._fbcyl_actor_to_license: Dict = {}
            for move in self.lines:
                aid = move.get('actorId')
                lid = move.get('licenseId')
                if aid is not None and lid is not None:
                    self._fbcyl_actor_to_license[aid] = str(lid)
        else:
            # FEB: play-by-play in PLAYBYPLAY.LINES
            self.playbyplay = game_data.get('PLAYBYPLAY', {})
            self.lines = self.playbyplay.get('LINES', [])

        # Track players on court for each team throughout the game
        self.court_state = {
            'team1': set(),
            'team2': set()
        }

        # Map team IDs to team1/team2
        self.team_mapping = self._get_team_mapping()
        
        # Cache for parse_substitutions (expensive operation)
        self._substitutions_cache = None

    def _get_team_mapping(self) -> Dict[str, str]:
        """Get mapping of team IDs to team1/team2."""
        if self.is_fbcyl:
            # FBCYL: Use teamIdIntern (matches moves[].idTeam for play-by-play)
            # Note: teamIdIntern changes per game, teamIdExtern is consistent
            stats = self.game_data.get('stats', {})
            teams = stats.get('teams', [])
            if len(teams) >= 2:
                team1_id = teams[0].get('teamIdIntern') or teams[0].get('teamIdExtern')
                team2_id = teams[1].get('teamIdIntern') or teams[1].get('teamIdExtern')
                return {
                    team1_id: 'team1',
                    team2_id: 'team2'
                }
        else:
            # FEB: teams are in HEADER.TEAM[]
            teams = self.game_data.get('HEADER', {}).get('TEAM', [])
            if len(teams) >= 2:
                return {
                    teams[0].get('id'): 'team1',
                    teams[1].get('id'): 'team2'
                }
        return {}

    def _time_to_seconds(self, quarter: str, time_str: str) -> int:
        """
        Convert quarter and time to absolute seconds from game start.

        Args:
            quarter: Quarter number (1-4)
            time_str: Time in format "mm:ss" (remaining in quarter)

        Returns:
            Absolute seconds from game start
        """
        try:
            quarter_num = int(quarter)
            parts = time_str.split(':')
            if len(parts) == 2:
                minutes, seconds = int(parts[0]), int(parts[1])
                # Each quarter is 10 minutes (600 seconds)
                # Time is remaining in quarter, so we need to invert it
                elapsed_in_quarter = 600 - (minutes * 60 + seconds)
                total_seconds = (quarter_num - 1) * 600 + elapsed_in_quarter
                return total_seconds
        except (ValueError, AttributeError):
            pass
        return 0

    def _get_team_key(self, id_team: Optional[str]) -> Optional[str]:
        """Get team key (team1/team2) from team ID."""
        if not id_team:
            return None
        return self.team_mapping.get(id_team)

    def _fbcyl_time_to_seconds(self, period: int, min: int, sec: int) -> int:
        """
        Convert FBCYL time to absolute seconds from game start.

        Args:
            period: Period number (1-4)
            min: Minutes elapsed in period
            sec: Seconds elapsed in minute

        Returns:
            Absolute seconds from game start
        """
        try:
            # Each period is 10 minutes (600 seconds)
            # Time is elapsed in period
            elapsed_in_period = min * 60 + sec
            total_seconds = (period - 1) * 600 + elapsed_in_period
            return total_seconds
        except (ValueError, TypeError):
            pass
        return 0

    def parse_substitutions(self) -> Dict[str, List[Tuple[int, bool]]]:
        """
        Parse all substitutions to create timeline of when each player is on court.

        Returns:
            Dict mapping player ID (idPlayer/actorId) to list of (timestamp, is_on_court) tuples
        """
        # Return cached result if available
        if self._substitutions_cache is not None:
            return self._substitutions_cache
        
        player_timeline = defaultdict(list)

        if self.is_fbcyl:
            # FBCYL: Use inOutsList from players
            stats = self.game_data.get('stats', {})
            teams = stats.get('teams', [])

            for team in teams:
                players = team.get('players', [])
                for player in players:
                    actor_id = player.get('actorId')
                    if not actor_id:
                        continue

                    # Use licenseId (persistent) instead of actorId (game-scoped)
                    # so that lineup keys remain stable across games.
                    player_id = self._fbcyl_actor_to_license.get(actor_id) or str(actor_id)

                    in_outs_list = player.get('inOutsList', [])
                    
                    # First pass: collect all events
                    for event in in_outs_list:
                        event_type = event.get('type')
                        minute_absolut = event.get('minuteAbsolut', 0)
                        # Convert minutes to seconds
                        timestamp = minute_absolut * 60

                        if event_type == 'IN_TYPE':
                            player_timeline[player_id].append((timestamp, True))
                        elif event_type == 'OUT_TYPE':
                            player_timeline[player_id].append((timestamp, False))
                    
                    # Second pass: detect starters (first event is OUT without prior IN)
                    if player_timeline[player_id] and player_timeline[player_id][0][1] == False:
                        # Player's first event is OUT, so they started the game
                        player_timeline[player_id].insert(0, (0, True))
        else:
            # FEB: Parse PLAYBYPLAY.LINES for substitutions
            # Lines are in reverse chronological order, so process them forward
            # to go from start to end of game
            for line in reversed(self.lines):
                # Check the text field for substitution indicators (case-insensitive)
                text = line.get('text', '')
                upper_text = text.upper() if isinstance(text, str) else ''
                quarter = line.get('quarter', '1')
                time_str = line.get('time', '10:00')
                timestamp = self._time_to_seconds(quarter, time_str)
                id_team = line.get('idTeam')
                team_key = self._get_team_key(id_team)

                # Check if it's a substitution based on text field
                # Handle various casing/formatting of substitution messages
                if 'ENTRA A PISTA' in upper_text or ('ENTRA' in upper_text and 'PISTA' in upper_text):
                    # Player entering court
                    id_player = line.get('idPlayer')
                    if id_player:
                        player_timeline[id_player].append((timestamp, True))
                        if team_key:
                            self.court_state[team_key].add(id_player)

                elif 'SALE DE PISTA' in upper_text or ('SALE' in upper_text and 'PISTA' in upper_text):
                    # Player leaving court
                    id_player = line.get('idPlayer')
                    if id_player:
                        player_timeline[id_player].append((timestamp, False))
                        if team_key:
                            self.court_state[team_key].discard(id_player)

            # FEB: Detect starting lineup (players who exit without prior entry)
            # These are players with OUT events but no IN events before them
            for player_id, events in list(player_timeline.items()):
                if events and events[0][1] == False:  # First event is OUT (False)
                    # This player was on court at start
                    player_timeline[player_id].insert(0, (0, True))

        # Sort timelines by timestamp
        for player_id in player_timeline:
            player_timeline[player_id].sort(key=lambda x: x[0])

        # Cache the result for future calls
        self._substitutions_cache = dict(player_timeline)
        return self._substitutions_cache

    def get_player_court_segments(self, player_id) -> List[Tuple[int, int]]:
        """
        Get time segments when a specific player was on court.

        Args:
            player_id: Player's ID (idPlayer from JSON) - can be str or int

        Returns:
            List of (start_time, end_time) tuples in seconds from game start
        """
        timeline = self.parse_substitutions()

        # Try to find player with both str and int formats
        player_events = timeline.get(player_id, [])
        if not player_events:
            # Try converting to int if it's a string
            try:
                player_events = timeline.get(int(player_id), [])
            except (ValueError, TypeError):
                pass
        if not player_events:
            # Try converting to str if it's an int
            try:
                player_events = timeline.get(str(player_id), [])
            except (ValueError, TypeError):
                pass

        segments = []
        current_start = None

        for timestamp, is_on_court in player_events:
            if is_on_court and current_start is None:
                current_start = timestamp
            elif not is_on_court and current_start is not None:
                segments.append((current_start, timestamp))
                current_start = None

        # If player was still on court at game end
        if current_start is not None:
            # Game ends at 40 minutes (2400 seconds) for regular time
            segments.append((current_start, 2400))

        return segments

    def was_player_on_court(self, player_id: str, quarter: str, time_str: str) -> bool:
        """
        Check if a player was on court at a specific moment.

        Args:
            player_id: Player's ID (idPlayer from JSON)
            quarter: Quarter number
            time_str: Time in format "mm:ss"

        Returns:
            True if player was on court, False otherwise
        """
        timestamp = self._time_to_seconds(quarter, time_str)
        segments = self.get_player_court_segments(player_id)

        for start, end in segments:
            if start <= timestamp <= end:
                return True
        return False

    def get_actions_when_on_court(self, player_id: str) -> List[Dict]:
        """
        Get all actions that occurred while a specific player was on court.

        Args:
            player_id: Player's ID (idPlayer for FEB, actorId for FBCYL)

        Returns:
            List of action dictionaries (all teams)
        """
        segments = self.get_player_court_segments(player_id)
        actions_on_court = []

        if self.is_fbcyl:
            # FBCYL: moves are already in chronological order
            for move in self.lines:
                period = move.get('period')
                min_val = move.get('min')
                sec_val = move.get('sec')

                if period is None or min_val is None or sec_val is None:
                    continue

                timestamp = self._fbcyl_time_to_seconds(period, min_val, sec_val)

                # Check if this action occurred while player was on court
                for start, end in segments:
                    if start <= timestamp <= end:
                        actions_on_court.append(move)
                        break
        else:
            # FEB: PLAYBYPLAY.LINES is reverse-chronological, so iterate reversed
            for line in reversed(self.lines):
                quarter = line.get('quarter')
                time_str = line.get('time')

                if not quarter or not time_str:
                    continue

                timestamp = self._time_to_seconds(quarter, time_str)

                # Check if this action occurred while player was on court
                for start, end in segments:
                    if start <= timestamp <= end:
                        actions_on_court.append(line)
                        break

        return actions_on_court

    def get_actions_when_off_court(self, player_id: str, id_team: str) -> List[Dict]:
        """
        Get all actions that occurred while a specific player was off court.

        Args:
            player_id: Player's ID (idPlayer for FEB, actorId for FBCYL)
            id_team: Team ID (not used for filtering, kept for compatibility)

        Returns:
            List of action dictionaries (all teams)
        """
        segments = self.get_player_court_segments(player_id)
        actions_off_court = []

        if self.is_fbcyl:
            # FBCYL: moves are already in chronological order
            for move in self.lines:
                period = move.get('period')
                min_val = move.get('min')
                sec_val = move.get('sec')

                if period is None or min_val is None or sec_val is None:
                    continue

                timestamp = self._fbcyl_time_to_seconds(period, min_val, sec_val)

                # Check if this action occurred while player was off court
                is_on_court = False
                for start, end in segments:
                    if start <= timestamp <= end:
                        is_on_court = True
                        break

                if not is_on_court:
                    actions_off_court.append(move)
        else:
            # FEB: Ensure chronological order for consistent analysis
            for line in reversed(self.lines):
                quarter = line.get('quarter')
                time_str = line.get('time')

                if not quarter or not time_str:
                    continue

                timestamp = self._time_to_seconds(quarter, time_str)

                # Check if this action occurred while player was off court
                is_on_court = False
                for start, end in segments:
                    if start <= timestamp <= end:
                        is_on_court = True
                        break

                if not is_on_court:
                    actions_off_court.append(line)

        return actions_off_court

    def calculate_time_played(self, player_id: str) -> int:
        """
        Calculate total time played by a player in seconds.

        Args:
            player_id: Player's ID (idPlayer from JSON)

        Returns:
            Total seconds played
        """
        segments = self.get_player_court_segments(player_id)
        total_seconds = sum(end - start for start, end in segments)
        return total_seconds


