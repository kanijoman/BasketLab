"""IN/OUT and together-stats repository mixin."""

from typing import Dict, List, Optional
from pymongo.errors import PyMongoError

from utils.collection_utils import is_fbcyl as _is_fbcyl
from database._inout_helpers_mixin import InOutHelpersMixin
from ._inout_game_lookup import find_fbcyl_player, find_feb_team_id, player_minutes_played, team_participated
from .pbp_stat_counters import empty_stats


class InOutRepositoryMixin(InOutHelpersMixin):
    """Mixin providing per-player IN/OUT and together-stats query methods."""

    def _find_feb_player_team_id(self, collection_name: str, player_id: str):
        """Team of a FEB player, from ONE game that has play-by-play and the player (iterating the cursor would exhaust it before the main loop)."""
        player_doc = self.connection.get_collection(collection_name).find_one(
            {
                "BOXSCORE.TEAM.PLAYER.id": player_id,
                "PLAYBYPLAY.LINES": {"$exists": True, "$ne": None},
            },
            {"BOXSCORE.TEAM.id": 1, "BOXSCORE.TEAM.PLAYER.id": 1},
        )
        return find_feb_team_id(player_doc, player_id)

    @staticmethod
    def _empty_in_out_totals() -> Dict:
        totals = empty_stats()
        totals.update({'minutes': 0, 'games': 0})
        return totals

    @staticmethod
    def _add_in_out_game(total: Dict, game_side: Dict) -> None:
        for key in total:
            if key in game_side:
                total[key] += game_side[key]

    @staticmethod
    def _write_in_out_debug(player_id: str, debug_outputs: List[Dict]) -> None:
        """Save the debug outputs to a JSON file in the repository root."""
        try:
            import json, os
            debug_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), f"debug_inout_{player_id}.json")
            with open(debug_file, 'w', encoding='utf-8') as f:
                json.dump(debug_outputs, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

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

            is_fbcyl = _is_fbcyl(collection_name)
            # count_documents: no docs loaded
            total_games = self.count_games_with_playbyplay(collection_name, date_filter)
            if progress_callback:
                progress_callback(0, max(total_games, 1))

            # FBCYL: player_id is the UUID (stable across games), while the actorId and the team id of the moves change per game, so both are
            # looked up in each game. FEB: the player id is stable and so is its team.
            player_team_id = None
            if not is_fbcyl:
                player_team_id = self._find_feb_player_team_id(collection_name, player_id)
                if not player_team_id:
                    return {}

            games = self.get_games_with_playbyplay(collection_name, date_filter)     # lazy cursor: one document in memory at a time
            if progress_callback and total_games > 0:
                progress_callback(1, total_games)

            total_stats_in, total_stats_out = self._empty_in_out_totals(), self._empty_in_out_totals()
            games_analyzed = games_participated = 0
            debug_outputs: List[Dict] = []
            if progress_callback:
                progress_callback(0, max(total_games, 1))

            for game_index, game in enumerate(games):
                if progress_callback:
                    progress_callback(game_index + 1, max(total_games, 1))

                if is_fbcyl:
                    identity = find_fbcyl_player(game, player_id)
                    if identity is None:
                        continue
                    pid_for_game, team_id_for_game = identity
                else:
                    pid_for_game, team_id_for_game = player_id, player_team_id

                minutes_played = player_minutes_played(game, pid_for_game, is_fbcyl)
                team_played = team_participated(game, team_id_for_game, is_fbcyl)
                if minutes_played > 0.0:
                    games_participated += 1          # the games where the player actually played (min > 0): the denominator of Min/J

                game_stats = {}
                try:
                    if not team_played:
                        if debug:
                            debug_outputs.append({'game_id': game.get('_id'), 'skipped': True, 'reason': 'team_not_participating',
                                                  'in': None, 'out': None, 'minutes_played': minutes_played, 'player_id': player_id})
                        continue
                    calculator = InOutStatsCalculator(PlayByPlayAnalyzer(game, is_fbcyl=is_fbcyl))
                    game_stats = calculator.calculate_in_out_stats(pid_for_game, team_id_for_game)
                    self._add_in_out_game(total_stats_in, game_stats.get('in', {}))
                    self._add_in_out_game(total_stats_out, game_stats.get('out', {}))
                    games_analyzed += 1
                except Exception:
                    if debug:
                        import traceback
                        traceback.print_exc()
                    continue
                finally:
                    if debug and team_played:
                        debug_outputs.append({
                            'game_id': game.get('_id'), 'skipped': False,
                            'in': game_stats.get('in') if isinstance(game_stats, dict) else None,
                            'out': game_stats.get('out') if isinstance(game_stats, dict) else None,
                            'minutes_played': minutes_played, 'player_id': player_id})

            total_stats_in['games'] = total_stats_out['games'] = games_participated
            if debug:
                self._write_in_out_debug(player_id, debug_outputs)

            return {
                'in': total_stats_in,
                'out': total_stats_out,
                'player_id': player_id,
                'player_team_id': player_team_id,
                'games_analyzed': games_analyzed
            }

        except PyMongoError:
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
