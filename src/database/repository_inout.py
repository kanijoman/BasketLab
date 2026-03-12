"""IN/OUT and together-stats repository mixin."""

from typing import Dict, List, Optional
from pymongo.errors import PyMongoError

from src.utils.collection_utils import is_fbcyl as _is_fbcyl


class InOutRepositoryMixin:
    """Mixin providing per-player IN/OUT and together-stats query methods."""

    def get_player_in_out_stats(self, collection_name: str, player_id: str,
                                 date_filter: Dict = None, debug: bool = False,
                                 progress_callback=None) -> Dict:
        """
        Get IN/OUT statistics for a specific player using play-by-play data.

        Args:
            collection_name: Name of the collection
            player_id: Player's ID (idPlayer from JSON)
            date_filter: Optional MongoDB date filter dict with datetime object
            progress_callback: Optional callback function(current, total) for progress reporting

        Returns:
            Dictionary with 'in' and 'out' statistics and metadata
        """
        if not self.connection.is_connected():
            return {}

        try:
            from .playbyplay_analyzer import PlayByPlayAnalyzer, InOutStatsCalculator

            # Report initial progress - fetching games
            if progress_callback:
                progress_callback(0, 100)  # Use percentage-based for this phase

            # Get all games with play-by-play data (this can be slow)
            games = self.get_games_with_playbyplay(collection_name, date_filter)

            # Report that loading is complete
            if progress_callback and len(games) > 0:
                progress_callback(1, len(games))  # Signal that we have the data and starting analysis

            # Detect if this is a FBCYL collection
            is_fbcyl = _is_fbcyl(collection_name)

            # Convert player_id to appropriate type for comparison
            if is_fbcyl:
                # FBCYL: player_id is UUID (stats.teams[].players[].uuid)
                # UUID is stable across games, but actorId changes per game
                # We extract actorId per game to identify actions in moves[]
                # We don't need to find player_team_id upfront since both actorId and teamIdIntern
                # change per game. We'll extract them in the per-game loop below.
                player_id_compare = player_id  # Keep as string (UUID format)
                player_team_id = None  # Not used for FBCYL (per-game extraction instead)
            else:
                # FEB: player_id is consistent across games, find team ID from first appearance
                player_id_compare = player_id
                player_team_id = None

                # Find player's team ID from first appearance
                for game in games:
                    # FEB structure: BOXSCORE.TEAM[].PLAYER[]
                    boxscore = game.get('BOXSCORE', {})
                    teams = boxscore.get('TEAM', [])

                    for team in teams:
                        players = team.get('PLAYER', [])
                        for player in players:
                            if player.get('id') == player_id_compare:
                                player_team_id = team.get('id')
                                break
                        if player_team_id:
                            break

                    if player_team_id:
                        break

                if not player_team_id:
                    return {}

            # Aggregate stats across all games
            total_stats_in = {
                'points_for': 0, 'points_against': 0,
                'fgm_2': 0, 'fga_2': 0, 'fgm_3': 0, 'fga_3': 0,
                'ftm': 0, 'fta': 0, 'orb': 0, 'drb': 0,
                'ast': 0, 'stl': 0, 'blk': 0, 'tov': 0, 'pf': 0,
                'minutes': 0, 'games': 0,
                # opponent aggregated keys (if provided by analyzer)
                'opp_fgm_2': 0, 'opp_fga_2': 0, 'opp_fgm_3': 0, 'opp_fga_3': 0,
                'opp_ftm': 0, 'opp_fta': 0, 'opp_orb': 0, 'opp_drb': 0,
                'opp_ast': 0, 'opp_stl': 0, 'opp_blk': 0, 'opp_tov': 0, 'opp_pf': 0
            }

            total_stats_out = {
                'points_for': 0, 'points_against': 0,
                'fgm_2': 0, 'fga_2': 0, 'fgm_3': 0, 'fga_3': 0,
                'ftm': 0, 'fta': 0, 'orb': 0, 'drb': 0,
                'ast': 0, 'stl': 0, 'blk': 0, 'tov': 0, 'pf': 0,
                'minutes': 0, 'games': 0,
                # opponent aggregated keys (if provided by analyzer)
                'opp_fgm_2': 0, 'opp_fga_2': 0, 'opp_fgm_3': 0, 'opp_fga_3': 0,
                'opp_ftm': 0, 'opp_fta': 0, 'opp_orb': 0, 'opp_drb': 0,
                'opp_ast': 0, 'opp_stl': 0, 'opp_blk': 0, 'opp_tov': 0, 'opp_pf': 0
            }

            games_analyzed = 0
            debug_outputs = []
            games_participated = 0
            total_games = len(games)

            # Report initial progress
            if progress_callback:
                progress_callback(0, total_games)

            for game_index, game in enumerate(games):
                # Report progress at the start of each game
                if progress_callback:
                    progress_callback(game_index + 1, total_games)
                # Default per-game container (to avoid UnboundLocalError in finally)
                game_stats = {}
                game_was_skipped = False

                # For FBCYL: Get actorId AND teamIdIntern for THIS specific game (both change per game)
                current_game_actor_id = None
                current_game_team_id = None

                if is_fbcyl:
                    # Helper function to normalize player names: first initial + surnames
                    def normalize_name(name):
                        if not name:
                            return ""
                        words = name.split()
                        if len(words) >= 3:
                            # First initial + two surnames
                            return f"{words[0][0]} {words[-2]} {words[-1]}"
                        elif len(words) >= 2:
                            # First initial + one surname
                            return f"{words[0][0]} {words[-1]}"
                        return name

                    # Try to get normalized name from player_id if it's a name-based identifier
                    # (in case UUID wasn't available and we're using surnames as fallback)
                    target_normalized = normalize_name(player_id_compare) if not player_id_compare.count('-') == 4 else None

                    stats = game.get('stats', {})
                    for team in stats.get('teams', []):
                        for player in team.get('players', []):
                            # FBCYL: Match by UUID (stable identifier) OR by normalized name
                            player_uuid = player.get('uuid')
                            player_name = player.get('name', '')
                            player_normalized = normalize_name(player_name)

                            if player_uuid == player_id_compare or \
                               (target_normalized and player_normalized == target_normalized):
                                # Extract actorId for THIS game (used in moves[])
                                current_game_actor_id = player.get('actorId')
                                current_game_team_id = team.get('teamIdIntern') or team.get('teamIdExtern')
                                break
                        if current_game_actor_id:
                            break

                    # Skip this game if player not found
                    if not current_game_actor_id or not current_game_team_id:
                        continue

                # Determine if player actually played in this game using BOXSCORE/stats minutes
                def _player_minutes_played(g, pid) -> float:
                    if is_fbcyl:
                        # For FBCYL, pid is the actorId for this specific game
                        # FBCYL structure: stats.teams[].players[]
                        stats = g.get('stats', {})
                        for team in stats.get('teams', []):
                            for p in team.get('players', []):
                                p_id = p.get('actorId')
                                if p_id == pid:
                                    m = p.get('timePlayed')  # FBCYL uses 'timePlayed' field
                                    if m is None:
                                        return 0.0
                                    if isinstance(m, (int, float)):
                                        return float(m)
                                    try:
                                        return float(m)
                                    except Exception:
                                        return 0.0
                        return 0.0
                    else:
                        # FEB structure: BOXSCORE.TEAM[].PLAYER[]
                        box = g.get('BOXSCORE', {})
                        for team in box.get('TEAM', []):
                            for p in team.get('PLAYER', []):
                                if p.get('id') == pid:
                                    m = p.get('min')
                                    if m is None:
                                        return 0.0
                                    if isinstance(m, (int, float)):
                                        return float(m)
                                    s = str(m).strip()
                                    if s in ('0', '0:00', ''):
                                        return 0.0
                                    if ':' in s:
                                        try:
                                            parts = s.split(':')
                                            mm = int(parts[0])
                                            ss = int(parts[1]) if len(parts) > 1 else 0
                                            return mm + ss / 60.0
                                        except Exception:
                                            return 0.0
                                    try:
                                        return float(s)
                                    except Exception:
                                        return 0.0
                        return 0.0

                # For FBCYL, use current game's actorId; for FEB use player_id_compare
                pid_for_game = current_game_actor_id if is_fbcyl else player_id_compare
                minutes_played = _player_minutes_played(game, pid_for_game)

                # Determine if the player's team participated in this game
                def _team_participated(g, team_id) -> bool:
                    if is_fbcyl:
                        # FBCYL: Use teamIdIntern (matches moves[].idTeam for play-by-play)
                        stats = g.get('stats', {})
                        for team in stats.get('teams', []):
                            t_id = team.get('teamIdIntern') or team.get('teamIdExtern')
                            if t_id == team_id:
                                # If there are players listed, consider the team participated
                                players = team.get('players', [])
                                if not players:
                                    return False
                                # If any player has minutes > 0, the team participated
                                for p in players:
                                    m = p.get('timePlayed')
                                    if m is None:
                                        continue
                                    if isinstance(m, (int, float)) and m > 0:
                                        return True
                                # If no player has minutes but players exist, assume team participated
                                return True
                        return False
                    else:
                        # FEB structure: BOXSCORE.TEAM[]
                        box = g.get('BOXSCORE', {})
                        for team in box.get('TEAM', []):
                            if team.get('id') == team_id:
                                # If there are players listed, consider the team participated
                                players = team.get('PLAYER', [])
                                if not players:
                                    return False
                                # If any player has minutes > 0, the team participated
                                for p in players:
                                    m = p.get('min')
                                    if m is None:
                                        continue
                                    if isinstance(m, (int, float)) and m > 0:
                                        return True
                                    s = str(m).strip()
                                    if s and s not in ('0', '0:00'):
                                        # treat presence of a non-zero string minute as participation
                                        return True
                                # If no player has minutes but players exist, assume team participated
                                return True
                        return False

                # Use current game's team_id for FBCYL, or player_team_id for FEB
                team_id_for_game = current_game_team_id if is_fbcyl else player_team_id
                team_played = _team_participated(game, team_id_for_game)

                # Count games where the player actually participated (min > 0)
                if minutes_played > 0.0:
                    games_participated += 1

                try:
                    # Skip games where the player's team did not participate
                    if not team_played:
                        game_was_skipped = True
                        if debug:
                            debug_outputs.append({
                                'game_id': game.get('_id'),
                                'skipped': True,
                                'reason': 'team_not_participating',
                                'in': None,
                                'out': None,
                                'minutes_played': minutes_played,
                                'player_id': player_id
                            })
                        continue
                    analyzer = PlayByPlayAnalyzer(game, is_fbcyl=is_fbcyl)
                    calculator = InOutStatsCalculator(analyzer)

                    # For FBCYL: use actorId and teamIdIntern for this specific game
                    game_stats = calculator.calculate_in_out_stats(pid_for_game, team_id_for_game)

                    # Accumulate IN stats
                    for key in list(total_stats_in.keys()):
                        if key in game_stats.get('in', {}):
                            total_stats_in[key] += game_stats['in'][key]

                    # Accumulate OUT stats
                    for key in list(total_stats_out.keys()):
                        if key in game_stats.get('out', {}):
                            total_stats_out[key] += game_stats['out'][key]

                    games_analyzed += 1

                except Exception as e:
                    if debug:
                        import traceback
                        traceback.print_exc()
                    continue

                finally:
                    if debug and not game_was_skipped:
                        debug_outputs.append({
                            'game_id': game.get('_id'),
                            'skipped': False,
                            'in': game_stats.get('in') if isinstance(game_stats, dict) else None,
                            'out': game_stats.get('out') if isinstance(game_stats, dict) else None,
                            'minutes_played': minutes_played,
                            'player_id': player_id
                        })

            # Use games_participated as the denominator for per-game minutes (Min/J)
            total_stats_in['games'] = games_participated
            total_stats_out['games'] = games_participated

            if debug:
                # Save debug outputs to a JSON file in repository root
                try:
                    import json, os
                    debug_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), f"debug_inout_{player_id}.json")
                    with open(debug_file, 'w', encoding='utf-8') as f:
                        json.dump(debug_outputs, f, ensure_ascii=False, indent=2)
                except Exception as e:
                    pass

            return {
                'in': total_stats_in,
                'out': total_stats_out,
                'player_id': player_id,
                'player_team_id': player_team_id,
                'games_analyzed': games_analyzed
            }

        except PyMongoError as e:
            return {}

    def get_two_players_together_stats(self, collection_name: str, player1_id: str, 
                                        player2_id: str, date_filter: Dict = None, 
                                        debug: bool = False, progress_callback=None) -> Dict:
        """
        Get statistics when two specific players are on court together.

        Args:
            collection_name: Name of the collection
            player1_id: First player's ID (idPlayer from JSON)
            player2_id: Second player's ID (idPlayer from JSON)
            date_filter: Optional MongoDB date filter dict with datetime object
            progress_callback: Optional callback function(current, total) for progress reporting

        Returns:
            Dictionary with statistics when both players are together on court
        """
        if not self.connection.is_connected():
            return {}

        try:
            from .playbyplay_analyzer import PlayByPlayAnalyzer, InOutStatsCalculator
            from .inout_repository_helper import InOutRepositoryHelper

            games = self._fetch_games_with_progress(collection_name, date_filter, progress_callback)
            is_fbcyl = _is_fbcyl(collection_name)
            
            total_stats = self._initialize_together_stats()
            games_analyzed = 0
            games_participated = 0

            for game_index, game in enumerate(games):
                self._report_progress(progress_callback, game_index + 1, len(games))
                
                player_info = InOutRepositoryHelper.find_players_in_game(
                    game, player1_id, player2_id, is_fbcyl
                )
                
                if not player_info.all_found:
                    continue

                try:
                    analyzer = PlayByPlayAnalyzer(game, is_fbcyl=is_fbcyl)
                    
                    segments1 = analyzer.get_player_court_segments(player_info.player1_actor_id)
                    segments2 = analyzer.get_player_court_segments(player_info.player2_actor_id)
                    
                    together_segments = InOutRepositoryHelper.calculate_overlap_segments(
                        segments1, segments2
                    )
                    
                    if not together_segments:
                        continue
                    
                    time_together = InOutRepositoryHelper.calculate_total_time(together_segments)
                    
                    actions = InOutRepositoryHelper.filter_actions_by_segments(
                        analyzer, together_segments, is_fbcyl
                    )
                    
                    opponent_id = InOutRepositoryHelper.find_opponent_team_id(
                        game, player_info.team_id, is_fbcyl
                    )
                    
                    calculator = InOutStatsCalculator(analyzer)
                    game_stats = calculator._calculate_stats_from_actions(
                        actions, player_info.team_id, opponent_id or ""
                    )
                    
                    self._accumulate_stats(total_stats, game_stats)
                    total_stats['minutes'] += time_together
                    
                    games_analyzed += 1
                    if time_together > 0:
                        games_participated += 1

                except Exception as e:
                    if debug:
                        import traceback
                        traceback.print_exc()
                    continue

            total_stats['games'] = games_participated

            return {
                'together': total_stats,
                'player1_id': player1_id,
                'player2_id': player2_id,
                'games_analyzed': games_analyzed
            }

        except PyMongoError as e:
            return {}

    def _process_game_with_teammate(self, game: Dict, main_player_id: str, teammate_id: str,
                                   is_fbcyl: bool, debug: bool = False) -> Optional[Dict]:
        """
        Process a single game to extract player and team stats when main player plays with teammate.
        
        Args:
            game: Game document
            main_player_id: Main player's ID
            teammate_id: Teammate's ID
            is_fbcyl: Whether this is FBCYL format
            debug: Whether to print debug info
            
        Returns:
            Dict with 'player_stats', 'team_stats', 'time_together' or None if players not found together
        """
        from .playbyplay_analyzer import PlayByPlayAnalyzer, InOutStatsCalculator
        from .inout_repository_helper import InOutRepositoryHelper
        
        player_info = InOutRepositoryHelper.find_players_in_game(
            game, main_player_id, teammate_id, is_fbcyl
        )
        
        if not player_info.all_found:
            return None
        
        try:
            analyzer = PlayByPlayAnalyzer(game, is_fbcyl=is_fbcyl)
            
            segments_main = analyzer.get_player_court_segments(player_info.player1_actor_id)
            segments_teammate = analyzer.get_player_court_segments(player_info.player2_actor_id)
            
            together_segments = InOutRepositoryHelper.calculate_overlap_segments(
                segments_main, segments_teammate
            )
            
            if not together_segments:
                return None
            
            time_together = InOutRepositoryHelper.calculate_total_time(together_segments)
            
            actions = InOutRepositoryHelper.filter_actions_by_segments(
                analyzer, together_segments, is_fbcyl
            )
            
            # Extract individual stats for main player
            player_game_stats = self._calculate_player_individual_stats_from_actions(
                actions, player_info.player1_actor_id, is_fbcyl
            )
            
            # Calculate team stats for possessions
            opponent_id = InOutRepositoryHelper.find_opponent_team_id(
                game, player_info.team_id, is_fbcyl
            )
            
            calculator = InOutStatsCalculator(analyzer)
            team_game_stats = calculator._calculate_stats_from_actions(
                actions, player_info.team_id, opponent_id or ""
            )
            
            return {
                'player_stats': player_game_stats,
                'team_stats': team_game_stats,
                'time_together': time_together
            }
            
        except Exception as e:
            if debug:
                import traceback
                traceback.print_exc()
            return None
    
    def get_player_individual_stats_with_teammate(self, collection_name: str, 
                                                   main_player_id: str, teammate_id: str,
                                                   date_filter: Dict = None, debug: bool = False,
                                                   progress_callback=None) -> Dict:
        """
        Get individual statistics of main_player when playing with teammate, normalized per 100 possessions.

        Args:
            collection_name: Name of the collection
            main_player_id: Main player's ID (idPlayer from JSON)
            teammate_id: Teammate's ID (idPlayer from JSON)
            date_filter: Optional MongoDB date filter dict with datetime object
            progress_callback: Optional callback function(current, total) for progress reporting

        Returns:
            Dictionary with main player's individual and normalized (per 100 poss) statistics
        """
        if not self.connection.is_connected():
            return {}

        try:
            games = self._fetch_games_with_progress(collection_name, date_filter, progress_callback)
            is_fbcyl = _is_fbcyl(collection_name)
            
            total_stats = self._initialize_player_individual_stats()
            team_stats = self._initialize_together_stats()
            games_analyzed = 0
            games_participated = 0

            for game_index, game in enumerate(games):
                self._report_progress(progress_callback, game_index + 1, len(games))
                
                game_result = self._process_game_with_teammate(
                    game, main_player_id, teammate_id, is_fbcyl, debug
                )
                
                if game_result is None:
                    continue
                
                # Accumulate stats
                self._accumulate_player_individual_stats(total_stats, game_result['player_stats'])
                self._accumulate_stats(team_stats, game_result['team_stats'])
                total_stats['minutes'] += game_result['time_together']
                team_stats['minutes'] += game_result['time_together']
                
                games_analyzed += 1
                if game_result['time_together'] > 0:
                    games_participated += 1

            total_stats['games'] = games_participated
            team_stats['games'] = games_participated

            # Calculate team possessions and normalize player stats
            possessions = self._calculate_possessions_from_stats(team_stats)
            normalized_stats = self._normalize_player_stats_per_100poss(
                total_stats, possessions
            )

            return {
                'raw_stats': total_stats,
                'team_stats': team_stats,
                'possessions': possessions,
                'per_100_poss': normalized_stats,
                'main_player_id': main_player_id,
                'teammate_id': teammate_id,
                'games_analyzed': games_analyzed
            }

        except PyMongoError as e:
            return {}
    
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
    
    def _process_fbcyl_player_action(self, action: Dict, player_actor_id: str, stats: Dict) -> None:
        """
        Process a single FBCYL action for individual player stats.
        
        Args:
            action: FBCYL action dictionary
            player_actor_id: Player's actor ID
            stats: Statistics dictionary to update (modified in place)
        """
        actor_id = str(action.get('actorId', ''))
        if actor_id != player_actor_id:
            return
        
        move_text = action.get('move', '')
        
        # Points scored and shots (based on Spanish FBCYL patterns)
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
        
        # Other stats (check if these patterns exist in FBCYL)
        move_lower = move_text.lower()
        if 'asistencia' in move_lower:
            stats['ast'] += 1
        if 'robo' in move_lower or 'recuperaci├│n' in move_lower:
            stats['stl'] += 1
        if 'tap├│n' in move_lower or 'bloqueo' in move_lower:
            stats['blk'] += 1
        if 'p├®rdida' in move_lower:
            stats['tov'] += 1
        if 'personal' in move_lower or 'falta' in move_lower:
            stats['pf'] += 1
        if 'rebote' in move_lower:
            if 'ofensivo' in move_lower:
                stats['orb'] += 1
            elif 'defensivo' in move_lower:
                stats['drb'] += 1
            else:
                # Generic rebound, count as defensive by default
                stats['drb'] += 1
    
    def _process_feb_player_action(self, action: Dict, player_actor_id: str, stats: Dict,
                                   context: Dict) -> None:
        """
        Process a single FEB action for individual player stats.
        
        Args:
            action: FEB action dictionary
            player_actor_id: Player's actor ID
            stats: Statistics dictionary to update (modified in place)
            context: Shared context dict with 'last_shot_team' and 'player_team' keys
        """
        actor_id = str(action.get('idPlayer', ''))
        action_type = action.get('action', '')
        text = action.get('text', '').upper()
        current_team = str(action.get('idTeam', ''))
        
        # Track player's team for rebound context
        if actor_id == player_actor_id and context['player_team'] is None:
            context['player_team'] = current_team
        
        # Track last shot team for rebound classification
        if action_type in ['shoot', 'fthrow']:
            if 'FALLADO' in text or 'MISS' in text:
                context['last_shot_team'] = current_team
            else:
                context['last_shot_team'] = None  # Made shots don't lead to rebounds
        
        if actor_id != player_actor_id:
            return
        
        # Process player's action based on type
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
    
    def _calculate_player_individual_stats_from_actions(self, actions: List[Dict], 
                                                        player_actor_id: str,
                                                        is_fbcyl: bool) -> Dict:
        """
        Calculate individual player statistics from filtered actions.

        Args:
            actions: List of play-by-play actions
            player_actor_id: Actor ID of the main player
            is_fbcyl: Whether this is FBCYL format

        Returns:
            Dictionary with player's individual statistics
        """
        stats = self._initialize_player_individual_stats()
        
        if is_fbcyl:
            # FBCYL: Simple iteration
            for action in actions:
                self._process_fbcyl_player_action(action, player_actor_id, stats)
        else:
            # FEB: Track context for rebound classification
            context = {'last_shot_team': None, 'player_team': None}
            for action in actions:
                self._process_feb_player_action(action, player_actor_id, stats, context)
        
        return stats
    
    def _accumulate_player_individual_stats(self, total_stats: Dict, game_stats: Dict) -> None:
        """Accumulate player individual statistics."""
        for key in ['points', 'fgm_2', 'fga_2', 'fgm_3', 'fga_3', 'ftm', 'fta',
                   'orb', 'drb', 'ast', 'stl', 'blk', 'tov', 'pf']:
            if key in game_stats:
                total_stats[key] += game_stats[key]

    def _calculate_possessions_from_stats(self, stats: Dict) -> float:
        """
        Calculate team possessions from statistics.
        Formula: FGA + (0.45 * FTA) + TOV - ORB
        """
        fga = stats.get('fga_2', 0) + stats.get('fga_3', 0)
        fta = stats.get('fta', 0)
        tov = stats.get('tov', 0)
        orb = stats.get('orb', 0)
        
        possessions = fga + (0.45 * fta) + tov - orb
        return max(possessions, 1)  # Avoid division by zero

    def _normalize_player_stats_per_100poss(self, stats: Dict, possessions: float) -> Dict:
        """
        Normalize player individual statistics per 100 possessions.
        
        Args:
            stats: Raw player statistics
            possessions: Team possessions when player was on court
            
        Returns:
            Dictionary with normalized statistics per 100 possessions
        """
        if possessions <= 0:
            return {key: 0.0 for key in ['points', 'fgm_2', 'fga_2', 'fgm_3', 'fga_3', 
                                         'ftm', 'fta', 'orb', 'drb', 'ast', 'stl', 
                                         'blk', 'tov', 'pf']}
        
        factor = 100.0 / possessions
        
        return {
            'points': stats.get('points', 0) * factor,
            'fgm_2': stats.get('fgm_2', 0) * factor,
            'fga_2': stats.get('fga_2', 0) * factor,
            'fgm_3': stats.get('fgm_3', 0) * factor,
            'fga_3': stats.get('fga_3', 0) * factor,
            'ftm': stats.get('ftm', 0) * factor,
            'fta': stats.get('fta', 0) * factor,
            'orb': stats.get('orb', 0) * factor,
            'drb': stats.get('drb', 0) * factor,
            'ast': stats.get('ast', 0) * factor,
            'stl': stats.get('stl', 0) * factor,
            'blk': stats.get('blk', 0) * factor,
            'tov': stats.get('tov', 0) * factor,
            'pf': stats.get('pf', 0) * factor,
            # Calculate percentages (not normalized)
            'fg2_pct': (stats.get('fgm_2', 0) / stats.get('fga_2', 1) * 100) if stats.get('fga_2', 0) > 0 else 0,
            'fg3_pct': (stats.get('fgm_3', 0) / stats.get('fga_3', 1) * 100) if stats.get('fga_3', 0) > 0 else 0,
            'ft_pct': (stats.get('ftm', 0) / stats.get('fta', 1) * 100) if stats.get('fta', 0) > 0 else 0,
            'efg_pct': ((stats.get('fgm_2', 0) + 1.5 * stats.get('fgm_3', 0)) / 
                       (stats.get('fga_2', 0) + stats.get('fga_3', 0)) * 100) 
                       if (stats.get('fga_2', 0) + stats.get('fga_3', 0)) > 0 else 0,
            'ts_pct': (stats.get('points', 0) / 
                      (2 * (stats.get('fga_2', 0) + stats.get('fga_3', 0) + 0.44 * stats.get('fta', 0))) * 100)
                      if (stats.get('fga_2', 0) + stats.get('fga_3', 0) + stats.get('fta', 0)) > 0 else 0
        }

    def _fetch_games_with_progress(self, collection_name: str, date_filter: Dict,
                                   progress_callback) -> List[Dict]:
        """Fetch games and report initial progress."""
        if progress_callback:
            progress_callback(0, 100)
        
        games = self.get_games_with_playbyplay(collection_name, date_filter)
        
        if progress_callback and len(games) > 0:
            progress_callback(1, len(games))
        
        return games

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

    def _report_progress(self, progress_callback, current: int, total: int) -> None:
        """Report progress if callback provided."""
        if progress_callback:
            progress_callback(current, total)

    def _accumulate_stats(self, total_stats: Dict, game_stats: Dict) -> None:
        """Accumulate game statistics into total."""
        for key in list(total_stats.keys()):
            if key in game_stats:
                total_stats[key] += game_stats[key]

    def _old_calculate_stats_from_actions_helper(self, actions: List[Dict], team_id: str, 
                                             is_fbcyl: bool, game: Dict) -> Dict:
        """
        Helper method to calculate statistics from a list of actions.
        
        Args:
            actions: List of action dictionaries
            team_id: Team ID to calculate stats for
            is_fbcyl: Whether this is FBCYL format
            game: Full game data for context
            
        Returns:
            Dictionary with calculated statistics
        """
        # Find opponent team ID
        opponent_team_id = None
        
        if is_fbcyl:
            stats = game.get('stats', {})
            for team in stats.get('teams', []):
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
        
        stats = {
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
                # FBCYL processing
                move_text = action.get('move', '').upper()
                action_team = str(action.get('idTeam', ''))
                points = action.get('points', 0)
                
                # Points
                if points > 0:
                    if action_team == str(team_id):
                        stats['points_for'] += points
                    elif opponent_team_id and action_team == str(opponent_team_id):
                        stats['points_against'] += points
                
                # Determine target (team or opponent)
                is_team_action = (action_team == str(team_id))
                prefix = '' if is_team_action else 'opp_'
                
                # Process stats based on move text
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
                # FEB processing
                text = action.get('text', '').upper()
                action_type = action.get('action', '')
                action_team = str(action.get('idTeam', ''))
                
                is_team_action = (action_team == str(team_id))
                prefix = '' if is_team_action else 'opp_'
                
                # Points
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
                
                # Other stats
                if action_type == 'rebound' or 'REBOTE' in text:
                    # Simplified: assume offensive if rebote ofensivo mentioned
                    if 'OFENSIVO' in text:
                        stats[f'{prefix}orb'] += 1
                    else:
                        stats[f'{prefix}drb'] += 1
                elif 'ASISTENCIA' in text:
                    stats[f'{prefix}ast'] += 1
                elif 'ROBO' in text or 'RECUPERA' in text:
                    stats[f'{prefix}stl'] += 1
                elif 'TAP├ôN' in text or 'TAPON' in text:
                    stats[f'{prefix}blk'] += 1
                elif 'P├ëRDIDA' in text or 'PERDIDA' in text:
                    stats[f'{prefix}tov'] += 1
                elif 'FALTA' in text:
                    stats[f'{prefix}pf'] += 1
        
        return stats

