"""Possession-stats repository mixin."""

from typing import Dict
from pymongo.errors import PyMongoError

from utils.collection_utils import is_fbcyl as _is_fbcyl


class PossessionRepositoryMixin:
    """Mixin providing team possession statistics query methods."""

    def get_team_possession_stats(self, collection_name: str, team_id: str,
                                   date_filter: Dict = None) -> Dict:
        """
        Get possession statistics for a team using play-by-play data.

        Args:
            collection_name: Name of the collection
            team_id: Team's ID
            date_filter: Optional MongoDB date filter dict with datetime object

        Returns:
            Dictionary with possession statistics:
            - total_possessions: Total number of possessions across all games
            - avg_duration: Average possession duration in seconds
            - possessions_by_duration: Stats for <=8s, 8-16s, >16s with count, points, and OER
            - games_analyzed: Number of games included in analysis
        """
        if not self.connection.is_connected():
            return {}

        try:
            from .playbyplay_analyzer import PossessionAnalyzer

            # Get games for this specific team WITH play-by-play data only (optimized)
            games = self.get_games_for_team(collection_name, team_id, only_with_playbyplay=True)
            
            if not games:
                return {
                    'total_possessions': 0,
                    'avg_duration': 0.0,
                    'possessions_by_duration': {
                        '<=8s': {'count': 0, 'total_points': 0, 'oer': 0.0},
                        '8-16s': {'count': 0, 'total_points': 0, 'oer': 0.0},
                        '>16s': {'count': 0, 'total_points': 0, 'oer': 0.0}
                    },
                    'games_analyzed': 0
                }
            
            # Detect if this is a FBCYL collection
            is_fbcyl = _is_fbcyl(collection_name)

            # Aggregate stats across all games
            all_possessions = []
            short_poss = {'count': 0, 'total_points': 0}  # <=8s
            medium_poss = {'count': 0, 'total_points': 0}  # 8-16s
            long_poss = {'count': 0, 'total_points': 0}  # >16s
            games_analyzed = 0

            for game in games:
                try:
                    analyzer = PossessionAnalyzer(game, is_fbcyl=is_fbcyl)
                    game_stats = analyzer.calculate_possessions(team_id)

                    # Aggregate totals
                    all_possessions.extend([game_stats['avg_duration']] * game_stats['total_possessions'])
                    
                    # Aggregate by duration
                    for duration_key in ['<=8s', '8-16s', '>16s']:
                        duration_stats = game_stats['possessions_by_duration'][duration_key]
                        if duration_key == '<=8s':
                            short_poss['count'] += duration_stats['count']
                            short_poss['total_points'] += duration_stats['total_points']
                        elif duration_key == '8-16s':
                            medium_poss['count'] += duration_stats['count']
                            medium_poss['total_points'] += duration_stats['total_points']
                        else:  # '>16s'
                            long_poss['count'] += duration_stats['count']
                            long_poss['total_points'] += duration_stats['total_points']

                    games_analyzed += 1

                except Exception as e:
                    continue

            # Calculate overall statistics
            total_possessions = short_poss['count'] + medium_poss['count'] + long_poss['count']
            avg_duration = sum(all_possessions) / len(all_possessions) if all_possessions else 0.0

            # Calculate OER for each duration range
            def calculate_oer(poss_count: int, total_points: int) -> float:
                if poss_count == 0:
                    return 0.0
                return (total_points / poss_count) * 100

            return {
                'total_possessions': total_possessions,
                'avg_duration': round(avg_duration, 2),
                'possessions_by_duration': {
                    '<=8s': {
                        'count': short_poss['count'],
                        'total_points': short_poss['total_points'],
                        'oer': round(calculate_oer(short_poss['count'], short_poss['total_points']), 2)
                    },
                    '8-16s': {
                        'count': medium_poss['count'],
                        'total_points': medium_poss['total_points'],
                        'oer': round(calculate_oer(medium_poss['count'], medium_poss['total_points']), 2)
                    },
                    '>16s': {
                        'count': long_poss['count'],
                        'total_points': long_poss['total_points'],
                        'oer': round(calculate_oer(long_poss['count'], long_poss['total_points']), 2)
                    }
                },
                'games_analyzed': games_analyzed
            }

        except PyMongoError as e:
            return {}

