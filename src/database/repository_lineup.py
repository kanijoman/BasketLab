"""Lineup analysis repository mixin."""

from typing import Dict, List, Optional, FrozenSet
from pymongo.errors import PyMongoError

from utils.collection_utils import is_fbcyl as _is_fbcyl


class LineupRepositoryMixin:
    """Mixin providing lineup analysis query methods."""

    def get_lineup_analysis(
        self,
        collection_name: str,
        team_id: str,
        team_name: str,
        combination_size: int = 5,
        date_filter: Dict = None,
        is_fbcyl: bool = False,
        progress_callback=None
    ) -> List[Dict]:
        """
        Get lineup analysis for a team showing best and worst lineups by statistics.

        Args:
            collection_name: MongoDB collection name
            team_id: Team identifier
            team_name: Team name for filtering
            combination_size: Size of player combination (3, 4, or 5)
            date_filter: Optional date filter dictionary
            is_fbcyl: Whether data is FBCYL format
            progress_callback: Optional callback function(current, total) for progress

        Returns:
            List of lineup dictionaries with statistics, sorted by net rating
        """
        from .playbyplay_analyzer import PlayByPlayAnalyzer
        from .lineup_extractor import LineupExtractor
        from .lineup_stats_calculator import LineupStatsCalculator

        try:
            # Get all games with play-by-play for this team
            games = self.get_games_for_team(
                collection_name,
                team_id,
                only_with_playbyplay=True
            )

            if not games:
                return []

            # Apply date filter if provided
            if date_filter:
                filtered_games = []
                for game in games:
                    # Extract date from game
                    if is_fbcyl:
                        game_date = game.get('date', '')
                    else:
                        game_date = game.get('HEADER', {}).get('starttime', '').split(' - ')[0]
                    
                    # Compare with filter (assuming filter is like {"$gte": "2024-01-01"})
                    if '$gte' in date_filter:
                        if game_date >= date_filter['$gte']:
                            filtered_games.append(game)
                    else:
                        filtered_games.append(game)
                
                games = filtered_games

            if not games:
                return []

            # Track lineup statistics across all games
            lineup_stats_map = {}  # frozenset -> stats dict
            total_games = len(games)

            for game_idx, game in enumerate(games):
                try:
                    # Report progress
                    if progress_callback:
                        progress_callback(game_idx + 1, total_games)

                    # Initialize analyzers
                    analyzer = PlayByPlayAnalyzer(game, is_fbcyl)
                    extractor = LineupExtractor(analyzer)
                    calculator = LineupStatsCalculator(analyzer)

                    # Get all lineup combinations for this game (NO minimum threshold per game)
                    lineup_times = extractor.get_lineup_combinations(
                        team_id,
                        combination_size,
                        min_seconds=0  # Detect ALL lineups, filter later by total time
                    )

                    # Calculate stats for each lineup in this game
                    for lineup_key, time_seconds in lineup_times.items():
                        lineup_stats = calculator.calculate_lineup_stats_single_game(
                            analyzer,
                            extractor,
                            team_id,
                            lineup_key
                        )

                        # Aggregate with existing stats
                        if lineup_key not in lineup_stats_map:
                            # First time seeing this lineup
                            lineup_stats['avg_minutes_per_game'] = lineup_stats.get('minutes', 0)
                            lineup_stats_map[lineup_key] = lineup_stats
                        else:
                            # Merge stats from this game
                            existing = lineup_stats_map[lineup_key]
                            self._merge_lineup_stats(existing, lineup_stats)

                except Exception as e:
                    # Skip games with errors (e.g., incomplete play-by-play)
                    print(f"Error processing game for lineup analysis: {e}")
                    continue

            # Convert to list and add player names
            # Filter by total accumulated time and games played for representative lineups
            lineup_list = []
            min_total_minutes = 15  # 15 minutes minimum total
            min_games_played = 5    # At least 5 games
            
            for lineup_key, stats in lineup_stats_map.items():
                total_minutes = stats.get('minutes', 0)
                games_played = stats.get('games_played', 0)
                
                # Skip lineups that don't meet minimum thresholds
                if total_minutes < min_total_minutes or games_played < min_games_played:
                    continue
                
                # Get player names
                player_names = self._get_player_names_for_lineup(
                    collection_name,
                    lineup_key,
                    is_fbcyl
                )
                
                stats['player_names'] = player_names
                stats['player_ids'] = list(lineup_key)
                lineup_list.append(stats)

            # Sort by net rating (descending)
            lineup_list.sort(key=lambda x: x.get('net_rating', 0), reverse=True)

            return lineup_list

        except PyMongoError as e:
            print(f"MongoDB error in get_lineup_analysis: {e}")
            return []

    def _merge_lineup_stats(self, existing: Dict, new_stats: Dict) -> None:
        """
        Merge new lineup stats into existing stats.

        Args:
            existing: Existing stats dictionary (modified in place)
            new_stats: New stats to add
        """
        # Aggregate counting stats
        counting_stats = [
            'points_for', 'points_against', 'fgm', 'fga', 'fg3m', 'fg3a',
            'ftm', 'fta', 'orb', 'drb', 'trb', 'ast', 'stl', 'blk', 'tov', 'pf'
        ]
        
        for stat in counting_stats:
            existing[stat] = existing.get(stat, 0) + new_stats.get(stat, 0)
        
        # Aggregate minutes, possessions, games, and segments
        old_minutes = existing.get('minutes', 0)
        new_minutes = new_stats.get('minutes', 0)
        existing['minutes'] = old_minutes + new_minutes
        existing['possessions'] = existing.get('possessions', 0) + new_stats.get('possessions', 0)
        existing['games_played'] = existing.get('games_played', 0) + new_stats.get('games_played', 0)
        existing['segments_count'] = existing.get('segments_count', 0) + new_stats.get('segments_count', 0)
        
        # Calculate average minutes per game
        if existing['games_played'] > 0:
            existing['avg_minutes_per_game'] = round(existing['minutes'] / existing['games_played'], 1)
        else:
            existing['avg_minutes_per_game'] = 0.0
        
        # Recalculate derived stats
        existing['plus_minus'] = existing['points_for'] - existing['points_against']
        
        possessions = existing['possessions']
        if possessions > 0:
            existing['ortg'] = round((existing['points_for'] / possessions) * 100, 1)
            existing['drtg'] = round((existing['points_against'] / possessions) * 100, 1)
            existing['net_rating'] = round(existing['ortg'] - existing['drtg'], 1)
        
        # Recalculate percentages
        fga = existing.get('fga', 0)
        if fga > 0:
            fgm = existing.get('fgm', 0)
            fg3m = existing.get('fg3m', 0)
            existing['efg_pct'] = round(((fgm + 0.5 * fg3m) / fga) * 100, 1)
            
            fta = existing.get('fta', 0)
            existing['ftr'] = round(fta / fga, 2)
        
        tov = existing.get('tov', 0)
        fta = existing.get('fta', 0)
        denominator = fga + 0.44 * fta + tov
        if denominator > 0:
            existing['tov_pct'] = round((tov / denominator) * 100, 1)

    def _get_player_names_for_lineup(
        self,
        collection_name: str,
        lineup_keys: FrozenSet[str],
        is_fbcyl: bool
    ) -> List[str]:
        """
        Get player names from their IDs.

        Args:
            collection_name: MongoDB collection name
            lineup_keys: Frozenset of player IDs
            is_fbcyl: Whether data is FBCYL format

        Returns:
            List of player names
        """
        names = []
        player_ids_list = list(lineup_keys)
        
        # Try to find all players in a single query
        try:
            collection = self.connection.get_collection(collection_name)
            
            if is_fbcyl:
                # FBCYL: actorId in stats.teams.players
                # Convert to ints for matching
                player_ids_int = []
                for pid in player_ids_list:
                    try:
                        player_ids_int.append(int(pid))
                    except:
                        player_ids_int.append(pid)
                
                game = collection.find_one(
                    {"stats.teams.players.actorId": {"$in": player_ids_int}},
                    {"stats.teams.players": 1}
                )
                
                if game:
                    player_map = {}
                    for team in game.get('stats', {}).get('teams', []):
                        for player in team.get('players', []):
                            actor_id = str(player.get('actorId'))
                            if actor_id in player_ids_list:
                                player_map[actor_id] = player.get('name', 'Unknown')
                    
                    # Preserve order and handle missing players
                    for pid in player_ids_list:
                        names.append(player_map.get(pid, f"Player {pid}"))
                else:
                    names = [f"Player {pid}" for pid in player_ids_list]
            else:
                # FEB: id in BOXSCORE.TEAM.PLAYER
                # Convert to mixed types for matching
                player_ids_mixed = []
                for pid in player_ids_list:
                    player_ids_mixed.append(pid)
                    try:
                        player_ids_mixed.append(int(pid))
                    except:
                        pass
                
                game = collection.find_one(
                    {"BOXSCORE.TEAM.PLAYER.id": {"$in": player_ids_mixed}},
                    {"BOXSCORE.TEAM.PLAYER": 1}
                )
                
                if game:
                    player_map = {}
                    for team in game.get('BOXSCORE', {}).get('TEAM', []):
                        for player in team.get('PLAYER', []):
                            player_id = str(player.get('id', ''))
                            if player_id in player_ids_list:
                                player_map[player_id] = player.get('name', 'Unknown')
                    
                    # Preserve order and handle missing players
                    for pid in player_ids_list:
                        names.append(player_map.get(pid, f"Player {pid}"))
                else:
                    names = [f"Player {pid}" for pid in player_ids_list]
                    
        except Exception as e:
            print(f"Error getting player names: {e}")
            names = [f"Player {pid}" for pid in player_ids_list]
        
        return names
