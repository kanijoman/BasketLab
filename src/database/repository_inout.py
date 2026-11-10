"""IN/OUT repository mixin."""

from typing import Dict, List, Optional
from pymongo.errors import PyMongoError

from utils.collection_utils import is_fbcyl as _is_fbcyl
from ._inout_game_lookup import find_fbcyl_player, find_feb_team_id, player_minutes_played, team_participated
from .pbp_stat_counters import empty_stats


class InOutRepositoryMixin:
    """Mixin providing the per-player IN/OUT query."""

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
