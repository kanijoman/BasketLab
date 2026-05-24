"""Private helper mixin for IN/OUT and together-stats calculations.

Extracted from repository_inout.py to reduce its size.
``InOutRepositoryMixin`` inherits from this class.
"""

from typing import Dict, Iterable, List, Tuple


class InOutHelpersMixin:
    """Pure-computation helpers used by InOutRepositoryMixin."""

    # ------------------------------------------------------------------
    # Initializers
    # ------------------------------------------------------------------

    def _initialize_player_individual_stats(self) -> Dict:
        """Initialize empty player individual statistics dictionary."""
        return {
            'points': 0,
            'fgm_2': 0, 'fga_2': 0,
            'fgm_3': 0, 'fga_3': 0,
            'ftm': 0, 'fta': 0,
            'orb': 0, 'drb': 0,
            'ast': 0, 'stl': 0, 'blk': 0, 'tov': 0, 'pf': 0,
            'minutes': 0, 'games': 0
        }

    def _initialize_together_stats(self) -> Dict:
        """Initialize empty statistics dictionary."""
        return {
            'points_for': 0, 'points_against': 0,
            'fgm_2': 0, 'fga_2': 0, 'fgm_3': 0, 'fga_3': 0,
            'ftm': 0, 'fta': 0, 'orb': 0, 'drb': 0,
            'ast': 0, 'stl': 0, 'blk': 0, 'tov': 0, 'pf': 0,
            'minutes': 0, 'games': 0,
            'opp_fgm_2': 0, 'opp_fga_2': 0, 'opp_fgm_3': 0, 'opp_fga_3': 0,
            'opp_ftm': 0, 'opp_fta': 0, 'opp_orb': 0, 'opp_drb': 0,
            'opp_ast': 0, 'opp_stl': 0, 'opp_blk': 0, 'opp_tov': 0, 'opp_pf': 0
        }

    # ------------------------------------------------------------------
    # Accumulation helpers
    # ------------------------------------------------------------------

    def _accumulate_player_individual_stats(self, total_stats: Dict, game_stats: Dict) -> None:
        """Accumulate player individual statistics."""
        for key in ['points', 'fgm_2', 'fga_2', 'fgm_3', 'fga_3', 'ftm', 'fta',
                    'orb', 'drb', 'ast', 'stl', 'blk', 'tov', 'pf']:
            if key in game_stats:
                total_stats[key] += game_stats[key]

    def _accumulate_stats(self, total_stats: Dict, game_stats: Dict) -> None:
        """Accumulate game statistics into total."""
        for key in list(total_stats.keys()):
            if key in game_stats:
                total_stats[key] += game_stats[key]

    def _report_progress(self, progress_callback, current: int, total: int) -> None:
        """Report progress if callback provided."""
        if progress_callback:
            progress_callback(current, total)

    # ------------------------------------------------------------------
    # Game fetching
    # ------------------------------------------------------------------

    def _fetch_games_with_progress(
        self, collection_name: str, date_filter: Dict, progress_callback
    ) -> Tuple[Iterable[Dict], int]:
        """Fetch a lazy game cursor and report initial progress.

        Returns a ``(cursor, total_count)`` tuple so callers can track progress
        without calling ``len()`` on the cursor (which would materialise it).
        ``total_count`` is obtained via ``count_documents()`` before the cursor
        is opened.

        Args:
            collection_name: MongoDB collection name.
            date_filter: Optional date range filter.
            progress_callback: Optional ``(current, total) -> None`` callback.

        Returns:
            ``(cursor, total_count)`` — an iterable cursor and the total number
            of matching game documents.
        """
        total = self.count_games_with_playbyplay(collection_name, date_filter)

        if progress_callback:
            progress_callback(0, max(total, 1))

        cursor = self.get_games_with_playbyplay(collection_name, date_filter)

        if progress_callback and total > 0:
            progress_callback(1, total)

        return cursor, total

    # ------------------------------------------------------------------
    # FBCYL action processing
    # ------------------------------------------------------------------

    def _process_fbcyl_player_action(self, action: Dict, player_actor_id: str, stats: Dict) -> None:
        """Process a single FBCYL action for individual player stats."""
        actor_id = str(action.get('actorId', ''))
        if actor_id != player_actor_id:
            return

        move_text = action.get('move', '')

        if 'Canasta de 1' in move_text:
            stats['points'] += 1
            stats['ftm'] += 1
            stats['fta'] += 1
        elif 'Intento fallado de 1' in move_text:
            stats['fta'] += 1
        elif 'Canasta de 2' in move_text:
            stats['points'] += 2
            stats['fgm_2'] += 1
            stats['fga_2'] += 1
        elif 'Intento fallado de 2' in move_text:
            stats['fga_2'] += 1
        elif 'Canasta de 3' in move_text:
            stats['points'] += 3
            stats['fgm_3'] += 1
            stats['fga_3'] += 1
        elif 'Intento fallado de 3' in move_text:
            stats['fga_3'] += 1

        move_lower = move_text.lower()
        if 'asistencia' in move_lower:
            stats['ast'] += 1
        if 'robo' in move_lower or 'recuperaci\u00f3n' in move_lower:
            stats['stl'] += 1
        if 'tap\u00f3n' in move_lower or 'bloqueo' in move_lower:
            stats['blk'] += 1
        if 'p\u00e9rdida' in move_lower:
            stats['tov'] += 1
        if 'personal' in move_lower or 'falta' in move_lower:
            stats['pf'] += 1
        if 'rebote' in move_lower:
            if 'ofensivo' in move_lower:
                stats['orb'] += 1
            elif 'defensivo' in move_lower:
                stats['drb'] += 1
            else:
                stats['drb'] += 1

    # ------------------------------------------------------------------
    # FEB action processing
    # ------------------------------------------------------------------

    def _process_feb_shot(self, text: str, stats: Dict) -> None:
        """Process FEB shoot action."""
        if 'TIRO DE 2' in text or 'TIRO DE CAMPO' in text:
            if 'ANOTADO' in text or 'CONVERTIDO' in text:
                stats['points'] += 2
                stats['fgm_2'] += 1
                stats['fga_2'] += 1
            else:
                stats['fga_2'] += 1
        elif 'TIRO DE 3' in text or '3 PUNTOS' in text:
            if 'ANOTADO' in text or 'CONVERTIDO' in text:
                stats['points'] += 3
                stats['fgm_3'] += 1
                stats['fga_3'] += 1
            else:
                stats['fga_3'] += 1

    def _process_feb_free_throw(self, text: str, stats: Dict) -> None:
        """Process FEB free throw action."""
        stats['fta'] += 1
        if 'ANOTADO' in text:
            stats['points'] += 1
            stats['ftm'] += 1

    def _process_feb_rebound(self, stats: Dict, context: Dict) -> None:
        """Process FEB rebound with context."""
        last_shot_team = context.get('last_shot_team')
        player_team = context.get('player_team')

        if last_shot_team and player_team:
            if last_shot_team == player_team:
                stats['orb'] += 1
            else:
                stats['drb'] += 1
        else:
            stats['drb'] += 1
        context['last_shot_team'] = None

    def _process_feb_player_action(self, action: Dict, player_actor_id: str, stats: Dict,
                                   context: Dict) -> None:
        """Process a single FEB action for individual player stats."""
        actor_id = str(action.get('idPlayer', ''))
        action_type = action.get('action', '')
        text = action.get('text', '').upper()
        current_team = str(action.get('idTeam', ''))

        if actor_id == player_actor_id and context['player_team'] is None:
            context['player_team'] = current_team

        if action_type in ['shoot', 'fthrow']:
            if 'FALLADO' in text or 'MISS' in text:
                context['last_shot_team'] = current_team
            else:
                context['last_shot_team'] = None

        if actor_id != player_actor_id:
            return

        if action_type == 'shoot':
            self._process_feb_shot(text, stats)
        elif action_type == 'fthrow':
            self._process_feb_free_throw(text, stats)
        elif action_type == 'assist':
            stats['ast'] += 1
        elif action_type == 'recovery':
            stats['stl'] += 1
        elif action_type == 'blockshot':
            stats['blk'] += 1
        elif action_type == 'lose':
            stats['tov'] += 1
        elif action_type == 'foul':
            stats['pf'] += 1
        elif action_type == 'rebound':
            self._process_feb_rebound(stats, context)

    # ------------------------------------------------------------------
    # Individual stats from filtered actions
    # ------------------------------------------------------------------

    def _calculate_player_individual_stats_from_actions(self, actions: List[Dict],
                                                        player_actor_id: str,
                                                        is_fbcyl: bool) -> Dict:
        """Calculate individual player statistics from filtered actions."""
        stats = self._initialize_player_individual_stats()

        if is_fbcyl:
            for action in actions:
                self._process_fbcyl_player_action(action, player_actor_id, stats)
        else:
            context = {'last_shot_team': None, 'player_team': None}
            for action in actions:
                self._process_feb_player_action(action, player_actor_id, stats, context)

        return stats

    # ------------------------------------------------------------------
    # Possession and normalization calculators
    # ------------------------------------------------------------------

    def _calculate_possessions_from_stats(self, stats: Dict) -> float:
        """Calculate team possessions: FGA + (0.45*FTA) + TOV - ORB."""
        fga = stats.get('fga_2', 0) + stats.get('fga_3', 0)
        fta = stats.get('fta', 0)
        tov = stats.get('tov', 0)
        orb = stats.get('orb', 0)
        return max(fga + (0.45 * fta) + tov - orb, 1)

    def _normalize_player_stats_per_100poss(self, stats: Dict, possessions: float) -> Dict:
        """Normalize player individual statistics per 100 possessions."""
        if possessions <= 0:
            return {key: 0.0 for key in ['points', 'fgm_2', 'fga_2', 'fgm_3', 'fga_3',
                                          'ftm', 'fta', 'orb', 'drb', 'ast', 'stl',
                                          'blk', 'tov', 'pf']}

        factor = 100.0 / possessions
        fga2 = stats.get('fga_2', 0)
        fga3 = stats.get('fga_3', 0)
        fta  = stats.get('fta', 0)
        fgm2 = stats.get('fgm_2', 0)
        fgm3 = stats.get('fgm_3', 0)
        ftm  = stats.get('ftm', 0)
        pts  = stats.get('points', 0)

        return {
            'points': pts * factor,
            'fgm_2': fgm2 * factor,
            'fga_2': fga2 * factor,
            'fgm_3': fgm3 * factor,
            'fga_3': fga3 * factor,
            'ftm': ftm * factor,
            'fta': fta * factor,
            'orb': stats.get('orb', 0) * factor,
            'drb': stats.get('drb', 0) * factor,
            'ast': stats.get('ast', 0) * factor,
            'stl': stats.get('stl', 0) * factor,
            'blk': stats.get('blk', 0) * factor,
            'tov': stats.get('tov', 0) * factor,
            'pf':  stats.get('pf',  0) * factor,
            'fg2_pct': (fgm2 / fga2 * 100) if fga2 > 0 else 0,
            'fg3_pct': (fgm3 / fga3 * 100) if fga3 > 0 else 0,
            'ft_pct':  (ftm  / fta  * 100) if fta  > 0 else 0,
            'efg_pct': ((fgm2 + 1.5 * fgm3) / (fga2 + fga3) * 100) if (fga2 + fga3) > 0 else 0,
            'ts_pct':  (pts / (2 * (fga2 + fga3 + 0.44 * fta)) * 100)
                       if (fga2 + fga3 + fta) > 0 else 0,
        }

    # ------------------------------------------------------------------
    # Legacy helper (kept for backwards-compat, not used in new code)
    # ------------------------------------------------------------------

    def _old_calculate_stats_from_actions_helper(self, actions: List[Dict], team_id: str,
                                                  is_fbcyl: bool, game: Dict) -> Dict:
        """Legacy helper — kept for backwards compatibility."""
        opponent_team_id = None

        if is_fbcyl:
            stats_data = game.get('stats', {})
            for team in stats_data.get('teams', []):
                tid = team.get('teamIdIntern') or team.get('teamIdExtern')
                if tid != team_id:
                    opponent_team_id = tid
                    break
        else:
            teams = game.get('HEADER', {}).get('TEAM', [])
            for team in teams:
                tid = team.get('id')
                if tid != team_id:
                    opponent_team_id = tid
                    break

        stats: Dict = {
            'points_for': 0, 'points_against': 0,
            'fgm_2': 0, 'fga_2': 0, 'fgm_3': 0, 'fga_3': 0,
            'ftm': 0, 'fta': 0, 'orb': 0, 'drb': 0,
            'ast': 0, 'stl': 0, 'blk': 0, 'tov': 0, 'pf': 0,
            'opp_fgm_2': 0, 'opp_fga_2': 0, 'opp_fgm_3': 0, 'opp_fga_3': 0,
            'opp_ftm': 0, 'opp_fta': 0, 'opp_orb': 0, 'opp_drb': 0,
            'opp_ast': 0, 'opp_stl': 0, 'opp_blk': 0, 'opp_tov': 0, 'opp_pf': 0
        }

        for action in actions:
            if is_fbcyl:
                move_text = action.get('move', '').upper()
                action_team = str(action.get('idTeam', ''))
                points = action.get('points', 0)

                if points > 0:
                    if action_team == str(team_id):
                        stats['points_for'] += points
                    elif opponent_team_id and action_team == str(opponent_team_id):
                        stats['points_against'] += points

                is_team_action = (action_team == str(team_id))
                prefix = '' if is_team_action else 'opp_'

                if points == 2 and '2PT' in move_text:
                    stats[f'{prefix}fga_2'] += 1
                    if 'SUCCESS' in move_text or points > 0:
                        stats[f'{prefix}fgm_2'] += 1
                elif points == 3 and '3PT' in move_text:
                    stats[f'{prefix}fga_3'] += 1
                    if 'SUCCESS' in move_text or points > 0:
                        stats[f'{prefix}fgm_3'] += 1
                elif 'FREE_THROW' in move_text:
                    stats[f'{prefix}fta'] += 1
                    if 'SUCCESS' in move_text or points > 0:
                        stats[f'{prefix}ftm'] += 1

                if 'REBOUND_OFF' in move_text:
                    stats[f'{prefix}orb'] += 1
                elif 'REBOUND_DEF' in move_text:
                    stats[f'{prefix}drb'] += 1
                elif 'ASSIST' in move_text:
                    stats[f'{prefix}ast'] += 1
                elif 'STEAL' in move_text or 'TURNOVER_STEAL' in move_text:
                    stats[f'{prefix}stl'] += 1
                elif 'BLOCK' in move_text:
                    stats[f'{prefix}blk'] += 1
                elif 'TURNOVER' in move_text and 'STEAL' not in move_text:
                    stats[f'{prefix}tov'] += 1
                elif 'FOUL' in move_text:
                    stats[f'{prefix}pf'] += 1
            else:
                text = action.get('text', '').upper()
                action_type = action.get('action', '')
                action_team = str(action.get('idTeam', ''))

                is_team_action = (action_team == str(team_id))
                prefix = '' if is_team_action else 'opp_'

                if 'CANASTA DE 2' in text or 'TIRO DE 2' in text:
                    stats[f'{prefix}fga_2'] += 1
                    if 'FALLADO' not in text:
                        stats[f'{prefix}fgm_2'] += 1
                        stats['points_for' if is_team_action else 'points_against'] += 2
                elif 'CANASTA DE 3' in text or 'TIRO DE 3' in text or 'TRIPLE' in text:
                    stats[f'{prefix}fga_3'] += 1
                    if 'FALLADO' not in text:
                        stats[f'{prefix}fgm_3'] += 1
                        stats['points_for' if is_team_action else 'points_against'] += 3
                elif 'TIRO LIBRE' in text:
                    stats[f'{prefix}fta'] += 1
                    if 'ANOTADO' in text:
                        stats[f'{prefix}ftm'] += 1
                        stats['points_for' if is_team_action else 'points_against'] += 1

                if action_type == 'rebound' or 'REBOTE' in text:
                    if 'OFENSIVO' in text:
                        stats[f'{prefix}orb'] += 1
                    else:
                        stats[f'{prefix}drb'] += 1
                elif 'ASISTENCIA' in text:
                    stats[f'{prefix}ast'] += 1
                elif 'ROBO' in text or 'RECUPERA' in text:
                    stats[f'{prefix}stl'] += 1
                elif 'TAP\u00d3N' in text or 'TAPON' in text:
                    stats[f'{prefix}blk'] += 1
                elif 'P\u00c9RDIDA' in text or 'PERDIDA' in text:
                    stats[f'{prefix}tov'] += 1
                elif 'FALTA' in text:
                    stats[f'{prefix}pf'] += 1

        return stats
