"""Calculate statistics for lineup combinations (5, 4, or 3 players together)."""

from typing import Dict, List, FrozenSet, Tuple, Optional
from collections import defaultdict


class LineupStatsCalculator:
    """Calculate team statistics when specific lineup is on court."""

    def __init__(self, analyzer):
        """
        Initialize the lineup stats calculator.

        Args:
            analyzer: PlayByPlayAnalyzer instance
        """
        self.analyzer = analyzer
        self.is_fbcyl = analyzer.is_fbcyl

    def calculate_lineup_stats(
        self,
        games: List[Dict],
        team_id: str,
        lineup: FrozenSet[str],
        is_fbcyl: bool
    ) -> Dict:
        """
        Calculate aggregated statistics for a specific lineup across multiple games.

        Args:
            games: List of game data dictionaries with play-by-play
            team_id: Team identifier
            lineup: Frozenset of player IDs in the lineup
            is_fbcyl: Whether data is FBCYL format

        Returns:
            Dict with lineup statistics including minutes, points, ORtg, DRtg, NetRtg
        """
        # Initialize cumulative stats
        total_stats = self._empty_stats()
        total_seconds = 0
        
        # Process each game
        from .playbyplay_analyzer import PlayByPlayAnalyzer
        from .lineup_extractor import LineupExtractor
        
        for game in games:
            analyzer = PlayByPlayAnalyzer(game, is_fbcyl)
            extractor = LineupExtractor(analyzer)
            
            # Get time segments when this lineup was on court
            segments = self._get_lineup_segments(extractor, team_id, lineup)
            
            # Process actions during these segments
            for start, end in segments:
                duration = end - start
                total_seconds += duration
                
                # Get actions during this segment
                actions = self._get_actions_in_timeframe(analyzer, start, end)
                
                # Process each action and accumulate stats
                for action in actions:
                    self._process_action(action, team_id, total_stats)
        
        # Calculate final statistics
        minutes = total_seconds / 60.0
        result = self._calculate_final_stats(total_stats, minutes)
        result['minutes'] = round(minutes, 1)
        result['players'] = lineup
        
        return result

    def calculate_lineup_stats_single_game(
        self,
        analyzer,
        extractor,
        team_id: str,
        lineup: FrozenSet[str]
    ) -> Dict:
        """
        Calculate statistics for a lineup in a single game.

        Args:
            analyzer: PlayByPlayAnalyzer instance for the game
            extractor: LineupExtractor instance for the game
            team_id: Team identifier
            lineup: Frozenset of player IDs in the lineup

        Returns:
            Dict with lineup statistics for this game
        """
        # Initialize stats
        stats = self._empty_stats()
        total_seconds = 0
        
        # Get time segments when this lineup was on court
        segments = self._get_lineup_segments(extractor, team_id, lineup)
        
        # Process actions during these segments
        for start, end in segments:
            duration = end - start
            total_seconds += duration
            
            # Get actions during this segment
            actions = self._get_actions_in_timeframe(analyzer, start, end)
            
            # Process actions with context (for rebound classification)
            self._process_actions_with_context(actions, team_id, stats)
        
        # Calculate final statistics
        minutes = total_seconds / 60.0
        result = self._calculate_final_stats(stats, minutes)
        result['minutes'] = round(minutes, 1)
        result['players'] = lineup
        result['games_played'] = 1  # This is a single game
        result['segments_count'] = len(segments)  # Number of times they played together
        
        return result

    def _empty_stats(self) -> Dict:
        """Create empty statistics dictionary."""
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

    def _get_lineup_segments(
        self,
        extractor,
        team_id: str,
        lineup: FrozenSet[str]
    ) -> List[Tuple[int, int]]:
        """
        Get time segments when specific lineup was on court.

        Args:
            extractor: LineupExtractor instance
            team_id: Team identifier
            lineup: Frozenset of player IDs

        Returns:
            List of (start_seconds, end_seconds) tuples
        """
        segments = []
        game_duration = extractor._get_game_duration()
        
        # Sample every 5 seconds (MUST match lineup_extractor sampling interval)
        current_start = None
        
        for timestamp in range(0, game_duration, 5):
            on_court = extractor.get_lineup_at_timestamp(team_id, timestamp)
            
            # Check if current lineup matches (subset for partial lineups)
            matches = lineup.issubset(on_court) if len(lineup) < 5 else lineup == frozenset(on_court)
            
            if matches:
                if current_start is None:
                    current_start = timestamp
            else:
                if current_start is not None:
                    segments.append((current_start, timestamp))
                    current_start = None
        
        # Close final segment
        if current_start is not None:
            segments.append((current_start, game_duration))
        
        return segments

    def _get_actions_in_timeframe(
        self,
        analyzer,
        start_sec: int,
        end_sec: int
    ) -> List[Dict]:
        """
        Get all play-by-play actions within a timeframe.

        Args:
            analyzer: PlayByPlayAnalyzer instance
            start_sec: Start time in seconds
            end_sec: End time in seconds

        Returns:
            List of action dictionaries
        """
        actions = []
        
        if self.is_fbcyl:
            # FBCYL: moves are in chronological order
            for move in analyzer.lines:
                period = move.get('period')
                min_val = move.get('min')
                sec_val = move.get('sec')
                
                if period is None or min_val is None or sec_val is None:
                    continue
                
                timestamp = analyzer._fbcyl_time_to_seconds(period, min_val, sec_val)
                
                if start_sec <= timestamp <= end_sec:
                    actions.append(move)
        else:
            # FEB: PLAYBYPLAY.LINES is reverse-chronological
            for line in analyzer.lines:
                quarter = line.get('quarter')
                time_str = line.get('time')
                
                if not quarter or not time_str:
                    continue
                
                timestamp = analyzer._time_to_seconds(quarter, time_str)
                
                if start_sec <= timestamp <= end_sec:
                    actions.append(line)
        
        return actions

    def _process_actions_with_context(self, actions: List[Dict], team_id: str, stats: Dict) -> None:
        """
        Process actions with context for better rebound classification.
        
        Args:
            actions: List of actions in chronological order
            team_id: Team identifier
            stats: Statistics dictionary to update
        """
        last_shot_team = None  # Track last team that missed a shot
        
        for idx, action in enumerate(actions):
            # Update last_shot_team if this is a missed shot
            action_team = str(action.get('idTeam', ''))
            
            if self.is_fbcyl:
                move_text = action.get('move', '')
                if 'Intento fallado' in move_text or 'intento fallado' in move_text:
                    last_shot_team = action_team
                elif 'Canasta' in move_text or 'canasta' in move_text:
                    last_shot_team = None  # Made shot, reset
            else:
                # FEB format
                text = action.get('text', '').upper()
                action_type = action.get('action', '')
                if action_type in ('shoot', 'fthrow'):
                    if 'FALLADO' in text or 'FALLA' in text or action.get('logParam4') == '0':
                        last_shot_team = action_team
                    else:
                        last_shot_team = None
            
            # Process the action with rebound context
            self._process_action(action, team_id, stats, last_shot_team)
            
            # Reset last_shot_team if rebound occurred
            if self.is_fbcyl:
                if 'Rebote' in action.get('move', ''):
                    last_shot_team = None
            else:
                if action.get('action') == 'rebound':
                    last_shot_team = None

    def _process_action(self, action: Dict, team_id: str, stats: Dict, last_shot_team: str = None) -> None:
        """
        Process a single action and update statistics.

        Args:
            action: Action dictionary from play-by-play
            team_id: Team identifier for determining team vs opponent
            stats: Statistics dictionary to update
            last_shot_team: Team ID of last missed shot (for rebound classification)
        """
        action_team = str(action.get('idTeam', ''))
        is_team_action = (action_team == team_id)
        
        if self.is_fbcyl:
            self._process_fbcyl_action(action, is_team_action, stats, last_shot_team)
        else:
            self._process_feb_action(action, is_team_action, stats, last_shot_team)

    def _process_fbcyl_action(self, action: Dict, is_team_action: bool, stats: Dict, last_shot_team: str = None) -> None:
        """Process FBCYL format action with rebound classification."""
        move_text = action.get('move', '')
        action_team = str(action.get('idTeam', ''))
        
        # Points
        points = 0
        if 'Canasta de 2' in move_text or 'canasta de 2' in move_text:
            points = 2
            if is_team_action:
                stats['fga_2'] += 1
                stats['fgm_2'] += 1
            else:
                stats['opp_fga_2'] += 1
                stats['opp_fgm_2'] += 1
        elif 'Intento fallado de 2' in move_text:
            if is_team_action:
                stats['fga_2'] += 1
            else:
                stats['opp_fga_2'] += 1
        elif 'Canasta de 3' in move_text or 'canasta de 3' in move_text:
            points = 3
            if is_team_action:
                stats['fga_3'] += 1
                stats['fgm_3'] += 1
            else:
                stats['opp_fga_3'] += 1
                stats['opp_fgm_3'] += 1
        elif 'Intento fallado de 3' in move_text:
            if is_team_action:
                stats['fga_3'] += 1
            else:
                stats['opp_fga_3'] += 1
        elif 'Tiro libre anotado' in move_text or 'Canasta de 1' in move_text:
            points = 1
            if is_team_action:
                stats['fta'] += 1
                stats['ftm'] += 1
            else:
                stats['opp_fta'] += 1
                stats['opp_ftm'] += 1
        elif 'Intento fallado de 1' in move_text:
            if is_team_action:
                stats['fta'] += 1
            else:
                stats['opp_fta'] += 1
        
        # Update points for/against
        if points > 0:
            if is_team_action:
                stats['points_for'] += points
            else:
                stats['points_against'] += points
        
        # Other stats
        if 'Pérdida' in move_text or 'pérdida' in move_text:
            if is_team_action:
                stats['tov'] += 1
            else:
                stats['opp_tov'] += 1
        
        if 'Personal' in move_text or 'Falta' in move_text:
            if is_team_action:
                stats['pf'] += 1
            else:
                stats['opp_pf'] += 1
        
        # Assists (FBCYL)
        if 'Asistencia' in move_text or 'asistencia' in move_text:
            if is_team_action:
                stats['ast'] += 1
            else:
                stats['opp_ast'] += 1
        
        # Steals (FBCYL)
        if 'Robo' in move_text or 'robo' in move_text:
            if is_team_action:
                stats['stl'] += 1
            else:
                stats['opp_stl'] += 1
        
        # Blocks (FBCYL)
        if 'Tapón' in move_text or 'tapón' in move_text or 'Tapon' in move_text:
            if is_team_action:
                stats['blk'] += 1
            else:
                stats['opp_blk'] += 1
        
        # Rebounds (FBCYL format) - use last_shot_team for classification
        if 'Rebote' in move_text or 'rebote' in move_text:
            # If last shot was by same team → offensive rebound
            # Otherwise (or if no last_shot_team tracked) → defensive rebound
            is_offensive = (last_shot_team is not None and last_shot_team == action_team)
            
            if is_offensive:
                if is_team_action:
                    stats['orb'] += 1
                else:
                    stats['opp_orb'] += 1
            else:
                if is_team_action:
                    stats['drb'] += 1
                else:
                    stats['opp_drb'] += 1

    def _process_feb_action(self, action: Dict, is_team_action: bool, stats: Dict, last_shot_team: str = None) -> None:
        """Process FEB format action with rebound classification."""
        text = action.get('text', '').upper()
        action_type = action.get('action', '')
        action_team = str(action.get('idTeam', ''))
        
        # Points and shooting
        points = 0
        if 'TIRO DE 2' in text or 'CANASTA DE 2' in text:
            if is_team_action:
                stats['fga_2'] += 1
                if 'FALLADO' not in text:
                    stats['fgm_2'] += 1
                    points = 2
            else:
                stats['opp_fga_2'] += 1
                if 'FALLADO' not in text:
                    stats['opp_fgm_2'] += 1
                    points = 2
        elif 'TIRO DE 3' in text or 'TRIPLE' in text or 'CANASTA DE 3' in text:
            if is_team_action:
                stats['fga_3'] += 1
                if 'FALLADO' not in text:
                    stats['fgm_3'] += 1
                    points = 3
            else:
                stats['opp_fga_3'] += 1
                if 'FALLADO' not in text:
                    stats['opp_fgm_3'] += 1
                    points = 3
        elif 'TIRO LIBRE' in text or 'TIRO DE 1' in text:
            if is_team_action:
                stats['fta'] += 1
                if 'ANOTADO' in text:
                    stats['ftm'] += 1
                    points = 1
            else:
                stats['opp_fta'] += 1
                if 'ANOTADO' in text:
                    stats['opp_ftm'] += 1
                    points = 1
        
        # Update points for/against
        if points > 0:
            if is_team_action:
                stats['points_for'] += points
            else:
                stats['points_against'] += points
        
        # Rebounds - use last_shot_team for classification (same logic as playbyplay_analyzer)
        if action_type == 'rebound' or 'REBOTE' in text:
            # If last shot was by same team → offensive rebound
            # Otherwise → defensive rebound
            is_offensive = (last_shot_team is not None and last_shot_team == action_team)
            
            if is_offensive:
                if is_team_action:
                    stats['orb'] += 1
                else:
                    stats['opp_orb'] += 1
            else:
                if is_team_action:
                    stats['drb'] += 1
                else:
                    stats['opp_drb'] += 1
        
        # Assists
        if 'ASISTENCIA' in text or action_type == 'assist':
            if is_team_action:
                stats['ast'] += 1
            else:
                stats['opp_ast'] += 1
        
        # Steals
        if 'ROBO' in text or action_type == 'steal':
            if is_team_action:
                stats['stl'] += 1
            else:
                stats['opp_stl'] += 1
        
        # Blocks
        if 'TAPÓN' in text or action_type == 'block':
            if is_team_action:
                stats['blk'] += 1
            else:
                stats['opp_blk'] += 1
        
        # Turnovers
        if 'PÉRDIDA' in text or 'PERDIDA' in text or action_type == 'turnover':
            if is_team_action:
                stats['tov'] += 1
            else:
                stats['opp_tov'] += 1
        
        # Fouls
        if 'FALTA' in text or action_type == 'foul':
            if is_team_action:
                stats['pf'] += 1
            else:
                stats['opp_pf'] += 1

    def _calculate_final_stats(self, stats: Dict, minutes: float) -> Dict:
        """
        Calculate advanced statistics from raw stats.

        Args:
            stats: Raw statistics dictionary
            minutes: Minutes played

        Returns:
            Dict with calculated statistics including ORtg, DRtg, NetRtg
        """
        result = {
            'points_for': stats['points_for'],
            'points_against': stats['points_against'],
            'plus_minus': stats['points_for'] - stats['points_against'],
        }
        
        # Calculate possessions (team and opponent)
        fga = stats['fga_2'] + stats['fga_3']
        orb = stats['orb']
        tov = stats['tov']
        fta = stats['fta']
        
        opp_fga = stats['opp_fga_2'] + stats['opp_fga_3']
        opp_orb = stats['opp_orb']
        opp_tov = stats['opp_tov']
        opp_fta = stats['opp_fta']
        
        # Possessions formula: FGA - ORB + TOV + 0.44*FTA
        team_poss = fga - orb + tov + 0.44 * fta
        opp_poss = opp_fga - opp_orb + opp_tov + 0.44 * opp_fta
        
        # Average possessions
        possessions = (team_poss + opp_poss) / 2.0 if team_poss + opp_poss > 0 else 0
        result['possessions'] = round(possessions, 1)
        
        # Offensive Rating (points per 100 possessions)
        if possessions > 0:
            result['ortg'] = round((stats['points_for'] / possessions) * 100, 1)
        else:
            result['ortg'] = 0.0
        
        # Defensive Rating (points allowed per 100 possessions)
        if possessions > 0:
            result['drtg'] = round((stats['points_against'] / possessions) * 100, 1)
        else:
            result['drtg'] = 0.0
        
        # Net Rating
        result['net_rating'] = round(result['ortg'] - result['drtg'], 1)
        
        # Shooting percentages
        fgm = stats['fgm_2'] + stats['fgm_3']
        fgm_3 = stats['fgm_3']
        
        # eFG% = (FGM + 0.5 * 3PM) / FGA
        if fga > 0:
            result['efg_pct'] = round(((fgm + 0.5 * fgm_3) / fga) * 100, 1)
        else:
            result['efg_pct'] = 0.0
        
        # TOV% = TOV / (FGA + 0.44*FTA + TOV)
        denominator = fga + 0.44 * fta + tov
        if denominator > 0:
            result['tov_pct'] = round((tov / denominator) * 100, 1)
        else:
            result['tov_pct'] = 0.0
        
        # ORB% = ORB / (ORB + Opp_DRB)
        orb_chances = orb + stats['opp_drb']
        if orb_chances > 0:
            result['orb_pct'] = round((orb / orb_chances) * 100, 1)
        else:
            result['orb_pct'] = 0.0
        
        # FT Rate = FTA / FGA
        if fga > 0:
            result['ftr'] = round(fta / fga, 2)
        else:
            result['ftr'] = 0.0
        
        # Store raw stats for reference
        result['fgm'] = fgm
        result['fga'] = fga
        result['fg3m'] = fgm_3
        result['fg3a'] = stats['fga_3']
        result['ftm'] = stats['ftm']
        result['fta'] = fta
        result['orb'] = orb
        result['drb'] = stats['drb']
        result['trb'] = orb + stats['drb']
        result['ast'] = stats['ast']
        result['stl'] = stats['stl']
        result['blk'] = stats['blk']
        result['tov'] = tov
        result['pf'] = stats['pf']
        
        return result
