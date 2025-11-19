"""Statistics calculation module for basketball matches.

This module provides the StatsCalculator class which handles all statistical
calculations for basketball matches, including:
- Basic statistics (points, rebounds, assists, etc.)
- Advanced metrics (efficiency ratings, possession-based stats, etc.)
- Comparative statistics with delta calculations between time periods

The calculator uses safe conversion methods to handle missing or invalid data gracefully.
"""

from typing import Dict
from .numeric_utils import safe_int, safe_float


class StatsCalculator:
    """Calculate statistics from basketball match data."""

    def calculate_single_match_stats(self, team_data: Dict, opponent_data: Dict) -> Dict:
        """
        Calculate statistics from a single match boxscore.

        Args:
            team_data: BOXSCORE.TEAM.TOTAL data for the team
            opponent_data: BOXSCORE.TEAM.TOTAL data for the opponent

        Returns:
            Dictionary with calculated statistics
        """
        # Extract basic stats
        pts = safe_int(team_data.get("pts", 0))
        opp_pts = safe_int(opponent_data.get("pts", 0))

        fg2_made = safe_int(team_data.get("p2m", 0))
        fg2_att = safe_int(team_data.get("p2a", 0))
        fg3_made = safe_int(team_data.get("p3m", 0))
        fg3_att = safe_int(team_data.get("p3a", 0))
        ft_made = safe_int(team_data.get("p1m", 0))
        ft_att = safe_int(team_data.get("p1a", 0))

        off_reb = safe_int(team_data.get("ro", 0))
        def_reb = safe_int(team_data.get("rd", 0))
        tot_reb = off_reb + def_reb

        assists = safe_int(team_data.get("assist", 0))
        steals = safe_int(team_data.get("st", 0))
        turnovers = safe_int(team_data.get("to", 0))
        blocks = safe_int(team_data.get("bs", 0))

        # Opponent stats for possessions
        opp_off_reb = safe_int(opponent_data.get("ro", 0))
        opp_fg2_att = safe_int(opponent_data.get("p2a", 0))
        opp_fg3_att = safe_int(opponent_data.get("p3a", 0))
        opp_ft_att = safe_int(opponent_data.get("p1a", 0))
        opp_turnovers = safe_int(opponent_data.get("to", 0))
        opp_def_reb = safe_int(opponent_data.get("rd", 0))

        # Calculate possessions
        poss = fg2_att + fg3_att + (0.45 * ft_att) + turnovers - off_reb
        opp_poss = opp_fg2_att + opp_fg3_att + (0.45 * opp_ft_att) + opp_turnovers - opp_off_reb

        # Calculate percentages
        fg2_pct = (fg2_made / fg2_att * 100) if fg2_att > 0 else 0
        fg3_pct = (fg3_made / fg3_att * 100) if fg3_att > 0 else 0
        ft_pct = (ft_made / ft_att * 100) if ft_att > 0 else 0
        fg_pct = ((fg2_made + fg3_made) / (fg2_att + fg3_att) * 100) if (fg2_att + fg3_att) > 0 else 0

        # eFG%
        efg_pct = ((fg2_made + 1.5 * fg3_made) / (fg2_att + fg3_att) * 100) if (fg2_att + fg3_att) > 0 else 0

        # True Shooting %
        ts_pct = (pts / (2 * (fg2_att + fg3_att + 0.44 * ft_att)) * 100) if (fg2_att + fg3_att + ft_att) > 0 else 0

        # Three Point Rate (3PA / FGA)
        three_pt_rate = (fg3_att / (fg2_att + fg3_att) * 100) if (fg2_att + fg3_att) > 0 else 0

        # Free Throw Rate (FTA / FGA)
        ft_rate = (ft_att / (fg2_att + fg3_att) * 100) if (fg2_att + fg3_att) > 0 else 0

        # Assist/FG Rate (AST / FGM)
        assist_fg_rate = (assists / (fg2_made + fg3_made) * 100) if (fg2_made + fg3_made) > 0 else 0

        # Assist Rate (AST / Possessions)
        assist_rate = (assists / poss * 100) if poss > 0 else 0

        # Turnover Rate
        turnover_rate = (turnovers / poss * 100) if poss > 0 else 0

        # Steal Rate
        steal_rate = (steals / opp_poss * 100) if opp_poss > 0 else 0

        # Block Rate
        block_rate = (blocks / opp_poss * 100) if opp_poss > 0 else 0

        # Offensive Rebound Rate
        oreb_rate = (off_reb / (off_reb + opp_def_reb) * 100) if (off_reb + opp_def_reb) > 0 else 0

        # Defensive Rebound Rate
        dreb_rate = (def_reb / (def_reb + opp_off_reb) * 100) if (def_reb + opp_off_reb) > 0 else 0

        # Turnover % (legacy name for compatibility)
        tov_pct = turnover_rate

        # Offensive Rebound % (legacy name for compatibility)
        oreb_pct = oreb_rate

        # Offensive Rating
        ortg = (pts / poss * 100) if poss > 0 else 0

        # Defensive Rating
        drtg = (opp_pts / opp_poss * 100) if opp_poss > 0 else 0

        # Net Rating
        net_rtg = ortg - drtg

        return {
            "team_name": team_data.get("name", ""),
            "total_games": 1,
            "points_per_game": pts,
            "points_against_per_game": opp_pts,
            "fg2_percentage": fg2_pct,
            "fg3_percentage": fg3_pct,
            "ft_percentage": ft_pct,
            "fg_percentage": fg_pct,
            "efg_percentage": efg_pct,
            "true_shooting": ts_pct,
            "three_point_rate": three_pt_rate,
            "free_throw_rate": ft_rate,
            "assist_fg_rate": assist_fg_rate,
            "assist_rate": assist_rate,
            "turnover_rate": turnover_rate,
            "steal_rate": steal_rate,
            "block_rate": block_rate,
            "offensive_rebound_rate": oreb_rate,
            "defensive_rebound_rate": dreb_rate,
            "possessions_per_game": poss,
            "rebounds_per_game": tot_reb,
            "offensive_rebounds_per_game": off_reb,
            "defensive_rebounds_per_game": def_reb,
            "assists_per_game": assists,
            "steals_per_game": steals,
            "turnovers_per_game": turnovers,
            "blocks_per_game": blocks,
            "turnover_percentage": tov_pct,
            "oreb_percentage": oreb_pct,
            "offensive_rating": ortg,
            "defensive_rating": drtg,
            "net_rating": net_rtg,
            # Raw totals for display
            "fg2_made": fg2_made,
            "fg2_attempts": fg2_att,
            "fg3_made": fg3_made,
            "fg3_attempts": fg3_att,
            "ft_made": ft_made,
            "ft_attempts": ft_att,
            # Additional required fields
            "points_scored": pts,
            "points_received": opp_pts,
            "total_rebounds": tot_reb,
            "rebounds_def": def_reb,
            "rebounds_off": off_reb,
            "assists": assists,
            "steals": steals,
            "turnovers": turnovers,
            "blocks": blocks
        }

    def create_comparative_stat(self, monthly: Dict, rest: Dict) -> Dict:
        """
        Create a comparative statistic dictionary combining monthly and rest data.

        Args:
            monthly: Statistics for the monthly period
            rest: Statistics for the rest of the season

        Returns:
            Dictionary with structure:
            {
                "_id": ...,
                "team_name": ...,
                "monthly": {...},
                "rest": {...},
                "deltas": {...}
            }
        """
        comp_stat = {
            "_id": monthly.get("_id"),
            "team_name": monthly.get("team_name", ""),
            "monthly": monthly,
            "rest": rest,
            "deltas": {}
        }

        # Define numeric fields to calculate deltas for
        numeric_fields = [
            "total_games", "points_scored", "points_received", "points_per_game", "points_against_per_game",
            "fg2_percentage", "fg3_percentage", "ft_percentage", "total_rebounds", "rebounds_def", "rebounds_off",
            "assists", "assists_per_game", "steals", "steals_per_game", "turnovers", "turnovers_per_game",
            "blocks", "blocks_per_game",
            "possessions_per_game", "offensive_rating", "defensive_rating", "net_rating",
            "efg_percentage", "turnover_rate", "offensive_rebound_rate", "free_throw_rate", "three_point_rate",
            "true_shooting", "assist_fg_rate", "assist_rate", "steal_rate", "block_rate",
            "defensive_rebound_rate", "games_home", "games_away"
        ]

        # Calculate deltas with safe value extraction
        for key in numeric_fields:
            monthly_value = safe_float(monthly.get(key, 0))
            rest_value = safe_float(rest.get(key, 0))

            if rest_value != 0:
                delta = ((monthly_value - rest_value) / abs(rest_value)) * 100
                comp_stat["deltas"][key] = delta
            else:
                comp_stat["deltas"][key] = 0

        return comp_stat
