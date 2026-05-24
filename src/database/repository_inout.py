"""IN/OUT and together-stats repository mixin."""

from typing import Dict, List, Optional
from pymongo.errors import PyMongoError

from utils.collection_utils import is_fbcyl as _is_fbcyl
from database._inout_helpers_mixin import InOutHelpersMixin


class InOutRepositoryMixin(InOutHelpersMixin):
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

            # Detect if this is a FBCYL collection
            is_fbcyl = _is_fbcyl(collection_name)

            # Get total count for progress reporting (count_documents, no docs loaded)
            total_games = self.count_games_with_playbyplay(collection_name, date_filter)

            if progress_callback:
                progress_callback(0, max(total_games, 1))

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
                # FEB: player_id is consistent across games.
                # Find team_id via a single find_one() instead of iterating the cursor
                # (iterating would exhaust it before the main processing loop).
                player_id_compare = player_id
                player_team_id = None

                collection_obj = self.connection.get_collection(collection_name)
                player_doc = collection_obj.find_one(
                    {
                        "BOXSCORE.TEAM.PLAYER.id": player_id,
                        "PLAYBYPLAY.LINES": {"$exists": True, "$ne": None},
                    },
                    {"BOXSCORE.TEAM.id": 1, "BOXSCORE.TEAM.PLAYER.id": 1},
                )
                if player_doc:
                    for team in player_doc.get("BOXSCORE", {}).get("TEAM", []):
                        for player in team.get("PLAYER", []):
                            if player.get("id") == player_id_compare:
                                player_team_id = team.get("id")
                                break
                        if player_team_id:
                            break

                if not player_team_id:
                    return {}

            # Lazy cursor — one document in memory at a time
            games = self.get_games_with_playbyplay(collection_name, date_filter)

            if progress_callback and total_games > 0:
                progress_callback(1, total_games)

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

            # Report initial progress
            if progress_callback:
                progress_callback(0, max(total_games, 1))

            for game_index, game in enumerate(games):
                # Report progress at the start of each game
                if progress_callback:
                    progress_callback(game_index + 1, max(total_games, 1))
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
                                    minutes = float(m)
                                    # Phantom player: inscribed but never played.
                                    # FBCYL assigns timePlayed=40 to these players while
                                    # every activity stat remains 0.
                                    if minutes == 40.0:
                                        data = p.get('data', {}) or {}
                                        activity = sum(
                                            data.get(k, 0) or 0
                                            for k in (
                                                'score', 'shotsOfTwoAttempted',
                                                'shotsOfThreeAttempted', 'shotsOfOneAttempted',
                                                'offensiveRebound', 'defensiveRebound',
                                                'assists', 'lost', 'block', 'steals',
                                            )
                                        )
                                        if activity == 0:
                                            return 0.0
                                    return minutes
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

            games, total_games = self._fetch_games_with_progress(collection_name, date_filter, progress_callback)
            is_fbcyl = _is_fbcyl(collection_name)
            
            total_stats = self._initialize_together_stats()
            games_analyzed = 0
            games_participated = 0

            for game_index, game in enumerate(games):
                self._report_progress(progress_callback, game_index + 1, max(total_games, 1))
                
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
            games, total_games = self._fetch_games_with_progress(collection_name, date_filter, progress_callback)
            is_fbcyl = _is_fbcyl(collection_name)
            
            total_stats = self._initialize_player_individual_stats()
            team_stats = self._initialize_together_stats()
            games_analyzed = 0
            games_participated = 0

            for game_index, game in enumerate(games):
                self._report_progress(progress_callback, game_index + 1, max(total_games, 1))
                
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

        except PyMongoError:
            return {}
