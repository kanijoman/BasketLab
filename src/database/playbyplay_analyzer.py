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
                    player_id = player.get('actorId')
                    if not player_id:
                        continue

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


class InOutStatsCalculator:
    """Calculate team statistics when a player is on/off the court."""

    def __init__(self, analyzer: PlayByPlayAnalyzer):
        """
        Initialize the IN/OUT stats calculator.

        Args:
            analyzer: PlayByPlayAnalyzer instance
        """
        self.analyzer = analyzer

    def _extract_points_from_action(self, action: Dict) -> Tuple[int, str]:
        """
        Extract points scored from an action.

        Args:
            action: Action dictionary

        Returns:
            Tuple of (points, team_id)
        """
        team_id = action.get('idTeam')

        # Check if this is FBCYL format (uses 'move' field)
        if 'move' in action:
            move = action.get('move', '')
            # FBCYL uses Spanish text like "Canasta de 2", "Canasta de 3", etc.
            if 'Canasta de 2' in move or 'canasta de 2' in move:
                return 2, team_id
            elif 'Canasta de 3' in move or 'canasta de 3' in move:
                return 3, team_id
            elif 'Canasta de 1' in move or 'canasta de 1' in move or 'Tiro libre anotado' in move:
                return 1, team_id
            return 0, None

        # FEB format processing
        text = action.get('text', '').upper()  # Convert to uppercase

        # Check for successful shots in text
        if 'TIRO DE 2' in text or 'CANASTA DE 2' in text:
            if 'FALLADO' not in text and 'FALLA' not in text:
                return 2, team_id
        elif 'TIRO DE 3' in text or 'CANASTA DE 3' in text or 'TRIPLE' in text:
            if 'FALLADO' not in text and 'FALLA' not in text:
                return 3, team_id
        elif ('TIRO DE 1' in text or 'TIRO LIBRE' in text) and 'ANOTADO' in text:
            return 1, team_id

        # Fallback to old logic using action type and logParams
        action_type = action.get('action', '')

        if action_type == 'shoot':
            # logParam4: 1 = made, 0 = missed
            # logParam6: point value (2 or 3)
            made = action.get('logParam4') == '1'
            point_value = int(action.get('logParam6', 0)) if action.get('logParam6') else 0
            if made and point_value > 0:
                return point_value, team_id

        elif action_type == 'fthrow':
            # logParam4: 1 = made, 0 = missed
            made = action.get('logParam4') == '1'
            if made:
                return 1, team_id

        return 0, None

    def _process_fbcyl_move(self, line: Dict, move_text: str, action_team: str,
                           id_team: str, target: Dict, idx: int, lines: List[Dict]) -> None:
        """
        Process a FBCYL move and update statistics.

        Note: FBCYL does NOT include rebounds in play-by-play data (moves list).
        Rebounds are only in pre-calculated stats, so we cannot determine when they
        occurred relative to player substitutions. Therefore, ORB/DRB remain 0 for FBCYL.
        """
        # Points
        points, scoring_team = self._extract_points_from_action(line)
        if points > 0 and scoring_team:
            scoring_team = str(scoring_team)
            if scoring_team == id_team:
                target['points_for'] += points
            elif scoring_team != id_team:
                target['points_against'] += points

        # Determine whether we write to team or opponent keys
        is_team_action = (action_team == id_team)

        # Shooting stats - based on move text
        if 'Canasta de 2' in move_text or 'canasta de 2' in move_text:
            if is_team_action:
                target['fga_2'] += 1
                target['fgm_2'] += 1
            else:
                target['opp_fga_2'] += 1
                target['opp_fgm_2'] += 1
        elif 'Intento fallado de 2' in move_text or 'intento fallado de 2' in move_text:
            if is_team_action:
                target['fga_2'] += 1
            else:
                target['opp_fga_2'] += 1
        elif 'Canasta de 3' in move_text or 'canasta de 3' in move_text:
            if is_team_action:
                target['fga_3'] += 1
                target['fgm_3'] += 1
            else:
                target['opp_fga_3'] += 1
                target['opp_fgm_3'] += 1
        elif 'Intento fallado de 3' in move_text or 'intento fallado de 3' in move_text:
            if is_team_action:
                target['fga_3'] += 1
            else:
                target['opp_fga_3'] += 1
        elif 'Canasta de 1' in move_text or 'canasta de 1' in move_text or 'Tiro libre anotado' in move_text:
            if is_team_action:
                target['fta'] += 1
                target['ftm'] += 1
            else:
                target['opp_fta'] += 1
                target['opp_ftm'] += 1
        elif 'Intento fallado de 1' in move_text or 'intento fallado de 1' in move_text:
            if is_team_action:
                target['fta'] += 1
            else:
                target['opp_fta'] += 1

        # Turnovers
        if 'Pérdida' in move_text or 'pérdida' in move_text:
            if is_team_action:
                target['tov'] += 1
            else:
                target['opp_tov'] += 1

        # Personal fouls
        if 'Personal' in move_text or 'personal' in move_text or 'Falta' in move_text:
            if is_team_action:
                target['pf'] += 1
            else:
                target['opp_pf'] += 1

    def _process_feb_action(self, line: Dict, upper_text: str, action_type: str,
                           action_team: str, id_team: str, target: Dict,
                           orig_idx: int, lines: List[Dict], last_shot_team: Optional[str]) -> Optional[str]:
        """Process a FEB action and update statistics. Returns updated last_shot_team."""
        # Track shots for rebound classification
        if action_type in ('shoot', 'fthrow'):
            is_miss = False
            if isinstance(line.get('logParam4'), str):
                is_miss = line.get('logParam4') == '0'
            if 'FALLADO' in upper_text or 'FALLA' in upper_text or is_miss:
                last_shot_team = action_team
            else:
                last_shot_team = None

        # Points
        points, scoring_team = self._extract_points_from_action(line)
        if points > 0 and scoring_team:
            scoring_team = str(scoring_team)
            if scoring_team == id_team:
                target['points_for'] += points
            elif scoring_team != id_team:
                target['points_against'] += points

        # Determine whether we write to team or opponent keys
        is_team_action = (action_team == id_team)

        # Shooting stats - use text first
        if 'TIRO DE 2' in upper_text or 'CANASTA DE 2' in upper_text:
            if is_team_action:
                target['fga_2'] += 1
                if 'FALLADO' not in upper_text and 'FALLA' not in upper_text:
                    target['fgm_2'] += 1
            else:
                target['opp_fga_2'] += 1
                if 'FALLADO' not in upper_text and 'FALLA' not in upper_text:
                    target['opp_fgm_2'] += 1
        elif 'TIRO DE 3' in upper_text or 'TRIPLE' in upper_text or 'CANASTA DE 3' in upper_text:
            if is_team_action:
                target['fga_3'] += 1
                if 'FALLADO' not in upper_text and 'FALLA' not in upper_text:
                    target['fgm_3'] += 1
            else:
                target['opp_fga_3'] += 1
                if 'FALLADO' not in upper_text and 'FALLA' not in upper_text:
                    target['opp_fgm_3'] += 1
        elif 'TIRO DE 1' in upper_text or 'TIRO LIBRE' in upper_text:
            if is_team_action:
                target['fta'] += 1
                if 'ANOTADO' in upper_text or 'ANOTA' in upper_text:
                    target['ftm'] += 1
            else:
                target['opp_fta'] += 1
                if 'ANOTADO' in upper_text or 'ANOTA' in upper_text:
                    target['opp_ftm'] += 1
        # fallback to action_type
        elif action_type == 'shoot':
            point_value = int(line.get('logParam6', 0)) if line.get('logParam6') else 0
            made = line.get('logParam4') == '1'
            if point_value == 2:
                if is_team_action:
                    target['fga_2'] += 1
                    if made:
                        target['fgm_2'] += 1
                else:
                    target['opp_fga_2'] += 1
                    if made:
                        target['opp_fgm_2'] += 1
            elif point_value == 3:
                if is_team_action:
                    target['fga_3'] += 1
                    if made:
                        target['fgm_3'] += 1
                else:
                    target['opp_fga_3'] += 1
                    if made:
                        target['opp_fgm_3'] += 1
        elif action_type == 'fthrow':
            if is_team_action:
                target['fta'] += 1
                if line.get('logParam4') == '1':
                    target['ftm'] += 1
            else:
                target['opp_fta'] += 1
                if line.get('logParam4') == '1':
                    target['opp_ftm'] += 1

        # Rebounds
        if action_type == 'rebound':
            prev_idx = orig_idx + 1
            shot_team = None
            if prev_idx < len(lines):
                prev = lines[prev_idx]
                p_action = (prev.get('action') or '').lower()
                p_text = (prev.get('text') or '').upper()
                if p_action in ('shoot', 'fthrow') or ('TIRO' in p_text or 'CANASTA' in p_text or 'TRIPLE' in p_text or 'FALLADO' in p_text):
                    shot_team = prev.get('idTeam')

            if shot_team is not None and shot_team == action_team:
                # offensive rebound
                if is_team_action:
                    target['orb'] += 1
                else:
                    target['opp_orb'] += 1
            else:
                # defensive rebound (default if no previous shot found)
                if is_team_action:
                    target['drb'] += 1
                else:
                    target['opp_drb'] += 1
            last_shot_team = None

        # Assists
        if 'ASISTENCIA' in upper_text or action_type == 'assist':
            if is_team_action:
                target['ast'] += 1
            else:
                target['opp_ast'] += 1

        # Steals
        if 'ROBO' in upper_text or 'RECUPERA' in upper_text or action_type == 'steal' or action_type == 'recovery':
            if is_team_action:
                target['stl'] += 1
            else:
                target['opp_stl'] += 1

        # Blocks
        if 'TAPÓN' in upper_text or 'TAPON' in upper_text or action_type == 'block':
            if is_team_action:
                target['blk'] += 1
            else:
                target['opp_blk'] += 1

        # Turnovers
        if 'PÉRDIDA' in upper_text or 'PERDIDA' in upper_text or action_type == 'turnover' or action_type == 'lose':
            if is_team_action:
                target['tov'] += 1
            else:
                target['opp_tov'] += 1

        # Personal fouls
        if 'FALTA' in upper_text or action_type == 'foul':
            if is_team_action:
                target['pf'] += 1
            else:
                target['opp_pf'] += 1

        return last_shot_team

    def calculate_in_out_stats(self, player_id: str, id_team: str) -> Dict[str, Dict]:
        """
        Calculate statistics for when player is IN vs OUT.

        Args:
            player_id: Player's ID (idPlayer from JSON)
            id_team: Player's team ID

        Returns:
            Dictionary with 'in' and 'out' keys containing stats
        """
        # We'll iterate the full play-by-play in chronological order and
        # apply identical processing to every action, assigning results to
        # the IN or OUT dictionary depending on whether the player was on court
        # at that timestamp. This ensures rebound and possession classification
        # uses complete game context and the same logic for both cases.

        # Initialize stat buckets for IN and OUT (team + opponent prefixed)
        def _empty_stats():
            return {
                'points_for': 0,
                'points_against': 0,
                'fgm_2': 0,
                'fga_2': 0,
                'fgm_3': 0,
                'fga_3': 0,
                'ftm': 0,
                'fta': 0,
                'orb': 0,
                'drb': 0,
                'ast': 0,
                'stl': 0,
                'blk': 0,
                'tov': 0,
                'pf': 0,
                # opponent prefixed
                'opp_fgm_2': 0,
                'opp_fga_2': 0,
                'opp_fgm_3': 0,
                'opp_fga_3': 0,
                'opp_ftm': 0,
                'opp_fta': 0,
                'opp_orb': 0,
                'opp_drb': 0,
                'opp_ast': 0,
                'opp_stl': 0,
                'opp_blk': 0,
                'opp_tov': 0,
                'opp_pf': 0,
            }

        stats_in = _empty_stats()
        stats_out = _empty_stats()

        # Shared variables
        last_shot_team = None
        # Keep a short history of processed actions to allow back-scan when needed
        prev_actions: List[Dict] = []

        # Precompute player segments for speed (delegated to analyzer)
        segments = self.analyzer.get_player_court_segments(player_id)

        # Helper to decide if timestamp is within any segment
        def _is_on_court(ts: int) -> bool:
            for s, e in segments:
                if s <= ts <= e:
                    return True
            return False

        # Iterate chronological
        # For FEB: PLAYBYPLAY.LINES stored reverse-chronological, iterate reversed
        # For FBCYL: moves are already chronological
        lines = self.analyzer.lines or []
        is_fbcyl = self.analyzer.is_fbcyl

        if is_fbcyl:
            # FBCYL: iterate forwards (already chronological)
            for idx, line in enumerate(lines):
                period = line.get('period')
                min_val = line.get('min')
                sec_val = line.get('sec')

                if period is None or min_val is None or sec_val is None:
                    prev_actions.append(line)
                    if len(prev_actions) > 40:
                        prev_actions.pop(0)
                    continue

                timestamp = self.analyzer._fbcyl_time_to_seconds(period, min_val, sec_val)
                action_team = str(line.get('idTeam', ''))
                move_text = line.get('move', '')

                # Determine which bucket this action affects
                on_court = _is_on_court(timestamp)
                target = stats_in if on_court else stats_out

                # Process FBCYL move
                self._process_fbcyl_move(line, move_text, action_team, str(id_team), target, idx, lines)

                # Append to history
                prev_actions.append(line)
                if len(prev_actions) > 80:
                    prev_actions.pop(0)
        else:
            # FEB: iterate reverse-chronologically
            for orig_idx in range(len(lines) - 1, -1, -1):
                line = lines[orig_idx]
                quarter = line.get('quarter')
                time_str = line.get('time')
                if not quarter or not time_str:
                    # keep history but skip lines without timing
                    prev_actions.append(line)
                    if len(prev_actions) > 40:
                        prev_actions.pop(0)
                    continue
                timestamp = self.analyzer._time_to_seconds(quarter, time_str)
                action_team = str(line.get('idTeam', ''))
                text = line.get('text', '')
                upper_text = text.upper() if isinstance(text, str) else ''
                action_type = line.get('action', '')

                # Determine which bucket this action affects
                on_court = _is_on_court(timestamp)
                target = stats_in if on_court else stats_out

                # Process FEB action
                last_shot_team = self._process_feb_action(line, upper_text, action_type, action_team, str(id_team), target, orig_idx, lines, last_shot_team)

                # Append to history
                prev_actions.append(line)
                if len(prev_actions) > 80:
                    prev_actions.pop(0)

        # Add minutes info
        time_in = self.analyzer.calculate_time_played(player_id)
        total_game_time = 2400
        time_out = total_game_time - time_in
        stats_in['minutes'] = time_in / 60
        stats_out['minutes'] = time_out / 60

        return {'in': stats_in, 'out': stats_out}

    def _calculate_stats_from_actions(self, actions: List[Dict],
                                      team_id: str, opponent_team: str) -> Dict:
        """
        Calculate statistics from a list of actions.

        Args:
            actions: List of action dictionaries
            team_id: Team ID to calculate stats for
            opponent_team: Opponent team ID

        Returns:
            Dictionary with calculated statistics
        """
        stats = {
            'points_for': 0,
            'points_against': 0,
            'fgm_2': 0,  # Field goals made 2pt
            'fga_2': 0,  # Field goals attempted 2pt
            'fgm_3': 0,  # Field goals made 3pt
            'fga_3': 0,  # Field goals attempted 3pt
            'ftm': 0,    # Free throws made
            'fta': 0,    # Free throws attempted
            'orb': 0,    # Offensive rebounds
            'drb': 0,    # Defensive rebounds
            'ast': 0,    # Assists
            'stl': 0,    # Steals
            'blk': 0,    # Blocks
            'tov': 0,    # Turnovers
            'pf': 0,     # Personal fouls
        }
        # Track opponent stats as well (prefix opp_)
        opp_stats = {
            'opp_fgm_2': 0,
            'opp_fga_2': 0,
            'opp_fgm_3': 0,
            'opp_fga_3': 0,
            'opp_ftm': 0,
            'opp_fta': 0,
            'opp_orb': 0,
            'opp_drb': 0,
            'opp_ast': 0,
            'opp_stl': 0,
            'opp_blk': 0,
            'opp_tov': 0,
            'opp_pf': 0,
        }

        last_shot_team = None  # Track who took the last shot for rebound classification

        for idx, action in enumerate(actions):
            action_type = action.get('action', '')
            action_team = action.get('idTeam')
            text = action.get('text', '').upper()  # Convert to uppercase for matching

            # Track ALL shots (both teams) for rebound classification
            if action_type in ('shoot', 'fthrow'):
                # Consider explicit miss indicators in text or logParam4
                is_miss = False
                if isinstance(action.get('logParam4'), str):
                    is_miss = action.get('logParam4') == '0'
                if 'FALLADO' in text or 'FALLA' in text or is_miss:
                    last_shot_team = action_team
                else:
                    # Made shot, reset
                    last_shot_team = None

            # Points scored
            points, scoring_team = self._extract_points_from_action(action)
            if points > 0 and scoring_team:
                if scoring_team == team_id:
                    stats['points_for'] += points
                elif scoring_team == opponent_team:
                    stats['points_against'] += points

            # Determine target dict (team or opponent)
            target = stats if action_team == team_id else opp_stats

            # Shooting stats - analyze text field for both teams
            if 'TIRO DE 2' in text or 'CANASTA DE 2' in text:
                target['fga_2' if target is stats else 'opp_fga_2'] = target.get('fga_2' if target is stats else 'opp_fga_2', 0) + 1
                if 'FALLADO' not in text and 'FALLA' not in text:
                    target['fgm_2' if target is stats else 'opp_fgm_2'] = target.get('fgm_2' if target is stats else 'opp_fgm_2', 0) + 1
            elif 'TIRO DE 3' in text or 'TRIPLE' in text or 'CANASTA DE 3' in text:
                target['fga_3' if target is stats else 'opp_fga_3'] = target.get('fga_3' if target is stats else 'opp_fga_3', 0) + 1
                if 'FALLADO' not in text and 'FALLA' not in text:
                    target['fgm_3' if target is stats else 'opp_fgm_3'] = target.get('fgm_3' if target is stats else 'opp_fgm_3', 0) + 1
            elif 'TIRO DE 1' in text or 'TIRO LIBRE' in text:
                target['fta' if target is stats else 'opp_fta'] = target.get('fta' if target is stats else 'opp_fta', 0) + 1
                if 'ANOTADO' in text or 'ANOTA' in text:
                    target['ftm' if target is stats else 'opp_ftm'] = target.get('ftm' if target is stats else 'opp_ftm', 0) + 1

            # Fallback to action_type for shooting
            elif action_type == 'shoot':
                point_value = int(action.get('logParam6', 0)) if action.get('logParam6') else 0
                made = action.get('logParam4') == '1'
                if point_value == 2:
                    target['fga_2' if target is stats else 'opp_fga_2'] = target.get('fga_2' if target is stats else 'opp_fga_2', 0) + 1
                    if made:
                        target['fgm_2' if target is stats else 'opp_fgm_2'] = target.get('fgm_2' if target is stats else 'opp_fgm_2', 0) + 1
                elif point_value == 3:
                    target['fga_3' if target is stats else 'opp_fga_3'] = target.get('fga_3' if target is stats else 'opp_fga_3', 0) + 1
                    if made:
                        target['fgm_3' if target is stats else 'opp_fgm_3'] = target.get('fgm_3' if target is stats else 'opp_fgm_3', 0) + 1

            # Free throws fallback
            elif action_type == 'fthrow':
                target['fta' if target is stats else 'opp_fta'] = target.get('fta' if target is stats else 'opp_fta', 0) + 1
                if action.get('logParam4') == '1':
                    target['ftm' if target is stats else 'opp_ftm'] = target.get('ftm' if target is stats else 'opp_ftm', 0) + 1

            # Rebounds - only when action == 'rebound'. Determine previous shot by
            # inspecting the next element in the original ordering (which corresponds
            # to the previous event in time when actions were provided in descending order).
            if action_type == 'rebound':
                shot_team = None
                if idx + 1 < len(actions):
                    prev = actions[idx + 1]
                    p_action = (prev.get('action') or '').lower()
                    p_text = (prev.get('text') or '').upper()
                    if p_action in ('shoot', 'fthrow') or ('TIRO' in p_text or 'CANASTA' in p_text or 'TRIPLE' in p_text or 'FALLADO' in p_text):
                        shot_team = prev.get('idTeam')

                if shot_team is not None and shot_team == action_team:
                    # Offensive rebound for action_team
                    if action_team == team_id:
                        stats['orb'] += 1
                    else:
                        opp_stats['opp_orb'] += 1
                else:
                    # Defensive rebound for action_team (default)
                    if action_team == team_id:
                        stats['drb'] += 1
                    else:
                        opp_stats['opp_drb'] += 1
                # do not attempt extended back-scan; follow strict previous-element rule
                last_shot_team = None

            # Assists
            if 'ASISTENCIA' in text or action_type == 'assist':
                if action_team == team_id:
                    stats['ast'] += 1
                else:
                    opp_stats['opp_ast'] += 1

            # Steals
            if 'ROBO' in text or 'RECUPERA' in text or action_type == 'steal' or action_type == 'recovery':
                if action_team == team_id:
                    stats['stl'] += 1
                else:
                    opp_stats['opp_stl'] += 1

            # Blocks
            if 'TAPÓN' in text or 'TAPON' in text or action_type == 'block':
                if action_team == team_id:
                    stats['blk'] += 1
                else:
                    opp_stats['opp_blk'] += 1

            # Turnovers
            if 'PÉRDIDA' in text or 'PERDIDA' in text or action_type == 'turnover' or action_type == 'lose':
                if action_team == team_id:
                    stats['tov'] += 1
                else:
                    opp_stats['opp_tov'] += 1

            # Personal fouls
            if 'FALTA' in text or action_type == 'foul':
                if action_team == team_id:
                    stats['pf'] += 1
                else:
                    opp_stats['opp_pf'] += 1

        # Merge opponent stats into returned dict so caller can aggregate them
        stats.update(opp_stats)
        return stats


class PossessionAnalyzer:
    """Analyzes play-by-play data to calculate possession durations and efficiency by time ranges."""

    def __init__(self, game_data: Dict, is_fbcyl: bool = False):
        """
        Initialize the possession analyzer.

        Args:
            game_data: The complete game JSON data including PLAYBYPLAY (FEB) or moves (FBCYL)
            is_fbcyl: Whether this is FBCYL data format
        """
        self.game_data = game_data
        self.is_fbcyl = is_fbcyl

        if is_fbcyl:
            self.moves = game_data.get('moves', [])
        else:
            self.playbyplay = game_data.get('PLAYBYPLAY', {})
            self.moves = self.playbyplay.get('LINES', [])

        self.team_mapping = self._get_team_mapping()

    def _get_team_mapping(self) -> Dict[str, str]:
        """Get mapping of team IDs to team1/team2."""
        if self.is_fbcyl:
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
            teams = self.game_data.get('HEADER', {}).get('TEAM', [])
            if len(teams) >= 2:
                return {
                    teams[0].get('id'): 'team1',
                    teams[1].get('id'): 'team2'
                }
        return {}

    def _get_timestamp(self, move: Dict) -> int:
        """
        Get timestamp in seconds for a move.

        Args:
            move: Move dictionary (FBCYL or FEB format)

        Returns:
            Timestamp in seconds from game start
        """
        if self.is_fbcyl:
            period = move.get('period', 1)
            min_val = move.get('min', 0)
            sec_val = move.get('sec', 0)
            return (period - 1) * 600 + min_val * 60 + sec_val
        else:
            quarter = move.get('quarter', '1')
            time_str = move.get('time', '10:00')
            try:
                quarter_num = int(quarter)
                parts = time_str.split(':')
                if len(parts) == 2:
                    minutes, seconds = int(parts[0]), int(parts[1])
                    elapsed_in_quarter = 600 - (minutes * 60 + seconds)
                    return (quarter_num - 1) * 600 + elapsed_in_quarter
            except (ValueError, AttributeError):
                pass
        return 0

    def _is_possession_ending_event(self, move: Dict) -> bool:
        """
        Check if a move ends a possession.

        A possession ends when:
        - A field goal is made (2pt or 3pt)
        - A turnover occurs
        - The last free throw is made (ends possession)
        - An opponent gets a defensive rebound

        Args:
            move: Move dictionary

        Returns:
            True if this move ends a possession
        """
        if self.is_fbcyl:
            move_text = move.get('move', '')
            # Made field goals end possession
            if 'Canasta de 2' in move_text or 'Canasta de 3' in move_text:
                return True
            # Turnovers end possession
            if 'Pérdida' in move_text or 'pérdida' in move_text:
                return True
            # Last made free throw ends possession (we'll handle this in sequence)
            # For now, mark free throws as potential endings
            if 'Canasta de 1' in move_text or 'Tiro libre anotado' in move_text:
                return True
        else:
            text = move.get('text', '').upper()
            action_type = move.get('action', '').lower()
            
            # Made field goals
            if ('TIRO DE 2' in text or 'CANASTA DE 2' in text or 'TIRO DE 3' in text or 
                'CANASTA DE 3' in text or 'TRIPLE' in text):
                if 'FALLADO' not in text and 'FALLA' not in text:
                    return True
            
            # Turnovers
            if 'PÉRDIDA' in text or 'PERDIDA' in text or action_type == 'turnover' or action_type == 'lose':
                return True
            
            # Made free throws (last one ends possession)
            if 'TIRO LIBRE' in text and 'ANOTADO' in text:
                return True

        return False

    def _get_points_from_move(self, move: Dict) -> int:
        """
        Extract points scored from a move.

        Args:
            move: Move dictionary

        Returns:
            Points scored (0, 1, 2, or 3)
        """
        if self.is_fbcyl:
            move_text = move.get('move', '')
            if 'Canasta de 2' in move_text:
                return 2
            elif 'Canasta de 3' in move_text:
                return 3
            elif 'Canasta de 1' in move_text or 'Tiro libre anotado' in move_text:
                return 1
        else:
            text = move.get('text', '').upper()
            if 'TIRO DE 2' in text or 'CANASTA DE 2' in text:
                if 'FALLADO' not in text and 'FALLA' not in text:
                    return 2
            elif 'TIRO DE 3' in text or 'CANASTA DE 3' in text or 'TRIPLE' in text:
                if 'FALLADO' not in text and 'FALLA' not in text:
                    return 3
            elif 'TIRO LIBRE' in text and 'ANOTADO' in text:
                return 1
        return 0

    def calculate_possessions(self, team_id: str) -> Dict[str, Any]:
        """
        Calculate possession statistics for a team based on play-by-play events.
        
        Tracks actual possession changes by detecting:
        - Made baskets (2pt, 3pt, free throws)
        - Turnovers
        - Missed shots (possession ends unless offensive rebound by SAME team in next 2 moves)
        - Defensive rebounds (confirm possession change)
        - Steals
        - Period starts/ends

        Args:
            team_id: Team ID to analyze

        Returns:
            Dictionary with possession statistics:
            - total_possessions: Total number of possessions
            - avg_duration: Average possession duration in seconds
            - possessions_by_duration: Dict with stats for <=8s, 8-16s, >16s
              Each contains: count, percentage, total_points, oer
        """
        team_id_str = str(team_id)
        
        # Get opponent team ID
        opponent_id = self._get_opponent_team(team_id_str, self.moves)
        
        # Sort moves chronologically
        moves_sorted = sorted(self.moves, key=lambda m: self._get_timestamp(m))
        
        possessions = []
        current_possession_team = None
        possession_start_time = 0
        possession_points = 0
        
        # Pre-process to identify offensive rebounds (to avoid ending possessions prematurely)
        offensive_rebound_indices = set()
        for i, move in enumerate(moves_sorted):
            move_text = move.get('move', '') if self.is_fbcyl else move.get('text', '')
            move_text_upper = move_text.upper()
            action_type = move.get('action', '').lower() if not self.is_fbcyl else ''
            
            # Check if this is a rebound
            if action_type == 'rebound' or 'REBOTE' in move_text_upper:
                curr_team = str(move.get('idTeam', ''))
                
                # Look back up to 2 moves to find a missed shot by same team
                # (more than 2 suggests it's not the same possession)
                for lookback in range(1, min(3, i + 1)):
                    prev_move = moves_sorted[i - lookback]
                    prev_team = str(prev_move.get('idTeam', ''))
                    prev_text = (prev_move.get('move', '') if self.is_fbcyl else prev_move.get('text', '')).upper()
                    prev_action = prev_move.get('action', '').lower() if not self.is_fbcyl else ''
                    
                    # Check if it's a missed field goal (not free throw)
                    is_missed_fg = False
                    if self.is_fbcyl:
                        if 'Intento fallado' in prev_text and 'de 1' not in prev_text.lower():
                            is_missed_fg = True
                    else:
                        if ('TIRO DE 2' in prev_text or 'TIRO DE 3' in prev_text) and 'FALLADO' in prev_text:
                            is_missed_fg = True
                    
                    if is_missed_fg:
                        if prev_team == curr_team:
                            # Same team rebounded their own miss = offensive rebound
                            offensive_rebound_indices.add(i - lookback)
                        break
                    
                    # Stop if we hit events that definitely end possessions
                    if (('CANASTA' in prev_text or 'ANOTADO' in prev_text) and 'FALLADO' not in prev_text) or 'PÉRDIDA' in prev_text or 'PERDIDA' in prev_text:
                        break
                    
                    # Stop if we hit another rebound or steal (suggests different possession)
                    if 'REBOTE' in prev_text or 'ROBO' in prev_text or prev_action == 'rebound' or prev_action == 'steal':
                        break
        
        possessions = []
        current_possession_team = None
        possession_start_time = 0
        possession_points = 0
        
        for i, move in enumerate(moves_sorted):
            move_team_id = str(move.get('idTeam', ''))
            timestamp = self._get_timestamp(move)
            move_text = move.get('move', '') if self.is_fbcyl else move.get('text', '')
            move_text_upper = move_text.upper()
            action_type = move.get('action', '').lower() if not self.is_fbcyl else ''
            
            # Skip period markers and other non-team events
            if action_type == 'period' or not move_team_id:
                # Handle period changes
                if action_type == 'period':
                    if current_possession_team == team_id_str and possession_start_time < timestamp:
                        duration = timestamp - possession_start_time
                        if 0 < duration <= 35:
                            possessions.append({
                                'duration': duration,
                                'points': possession_points,
                                'start_time': possession_start_time,
                                'end_time': timestamp
                            })
                    current_possession_team = None
                    possession_start_time = 0
                    possession_points = 0
                continue
            
            # Determine if this is a possession change event
            possession_change = False
            new_possession_team = None
            points_scored = 0
            
            # 1. Made field goals (possession ends, opponent gets ball)
            if self.is_fbcyl:
                if 'Canasta de 2' in move_text:
                    possession_change = True
                    points_scored = 2
                    new_possession_team = self._get_opponent_team(move_team_id, moves_sorted)
                elif 'Canasta de 3' in move_text:
                    possession_change = True
                    points_scored = 3
                    new_possession_team = self._get_opponent_team(move_team_id, moves_sorted)
                elif 'Canasta de 1' in move_text:
                    # Check if this is the last free throw in a sequence
                    if self._is_last_free_throw(i, moves_sorted):
                        possession_change = True
                        points_scored = 1
                        new_possession_team = self._get_opponent_team(move_team_id, moves_sorted)
                    else:
                        # Not last FT, possession continues
                        points_scored = 1
            else:
                # Made 2-pointers
                if ('TIRO DE 2' in move_text_upper and 'FALLADO' not in move_text_upper):
                    possession_change = True
                    points_scored = 2
                    new_possession_team = self._get_opponent_team(move_team_id, moves_sorted)
                # Made 3-pointers
                elif ('TIRO DE 3' in move_text_upper and 'FALLADO' not in move_text_upper):
                    possession_change = True
                    points_scored = 3
                    new_possession_team = self._get_opponent_team(move_team_id, moves_sorted)
                # Made free throws (only last one ends possession)
                elif ('TIRO LIBRE' in move_text_upper or 'TIRO DE 1' in move_text_upper):
                    if 'ANOTADO' in move_text_upper or ('FALLADO' not in move_text_upper and 'FALLA' not in move_text_upper):
                        if self._is_last_free_throw(i, moves_sorted):
                            possession_change = True
                            points_scored = 1
                            new_possession_team = self._get_opponent_team(move_team_id, moves_sorted)
                        else:
                            # Not last FT, accumulate points but don't end possession
                            points_scored = 1
            
            # 2. Turnovers (possession changes to opponent)
            if 'Pérdida' in move_text or 'PÉRDIDA' in move_text_upper or 'PERDIDA' in move_text_upper:
                possession_change = True
                new_possession_team = self._get_opponent_team(move_team_id, moves_sorted)
            
            # 3. Missed shots (possession ends UNLESS offensive rebound follows)
            is_missed_shot = False
            if self.is_fbcyl:
                if 'Intento fallado' in move_text or 'fallado' in move_text.lower():
                    # Exclude free throws
                    if 'de 1' not in move_text.lower():
                        is_missed_shot = True
            else:
                # Check for various forms of missed shots
                if ('FALLADO' in move_text_upper or 'FALLA' in move_text_upper or 
                    'INTENTO FALLADO' in move_text_upper):
                    # Make sure it's a FIELD GOAL (2pt or 3pt), NOT a free throw
                    if ('TIRO DE 2' in move_text_upper or 'TIRO DE 3' in move_text_upper):
                        is_missed_shot = True
            
            # Missed free throws on last attempt also end possession
            is_missed_last_ft = False
            if self._is_last_free_throw(i, moves_sorted):
                if self.is_fbcyl:
                    if 'Intento fallado de 1' in move_text or ('fallado' in move_text.lower() and 'de 1' in move_text):
                        is_missed_last_ft = True
                else:
                    if (('TIRO LIBRE' in move_text_upper or 'TIRO DE 1' in move_text_upper) and 
                        ('FALLADO' in move_text_upper or 'FALLA' in move_text_upper)):
                        is_missed_last_ft = True
            
            if is_missed_shot or is_missed_last_ft:
                # Check if this miss will be followed by offensive rebound
                if i not in offensive_rebound_indices:
                    # No offensive rebound = possession ends
                    possession_change = True
                    new_possession_team = self._get_opponent_team(move_team_id, moves_sorted)
            
            # 4. Defensive rebounds (confirm possession change)
            if action_type == 'rebound' or 'REBOTE' in move_text_upper:
                # Look back up to 2 moves to find a missed shot
                for lookback in range(1, min(3, i + 1)):
                    prev_move = moves_sorted[i - lookback]
                    prev_team = str(prev_move.get('idTeam', ''))
                    prev_text = (prev_move.get('move', '') if self.is_fbcyl else prev_move.get('text', '')).upper()
                    prev_action = prev_move.get('action', '').lower() if not self.is_fbcyl else ''
                    
                    # If we find a missed shot
                    if ('FALLADO' in prev_text or 'FALLA' in prev_text or 'INTENTO FALLADO' in prev_text):
                        if prev_team != move_team_id:
                            # Different team = defensive rebound, confirm possession change
                            possession_change = True
                            new_possession_team = move_team_id
                        break
                    
                    # Stop if we hit events that end possessions
                    if (('CANASTA' in prev_text or 'ANOTADO' in prev_text) and 'FALLADO' not in prev_text) or 'PÉRDIDA' in prev_text or 'PERDIDA' in prev_text:
                        break
                    
                    # Stop if we hit another rebound or steal
                    if 'REBOTE' in prev_text or 'ROBO' in prev_text or prev_action == 'rebound' or prev_action == 'steal':
                        break
            
            # 5. Steals (team gains possession)
            if 'Robo' in move_text or 'ROBO' in move_text_upper or 'Recupera' in move_text or action_type == 'steal':
                possession_change = True
                new_possession_team = move_team_id
            
            # 6. Period starts/ends
            if self.is_fbcyl:
                # Check for period change
                if i > 0 and move.get('period') != moves_sorted[i-1].get('period'):
                    # Period changed - close previous possession and start new one
                    if current_possession_team == team_id_str and possession_start_time < timestamp:
                        duration = timestamp - possession_start_time
                        if 0 < duration <= 35:  # Cap at 35 seconds (allows for shot clock resets)
                            possessions.append({
                                'duration': duration,
                                'points': possession_points,
                                'start_time': possession_start_time,
                                'end_time': timestamp
                            })
                    possession_change = True
                    new_possession_team = move_team_id
                elif i == 0:
                    # First move of the game
                    possession_change = True
                    new_possession_team = move_team_id
            else:
                # FEB format
                if action_type == 'period':
                    # Period end/start - close previous possession
                    if current_possession_team == team_id_str and possession_start_time < timestamp:
                        duration = timestamp - possession_start_time
                        if 0 < duration <= 35:  # Cap at 35 seconds (allows for shot clock resets)
                            possessions.append({
                                'duration': duration,
                                'points': possession_points,
                                'start_time': possession_start_time,
                                'end_time': timestamp
                            })
                    current_possession_team = None
                    possession_start_time = 0
                    possession_points = 0
                    continue
                elif i > 0 and move.get('quarter') != moves_sorted[i-1].get('quarter'):
                    # Quarter changed
                    if current_possession_team == team_id_str and possession_start_time < timestamp:
                        duration = timestamp - possession_start_time
                        if 0 < duration <= 35:  # Cap at 35 seconds (allows for shot clock resets)
                            possessions.append({
                                'duration': duration,
                                'points': possession_points,
                                'start_time': possession_start_time,
                                'end_time': timestamp
                            })
                    current_possession_team = None
                    possession_start_time = 0
                    possession_points = 0
            
            # Add points to current possession if same team
            if current_possession_team == move_team_id and points_scored > 0:
                possession_points += points_scored
            
            # Handle possession change
            if possession_change and new_possession_team:
                # Check for impossible sequence: same team ending possession twice
                # This indicates missing play-by-play data
                if current_possession_team == move_team_id:
                    # IMPOSSIBLE: Same team can't end possession twice without opponent having ball
                    # This happens when play-by-play is incomplete
                    # Solution: Insert a phantom opponent possession to maintain count accuracy
                    phantom_opponent = opponent_id if opponent_id else self._get_opponent_team(move_team_id, moves_sorted)
                    
                    # Save current team's possession first (if it was our team)
                    if current_possession_team == team_id_str and possession_start_time < timestamp:
                        duration = timestamp - possession_start_time
                        if 0 < duration <= 90:
                            possessions.append({
                                'duration': duration,
                                'points': possession_points,
                                'start_time': possession_start_time,
                                'end_time': timestamp
                            })
                    
                    # Now force possession to opponent (phantom possession we didn't see)
                    # The phantom possession had the ball but there's no record of what they did
                    current_possession_team = phantom_opponent
                    possession_start_time = timestamp
                    possession_points = 0
                    # Continue to process the current event normally below
                
                # Normal possession change processing
                if current_possession_team is None or current_possession_team != new_possession_team:
                    # Save previous possession if it was our team
                    if current_possession_team == team_id_str and possession_start_time < timestamp:
                        duration = timestamp - possession_start_time
                        if 0 < duration <= 90:  # Only count valid possessions (max 90 seconds allows shot clock violations + timeouts)
                            possessions.append({
                                'duration': duration,
                                'points': possession_points,
                                'start_time': possession_start_time,
                                'end_time': timestamp
                            })
                    
                    # Start new possession
                    current_possession_team = new_possession_team
                    possession_start_time = timestamp
                    possession_points = points_scored if new_possession_team == move_team_id else 0
        
        # Calculate statistics
        if not possessions:
            return {
                'total_possessions': 0,
                'avg_duration': 0.0,
                'possessions_by_duration': {
                    '<=8s': {'count': 0, 'percentage': 0.0, 'total_points': 0, 'oer': 0.0},
                    '8-16s': {'count': 0, 'percentage': 0.0, 'total_points': 0, 'oer': 0.0},
                    '>16s': {'count': 0, 'percentage': 0.0, 'total_points': 0, 'oer': 0.0}
                }
            }
        
        # Categorize possessions by duration
        short_poss = []   # <=8s
        medium_poss = []  # 8-16s
        long_poss = []    # >16s
        
        for poss in possessions:
            duration = poss['duration']
            if duration <= 8:
                short_poss.append(poss)
            elif duration <= 16:
                medium_poss.append(poss)
            else:
                long_poss.append(poss)
        
        # Calculate totals
        total_possessions = len(possessions)
        avg_duration = sum(p['duration'] for p in possessions) / total_possessions
        
        short_count = len(short_poss)
        short_points = sum(p['points'] for p in short_poss)
        short_pct = (short_count / total_possessions) * 100
        
        medium_count = len(medium_poss)
        medium_points = sum(p['points'] for p in medium_poss)
        medium_pct = (medium_count / total_possessions) * 100
        
        long_count = len(long_poss)
        long_points = sum(p['points'] for p in long_poss)
        long_pct = (long_count / total_possessions) * 100
        
        # Calculate OER (Offensive Efficiency Rating) = Points per 100 possessions
        def calculate_oer(poss_count: int, points: int) -> float:
            if poss_count == 0:
                return 0.0
            return (points / poss_count) * 100

        return {
            'total_possessions': total_possessions,
            'avg_duration': round(avg_duration, 2),
            'possessions_by_duration': {
                '<=8s': {
                    'count': short_count,
                    'percentage': round(short_pct, 1),
                    'total_points': short_points,
                    'oer': round(calculate_oer(short_count, short_points), 2)
                },
                '8-16s': {
                    'count': medium_count,
                    'percentage': round(medium_pct, 1),
                    'total_points': medium_points,
                    'oer': round(calculate_oer(medium_count, medium_points), 2)
                },
                '>16s': {
                    'count': long_count,
                    'percentage': round(long_pct, 1),
                    'total_points': long_points,
                    'oer': round(calculate_oer(long_count, long_points), 2)
                }
            }
        }
    
    def _get_opponent_team(self, team_id: str, moves: List[Dict]) -> str:
        """Get the opponent team ID."""
        team_ids = set(str(m.get('idTeam', '')) for m in moves if m.get('idTeam'))
        team_ids.discard(team_id)
        return team_ids.pop() if team_ids else team_id
    
    def _is_last_free_throw(self, current_index: int, moves: List[Dict]) -> bool:
        """Check if current free throw is the last in a sequence."""
        if current_index >= len(moves) - 1:
            return True
        
        next_move = moves[current_index + 1]
        next_text = next_move.get('move', '') if self.is_fbcyl else next_move.get('text', '')
        next_text_upper = next_text.upper()
        
        # If next move is also a free throw, current is not the last
        if 'Canasta de 1' in next_text or 'Intento fallado de 1' in next_text:
            return False
        if 'TIRO LIBRE' in next_text_upper or 'TIRO DE 1' in next_text_upper:
            return False
        
        return True

