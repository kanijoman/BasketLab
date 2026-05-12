"""Transformer to convert FBCYL data format to internal boxscore format.

NOTE: Both public methods below (`transform_match_to_boxscore` and
`extract_player_stats_from_moves`) are **intentionally incomplete stubs**.
The rest of the codebase reads FBCYL match data directly from the pre-aggregated
`stats.teams[].shotsOfTwoSuccessful` / `stats.teams[].players[].PTS` etc. fields
in MongoDB documents.  There is no active call site for these transformer methods;
they were prototyped but never wired up.  Do NOT implement them unless the data
pipeline is changed to supply raw `moves` arrays instead of pre-aggregated stats.
"""

from typing import Dict, List, Optional
from collections import defaultdict


class FBCYLTransformer:
    """Transform FBCYL match data (moves format) to internal boxscore format compatible with FEB."""

    @staticmethod
    def transform_match_to_boxscore(match_data: Dict) -> Optional[Dict]:
        """
        Transform FBCYL match data to boxscore format.

        Args:
            match_data: Dictionary with 'uuid', 'moves', and 'stats' keys

        Returns:
            Boxscore dictionary compatible with FEB format, or None if transformation fails
        """
        try:
            moves_data = match_data.get('moves')
            if not moves_data:
                print("[FBCYLTransformer] No moves data found in match")
                return None

            # Extract basic match info
            local_id = moves_data.get('localId')
            visit_id = moves_data.get('visitId')

            # Get final score from last entry in score array
            score_array = moves_data.get('score', [])
            if not score_array:
                print("[FBCYLTransformer] No score data found")
                return None

            final_score = score_array[-1]
            local_score = final_score.get('local', 0)
            visit_score = final_score.get('visit', 0)

            # TODO: Extract team names and player statistics from moves data
            # This requires parsing the 'moves' array to aggregate player stats

            # For now, return a minimal boxscore structure
            boxscore = {
                'local': {
                    'team_id': local_id,
                    'team_name': f"Team_{local_id}",
                    'score': local_score,
                    'players': []
                },
                'visitor': {
                    'team_id': visit_id,
                    'team_name': f"Team_{visit_id}",
                    'score': visit_score,
                    'players': []
                },
                'date': moves_data.get('time'),
                'match_id': moves_data.get('idMatchIntern')
            }

            return boxscore

        except Exception as e:
            print(f"[FBCYLTransformer] Error transforming match data: {e}")
            return None

    @staticmethod
    def extract_player_stats_from_moves(moves: List[Dict]) -> Dict[str, Dict]:
        """
        Extract player statistics by parsing move-by-move data.

        Args:
            moves: List of move dictionaries from FBCYL

        Returns:
            Dictionary mapping player_id to their aggregated stats
        """
        # TODO: Implement move-by-move parsing to calculate:
        # - Points (2PT, 3PT, FT)
        # - Rebounds (offensive, defensive)
        # - Assists
        # - Steals
        # - Blocks
        # - Turnovers
        # - Fouls

        player_stats = defaultdict(lambda: {
            'points': 0,
            'fg2_made': 0,
            'fg2_attempted': 0,
            'fg3_made': 0,
            'fg3_attempted': 0,
            'ft_made': 0,
            'ft_attempted': 0,
            'rebounds_offensive': 0,
            'rebounds_defensive': 0,
            'assists': 0,
            'steals': 0,
            'blocks': 0,
            'turnovers': 0,
            'fouls': 0
        })

        return dict(player_stats)
