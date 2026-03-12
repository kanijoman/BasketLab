"""Statistics calculation module for basketball matches.

This module provides the StatsCalculator class which handles all statistical
calculations for basketball matches, including:
- Basic statistics (points, rebounds, assists, etc.)
- Advanced metrics (efficiency ratings, possession-based stats, etc.)
- Comparative statistics with delta calculations between time periods

The calculator uses safe conversion methods to handle missing or invalid data gracefully.
"""

from typing import Dict, Optional
from utils.numeric_utils import safe_int, safe_float


class StatsCalculator:
    """Calculate statistics from basketball match data."""

    @staticmethod
    def normalize_team_data(data: Dict) -> Dict:
        """
        Normalize team data to a common format, supporting both FEB and FBCYL formats.

        FEB format uses: pts, p2m, p2a, p3m, p3a, p1m, p1a, ro, rd, assist, st, to, bs
        FBCYL format uses: score, shotsOfTwoSuccessful, shotsOfTwoAttempted, etc.

        Args:
            data: Raw team data dictionary (FEB or FBCYL format)

        Returns:
            Normalized dictionary with FEB field names
        """
        # If already in FEB format (has 'pts' field), return as-is
        if 'pts' in data:
            return data

        # Convert FBCYL format to FEB format
        normalized = {
            'pts': data.get('score', 0),
            'p2m': data.get('shotsOfTwoSuccessful', 0),
            'p2a': data.get('shotsOfTwoAttempted', 0),
            'p3m': data.get('shotsOfThreeSuccessful', 0),
            'p3a': data.get('shotsOfThreeAttempted', 0),
            'p1m': data.get('shotsOfOneSuccessful', 0),
            'p1a': data.get('shotsOfOneAttempted', 0),
            'ro': data.get('offensiveRebound', 0),
            'rd': data.get('defensiveRebound', 0),
            'assist': data.get('assists', 0),
            'st': data.get('steals', 0),
            'to': data.get('lost', 0),  # FBCYL uses 'lost' for turnovers
            'bs': data.get('block', 0)
        }
        return normalized

    @staticmethod
    def _extract_boxscore_values(team_data: Dict, opponent_data: Dict) -> Dict:
        """Extract and normalize raw integer values from both team boxscore dicts.

        Centralises the repeated ``safe_int(team_data.get(...))`` block used by
        ``calculate_single_match_stats`` and ``calculate_stat_value``.

        Args:
            team_data: Already-normalised team data dict.
            opponent_data: Already-normalised opponent data dict.

        Returns:
            Dict with keys: pts, opp_pts, fg2_made, fg2_att, fg3_made, fg3_att,
            ft_made, ft_att, off_reb, def_reb, assists, steals, turnovers, blocks,
            opp_off_reb, opp_def_reb, opp_fg2_att, opp_fg3_att, opp_ft_att, opp_turnovers.
        """
        return {
            'pts':          safe_int(team_data.get('pts', 0)),
            'opp_pts':      safe_int(opponent_data.get('pts', 0)),
            'fg2_made':     safe_int(team_data.get('p2m', 0)),
            'fg2_att':      safe_int(team_data.get('p2a', 0)),
            'fg3_made':     safe_int(team_data.get('p3m', 0)),
            'fg3_att':      safe_int(team_data.get('p3a', 0)),
            'ft_made':      safe_int(team_data.get('p1m', 0)),
            'ft_att':       safe_int(team_data.get('p1a', 0)),
            'off_reb':      safe_int(team_data.get('ro', 0)),
            'def_reb':      safe_int(team_data.get('rd', 0)),
            'assists':      safe_int(team_data.get('assist', 0)),
            'steals':       safe_int(team_data.get('st', 0)),
            'turnovers':    safe_int(team_data.get('to', 0)),
            'blocks':       safe_int(team_data.get('bs', 0)),
            'opp_off_reb':  safe_int(opponent_data.get('ro', 0)),
            'opp_def_reb':  safe_int(opponent_data.get('rd', 0)),
            'opp_fg2_att':  safe_int(opponent_data.get('p2a', 0)),
            'opp_fg3_att':  safe_int(opponent_data.get('p3a', 0)),
            'opp_ft_att':   safe_int(opponent_data.get('p1a', 0)),
            'opp_turnovers': safe_int(opponent_data.get('to', 0)),
        }

    def calculate_single_match_stats(self, team_data: Dict, opponent_data: Dict) -> Dict:
        """
        Calculate statistics from a single match boxscore.

        Args:
            team_data: Team data (FEB or FBCYL format)
            opponent_data: Opponent data (FEB or FBCYL format)

        Returns:
            Dictionary with calculated statistics
        """
        # Normalize data to support both FEB and FBCYL formats
        team_data = self.normalize_team_data(team_data)
        opponent_data = self.normalize_team_data(opponent_data)

        # Extract raw values from both boxscores
        v = self._extract_boxscore_values(team_data, opponent_data)
        pts       = v['pts'];      opp_pts   = v['opp_pts']
        fg2_made  = v['fg2_made']; fg2_att   = v['fg2_att']
        fg3_made  = v['fg3_made']; fg3_att   = v['fg3_att']
        ft_made   = v['ft_made'];  ft_att    = v['ft_att']
        off_reb   = v['off_reb'];  def_reb   = v['def_reb']
        assists   = v['assists'];  steals    = v['steals']
        turnovers = v['turnovers']; blocks   = v['blocks']
        opp_off_reb  = v['opp_off_reb'];  opp_def_reb = v['opp_def_reb']
        opp_fg2_att  = v['opp_fg2_att'];  opp_fg3_att = v['opp_fg3_att']
        opp_ft_att   = v['opp_ft_att'];   opp_turnovers = v['opp_turnovers']
        tot_reb = off_reb + def_reb

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

    def calculate_stat_value(self, team_data: Dict, opponent_data: Dict, stat_field: str) -> Optional[float]:
        """
        Calculate a specific statistic value for a single match.

        This method extracts and calculates any of the available basketball statistics
        from match data. Useful for temporal analysis and custom reports.

        Args:
            team_data: Team data (FEB or FBCYL format)
            opponent_data: Opponent data (FEB or FBCYL format)
            stat_field: The statistic field to calculate (e.g., 'points_per_game', 'offensive_rating')

        Returns:
            Calculated statistic value, or None if stat_field is invalid

        Examples:
            >>> calculator = StatsCalculator()
            >>> value = calculator.calculate_stat_value(team_data, opp_data, 'offensive_rating')
            >>> print(f"Offensive Rating: {value:.2f}")
        """
        # Normalize data to support both FEB and FBCYL formats
        team_data = self.normalize_team_data(team_data)
        opponent_data = self.normalize_team_data(opponent_data)

        # Extract raw values from both boxscores
        v = self._extract_boxscore_values(team_data, opponent_data)
        pts       = v['pts'];      opp_pts   = v['opp_pts']
        fg2_made  = v['fg2_made']; fg2_att   = v['fg2_att']
        fg3_made  = v['fg3_made']; fg3_att   = v['fg3_att']
        ft_made   = v['ft_made'];  ft_att    = v['ft_att']
        off_reb   = v['off_reb'];  def_reb   = v['def_reb']
        assists   = v['assists'];  steals    = v['steals']
        turnovers = v['turnovers']; blocks   = v['blocks']
        opp_off_reb  = v['opp_off_reb'];  opp_def_reb = v['opp_def_reb']
        opp_fg2_att  = v['opp_fg2_att'];  opp_fg3_att = v['opp_fg3_att']
        opp_ft_att   = v['opp_ft_att'];   opp_turnovers = v['opp_turnovers']

        # Calculate possessions
        poss = fg2_att + fg3_att + (0.45 * ft_att) + turnovers - off_reb
        opp_poss = opp_fg2_att + opp_fg3_att + (0.45 * opp_ft_att) + opp_turnovers - opp_off_reb
        poss = max(poss, 1)  # Avoid division by zero
        opp_poss = max(opp_poss, 1)

        # Calculate requested stat
        if stat_field == "points_per_game":
            return float(pts)
        elif stat_field == "points_allowed_per_game":
            return float(opp_pts)
        elif stat_field == "fg2_percentage":
            return (fg2_made / fg2_att * 100) if fg2_att > 0 else 0
        elif stat_field == "fg3_percentage":
            return (fg3_made / fg3_att * 100) if fg3_att > 0 else 0
        elif stat_field == "ft_percentage":
            return (ft_made / ft_att * 100) if ft_att > 0 else 0
        elif stat_field == "rebounds_per_game":
            return float(off_reb + def_reb)
        elif stat_field == "def_rebounds_per_game":
            return float(def_reb)
        elif stat_field == "off_rebounds_per_game":
            return float(off_reb)
        elif stat_field == "assists_per_game":
            return float(assists)
        elif stat_field == "steals_per_game":
            return float(steals)
        elif stat_field == "turnovers_per_game":
            return float(turnovers)
        elif stat_field == "blocks_per_game":
            return float(blocks)
        elif stat_field == "possessions_per_game":
            return float(poss)
        elif stat_field == "offensive_rating":
            return (pts / poss * 100) if poss > 0 else 0
        elif stat_field == "defensive_rating":
            return (opp_pts / opp_poss * 100) if opp_poss > 0 else 0
        elif stat_field == "net_rating":
            ortg = (pts / poss * 100) if poss > 0 else 0
            drtg = (opp_pts / opp_poss * 100) if opp_poss > 0 else 0
            return ortg - drtg
        elif stat_field == "efg_percentage":
            total_att = fg2_att + fg3_att
            return ((fg2_made + 1.5 * fg3_made) / total_att * 100) if total_att > 0 else 0
        elif stat_field == "true_shooting":
            total_att = fg2_att + fg3_att + 0.44 * ft_att
            return (pts / (2 * total_att) * 100) if total_att > 0 else 0
        elif stat_field == "three_point_rate":
            total_att = fg2_att + fg3_att
            return (fg3_att / total_att * 100) if total_att > 0 else 0
        elif stat_field == "free_throw_rate":
            total_att = fg2_att + fg3_att
            return (ft_att / total_att * 100) if total_att > 0 else 0
        elif stat_field == "assist_fg_rate":
            fg_made = fg2_made + fg3_made
            return (assists / fg_made * 100) if fg_made > 0 else 0
        elif stat_field == "assist_rate":
            return (assists / poss * 100) if poss > 0 else 0
        elif stat_field == "turnover_rate":
            return (turnovers / poss * 100) if poss > 0 else 0
        elif stat_field == "steal_rate":
            return (steals / opp_poss * 100) if opp_poss > 0 else 0
        elif stat_field == "block_rate":
            return (blocks / opp_poss * 100) if opp_poss > 0 else 0
        elif stat_field == "offensive_rebound_rate":
            total_off = off_reb + opp_def_reb
            return (off_reb / total_off * 100) if total_off > 0 else 0
        elif stat_field == "defensive_rebound_rate":
            total_def = def_reb + opp_off_reb
            return (def_reb / total_def * 100) if total_def > 0 else 0

        return None
