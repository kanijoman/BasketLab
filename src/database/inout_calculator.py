"""IN/OUT statistics calculator -- extracted from playbyplay_analyzer.py."""

from typing import Dict, List, Tuple, Optional
from .playbyplay_core import PlayByPlayAnalyzer

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


