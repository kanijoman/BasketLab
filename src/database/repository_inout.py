"""IN/OUT repository mixin."""

from typing import Dict, Iterable, List
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


    def get_players_in_out_stats(self, collection_name: str, player_ids: Iterable[str], date_filter: Dict = None) -> Dict[str, Dict]:
        """``{player id: what get_player_in_out_stats gives for him}`` for several players in ONE pass over the games.

        The query of one player walks every game of the competition and builds an analyzer for each game of his team; for all the players of a competition that is players x games (23/11/2026: 10 games
        18 s, 30 games 134 s; a conference of 370 games took hours). Here each game is read once and its analyzer is shared by every player that needs it. Each player's result is exactly the one of
        the query for that player (``tests/test_inout_single_pass.py``): the same rules, the games in the same order, so the totals add up the same."""
        ids = list(dict.fromkeys(player_ids))
        if not self.connection.is_connected():
            return {player_id: {} for player_id in ids}
        try:
            from .playbyplay_analyzer import PlayByPlayAnalyzer, InOutStatsCalculator

            is_fbcyl = _is_fbcyl(collection_name)
            runs: Dict[str, Dict] = {}
            for player_id in ids:
                player_team_id = None
                if not is_fbcyl:
                    player_team_id = self._find_feb_player_team_id(collection_name, player_id)
                    if not player_team_id:
                        continue                                                    # not found: an empty result, as the query of one player gives
                runs[player_id] = {'team': player_team_id, 'in': self._empty_in_out_totals(), 'out': self._empty_in_out_totals(), 'analyzed': 0, 'participated': 0}
            if runs:
                for game in self.get_games_with_playbyplay(collection_name, date_filter):          # lazy cursor: one document in memory at a time
                    analyzer, failed = None, False
                    for player_id, run in runs.items():
                        if is_fbcyl:
                            identity = find_fbcyl_player(game, player_id)
                            if identity is None:
                                continue
                            pid_for_game, team_id_for_game = identity
                        else:
                            pid_for_game, team_id_for_game = player_id, run['team']
                        if player_minutes_played(game, pid_for_game, is_fbcyl) > 0.0:
                            run['participated'] += 1
                        if not team_participated(game, team_id_for_game, is_fbcyl):
                            continue
                        try:
                            if analyzer is None and not failed:
                                try:
                                    analyzer = PlayByPlayAnalyzer(game, is_fbcyl=is_fbcyl)       # once per game, shared by its players
                                except Exception:
                                    failed = True                                   # as the query of one player: that game adds nothing
                            if analyzer is None:
                                continue
                            game_stats = InOutStatsCalculator(analyzer).calculate_in_out_stats(pid_for_game, team_id_for_game)
                            self._add_in_out_game(run['in'], game_stats.get('in', {}))
                            self._add_in_out_game(run['out'], game_stats.get('out', {}))
                            run['analyzed'] += 1
                        except Exception:
                            continue
            out: Dict[str, Dict] = {}
            for player_id in ids:
                run = runs.get(player_id)
                if run is None:
                    out[player_id] = {}
                    continue
                run['in']['games'] = run['out']['games'] = run['participated']
                out[player_id] = {'in': run['in'], 'out': run['out'], 'player_id': player_id, 'player_team_id': run['team'], 'games_analyzed': run['analyzed']}
            return out
        except PyMongoError:
            return {player_id: {} for player_id in ids}
