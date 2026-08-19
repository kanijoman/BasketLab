"""Possession analyzer -- extracted from playbyplay_analyzer.py."""


from typing import Dict, List, Any

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
        opponent_id = self._get_opponent_team(team_id_str, self.moves)
        moves_sorted = sorted(self.moves, key=lambda m: self._get_timestamp(m))
        offensive_rebound_indices = self._detect_offensive_rebounds(moves_sorted)
        shooting_foul_indices = self._detect_shooting_foul_indices(moves_sorted)
        possessions = self._run_possession_state_machine(
            moves_sorted, team_id_str, opponent_id, offensive_rebound_indices, shooting_foul_indices
        )
        return self._aggregate_possession_stats(possessions)

    def _detect_offensive_rebounds(self, moves_sorted: List[Dict]) -> set:
        """Pre-process moves to identify offensive rebound indices.

        Marks the list indices (into moves_sorted) of missed field goals that
        are immediately followed by an offensive rebound by the same team.
        Used to avoid closing possessions prematurely on missed shots.

        Returns:
            Set of indices into moves_sorted that are missed FGs followed by OReb.
        """
        offensive_rebound_indices: set = set()
        for i, move in enumerate(moves_sorted):
            move_text = move.get('move', '') if self.is_fbcyl else move.get('text', '')
            move_text_upper = move_text.upper()
            action_type = move.get('action', '').lower() if not self.is_fbcyl else ''

            if action_type == 'rebound' or 'REBOTE' in move_text_upper:
                curr_team = str(move.get('idTeam', ''))
                for lookback in range(1, min(3, i + 1)):
                    prev_move = moves_sorted[i - lookback]
                    prev_team = str(prev_move.get('idTeam', ''))
                    prev_text = (prev_move.get('move', '') if self.is_fbcyl else prev_move.get('text', '')).upper()
                    prev_action = prev_move.get('action', '').lower() if not self.is_fbcyl else ''

                    is_missed_fg = False
                    if self.is_fbcyl:
                        if 'Intento fallado' in prev_text and 'de 1' not in prev_text.lower():
                            is_missed_fg = True
                    else:
                        if ('TIRO DE 2' in prev_text or 'TIRO DE 3' in prev_text) and 'FALLADO' in prev_text:
                            is_missed_fg = True

                    if is_missed_fg:
                        if prev_team == curr_team:
                            offensive_rebound_indices.add(i - lookback)
                        break

                    if (('CANASTA' in prev_text or 'ANOTADO' in prev_text) and 'FALLADO' not in prev_text) or 'PÉRDIDA' in prev_text or 'PERDIDA' in prev_text:
                        break

                    if 'REBOTE' in prev_text or 'ROBO' in prev_text or prev_action == 'rebound' or prev_action == 'steal':
                        break
        return offensive_rebound_indices

    def _detect_shooting_foul_indices(self, moves_sorted: List[Dict]) -> set:
        """Pre-process moves to identify missed FGs that were shooting fouls.

        A missed FG is a shooting foul when the same team has a FT event within
        the next 3 moves (before any rebound, turnover, or made basket by either
        team). These possessions must not be ended on the miss — the FTs belong
        to the same possession.

        Returns:
            Set of indices into moves_sorted that are shooting-foul misses.
        """
        shooting_foul_indices: set = set()
        for i, move in enumerate(moves_sorted):
            move_text = move.get('move', '') if self.is_fbcyl else move.get('text', '')
            move_text_upper = move_text.upper()
            team = str(move.get('idTeam', ''))

            is_missed_fg = False
            if self.is_fbcyl:
                if ('Intento fallado' in move_text or 'fallado' in move_text.lower()) and 'de 1' not in move_text.lower():
                    is_missed_fg = True
            else:
                if ('TIRO DE 2' in move_text_upper or 'TIRO DE 3' in move_text_upper) and 'FALLADO' in move_text_upper:
                    is_missed_fg = True

            if not is_missed_fg:
                continue

            for j in range(i + 1, min(i + 4, len(moves_sorted))):
                nxt = moves_sorted[j]
                nxt_text = nxt.get('move', '') if self.is_fbcyl else nxt.get('text', '')
                nxt_text_upper = nxt_text.upper()
                nxt_team = str(nxt.get('idTeam', ''))

                # Same team's FT → shooting foul confirmed
                if nxt_team == team:
                    if self.is_fbcyl and ('Canasta de 1' in nxt_text or 'Intento fallado de 1' in nxt_text):
                        shooting_foul_indices.add(i)
                        break
                    if not self.is_fbcyl and 'TIRO LIBRE' in nxt_text_upper:
                        shooting_foul_indices.add(i)
                        break

                # Possession-ending event → stop looking (it was a clean miss)
                if 'REBOTE' in nxt_text_upper or 'ROBO' in nxt_text_upper:
                    break
                if not self.is_fbcyl and nxt.get('action', '').lower() in ('rebound', 'steal'):
                    break
                if ('CANASTA' in nxt_text_upper or 'ANOTADO' in nxt_text_upper) and 'FALLADO' not in nxt_text_upper:
                    break
                if 'PÉRDIDA' in nxt_text_upper or 'PERDIDA' in nxt_text_upper:
                    break

        return shooting_foul_indices

    def _run_possession_state_machine(
        self,
        moves_sorted: List[Dict],
        team_id_str: str,
        opponent_id: str,
        offensive_rebound_indices: set,
        shooting_foul_indices: set,
    ) -> List[Dict]:
        """Execute the possession state machine over chronologically sorted moves.

        Tracks team-level possession changes event by event, recording each
        observed possession of *team_id_str* as a dict with duration and points.
        Only trackable possessions are counted — no phantom insertions.

        Returns:
            List of possession dicts, each with keys ``duration``, ``points``,
            ``start_time``, ``end_time``.
        """
        possessions: List[Dict] = []
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
                # Possession ends on miss unless an offensive rebound or shooting foul follows
                if i not in offensive_rebound_indices and i not in shooting_foul_indices:
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

        return possessions

    def _aggregate_possession_stats(self, possessions: List[Dict]) -> Dict[str, Any]:
        """Aggregate possession list into duration-based summary statistics.

        Returns:
            Dict with ``total_possessions``, ``avg_duration``, and
            ``possessions_by_duration`` (keys: ``<=8s``, ``8-16s``, ``>16s``).
            Each bucket contains ``count``, ``percentage``, ``total_points``, ``oer``.
        """
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

        short_poss = []
        medium_poss = []
        long_poss = []

        for poss in possessions:
            duration = poss['duration']
            if duration <= 8:
                short_poss.append(poss)
            elif duration <= 16:
                medium_poss.append(poss)
            else:
                long_poss.append(poss)

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

        def _oer(count: int, points: int) -> float:
            return (points / count) * 100 if count else 0.0

        return {
            'total_possessions': total_possessions,
            'avg_duration': round(avg_duration, 2),
            'possessions_by_duration': {
                '<=8s': {
                    'count': short_count,
                    'percentage': round(short_pct, 1),
                    'total_points': short_points,
                    'oer': round(_oer(short_count, short_points), 2)
                },
                '8-16s': {
                    'count': medium_count,
                    'percentage': round(medium_pct, 1),
                    'total_points': medium_points,
                    'oer': round(_oer(medium_count, medium_points), 2)
                },
                '>16s': {
                    'count': long_count,
                    'percentage': round(long_pct, 1),
                    'total_points': long_points,
                    'oer': round(_oer(long_count, long_points), 2)
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

