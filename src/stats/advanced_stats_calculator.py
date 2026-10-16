"""Calculator for advanced player statistics based on Basketball Reference formulas."""

from typing import Dict, Any, List
import math

from .advanced_ratings import defensive_rating, net_rating, offensive_rating, pie


class AdvancedStatsCalculator:
    """
    Calculate advanced player statistics.

    Formulas based on Basketball Reference:
    - https://www.basketball-reference.com/about/glossary.html
    - https://www.basketball-reference.com/about/ratings.html
    """

    @staticmethod
    def calculate_usage_percentage(player: Dict[str, Any], team_stats: Dict[str, Any]) -> float:
        """
        Calculate Usage Percentage (Usg%).

        Formula: 100 * ((FGA + 0.44 * FTA + TOV) * (Tm MP / 5)) / (MP * (Tm FGA + 0.44 * Tm FTA + Tm TOV))

        Usage percentage is an estimate of the percentage of team plays used by a
        player while he was on the floor.

        Args:
            player: Player statistics dictionary
            team_stats: Team statistics dictionary

        Returns:
            Usage percentage (0-100)
        """
        mp = player.get('total_minutes', 0)  # Already in minutes (pipeline converts seconds→min)
        games = player.get('games_played', 1)
        team_mp = team_stats.get('total_games', 1) * 200  # 5 players * 40 minutes

        if mp == 0 or team_mp == 0:
            return 0.0

        # Player's plays (field goal attempts + free throw attempts + turnovers)
        fga = player.get('total_p2a', 0) + player.get('total_p3a', 0)  # Don't include FTA in FGA
        fta = player.get('total_p1a', 0)
        tov = player.get('total_to', 0)
        player_plays = fga + 0.44 * fta + tov

        # Team's plays
        team_fga = team_stats.get('fg2_attempted', 0) + team_stats.get('fg3_attempted', 0)
        team_fta = team_stats.get('ft_attempted', 0)
        team_tov = team_stats.get('turnovers', 0)
        team_plays = team_fga + 0.44 * team_fta + team_tov

        if team_plays == 0:
            return 0.0

        usg = 100 * (player_plays * (team_mp / 5)) / (mp * team_plays)
        return min(usg, 100.0)

    @staticmethod
    def calculate_true_shooting_percentage(player: Dict[str, Any]) -> float:
        """
        Calculate True Shooting Percentage (TS%).

        Formula: PTS / (2 * (FGA + 0.44 * FTA))

        True shooting percentage is a measure of shooting efficiency that takes
        into account field goals, 3-point field goals, and free throws.

        Args:
            player: Player statistics dictionary

        Returns:
            True shooting percentage (0-100)
        """
        pts = player.get('total_pts', 0)
        fga = player.get('total_p2a', 0) + player.get('total_p3a', 0)  # FGA = 2PA + 3PA (no FTA)
        fta = player.get('total_p1a', 0)

        tsa = fga + 0.44 * fta  # True shooting attempts

        if tsa == 0:
            return 0.0

        return 100 * pts / (2 * tsa)

    @staticmethod
    def calculate_effective_fg_percentage(player: Dict[str, Any]) -> float:
        """
        Calculate Effective Field Goal Percentage (eFG%).

        Formula: (FG2M + 1.5 * FG3M) / FGA

        This statistic adjusts for the fact that a 3-point field goal is worth
        one more point than a 2-point field goal.

        Args:
            player: Player statistics dictionary

        Returns:
            Effective FG percentage (0-100)
        """
        fg2m = player.get('total_p2m', 0)
        fg3m = player.get('total_p3m', 0)
        fga = player.get('total_p2a', 0) + player.get('total_p3a', 0)  # FGA = 2PA + 3PA (no FTA)

        if fga == 0:
            return 0.0

        return 100 * (fg2m + 1.5 * fg3m) / fga

    @staticmethod
    def calculate_ftr(player: Dict[str, Any]) -> float:
        """
        Calculate Free Throw Rate (FTr).

        Formula: FTA / FGA

        Measures how often a player gets to the free throw line.

        Args:
            player: Player statistics dictionary

        Returns:
            Free throw rate (as percentage, e.g., 25.0 for 25%)
        """
        fta = player.get('total_p1a', 0)
        fga = player.get('total_p2a', 0) + player.get('total_p3a', 0)  # FGA = 2PA + 3PA (no FTA)

        if fga == 0:
            return 0.0

        return 100 * fta / fga

    @staticmethod
    def calculate_3pr(player: Dict[str, Any]) -> float:
        """
        Calculate 3-Point Rate (3Pr).

        Formula: 3PA / FGA

        Measures the proportion of a player's field goal attempts that are 3-pointers.

        Args:
            player: Player statistics dictionary

        Returns:
            3-point rate (as percentage, e.g., 35.0 for 35%)
        """
        three_pa = player.get('total_p3a', 0)
        fga = player.get('total_p2a', 0) + player.get('total_p3a', 0)  # FGA = 2PA + 3PA (no FTA)

        if fga == 0:
            return 0.0

        return 100 * three_pa / fga

    @staticmethod
    def calculate_assist_percentage(player: Dict[str, Any], team_stats: Dict[str, Any]) -> float:
        """
        Calculate Assist Percentage (AST%).

        Formula: 100 * AST / (((MP / (Tm MP / 5)) * Tm FG) - FG)

        Assist percentage is an estimate of the percentage of teammate field goals
        a player assisted while he was on the floor.

        Args:
            player: Player statistics dictionary
            team_stats: Team statistics dictionary

        Returns:
            Assist percentage (0-100)
        """
        mp = player.get('total_minutes', 0)  # Already in minutes
        team_games = team_stats.get('total_games', 1)
        team_mp = team_games * 200  # 5 players * 40 minutes per game

        if mp == 0 or team_mp == 0:
            return 0.0

        ast = player.get('total_assist', 0)
        fg = player.get('total_p2m', 0) + player.get('total_p3m', 0)
        team_fg = team_stats.get('fg2_made', 0) + team_stats.get('fg3_made', 0)

        denominator = ((mp / (team_mp / 5)) * team_fg) - fg

        if denominator <= 0:
            return 0.0

        return 100 * ast / denominator

    @staticmethod
    def calculate_turnover_percentage(player: Dict[str, Any]) -> float:
        """
        Calculate Turnover Percentage (TOV%).

        Formula: 100 * TOV / (FGA + 0.44 * FTA + TOV)

        Turnover percentage is an estimate of turnovers per 100 plays.

        Args:
            player: Player statistics dictionary

        Returns:
            Turnover percentage (0-100)
        """
        tov = player.get('total_to', 0)
        # FGA = 2PT attempts + 3PT attempts (NOT free throw attempts)
        fga = player.get('total_p2a', 0) + player.get('total_p3a', 0)
        fta = player.get('total_p1a', 0)

        denominator = fga + 0.44 * fta + tov

        if denominator == 0:
            return 0.0

        return 100 * tov / denominator

    @staticmethod
    def calculate_steal_percentage(player: Dict[str, Any], team_stats: Dict[str, Any],
                                   opp_stats: Dict[str, Any]) -> float:
        """
        Calculate Steal Percentage (STL%).

        Formula: 100 * (STL * (Tm MP / 5)) / (MP * Opp Poss)

        Steal Percentage is an estimate of the percentage of opponent possessions
        that end with a steal by the player while he was on the floor.

        Args:
            player: Player statistics dictionary
            team_stats: Team statistics dictionary
            opp_stats: Opponent statistics dictionary

        Returns:
            Steal percentage (0-100)
        """
        mp = player.get('total_minutes', 0)  # Already in minutes
        team_games = team_stats.get('total_games', 1)
        team_mp = team_games * 200  # 5 players * 40 minutes per game

        if mp == 0 or team_mp == 0:
            return 0.0

        stl = player.get('total_st', 0)

        # Estimate opponent possessions from their stats
        opp_poss_per_game = opp_stats.get('possessions_per_game', 100)
        if opp_poss_per_game == 0:
            opp_poss_per_game = 100
        opp_poss = opp_poss_per_game * team_games

        if opp_poss == 0:
            return 0.0

        return 100 * (stl * (team_mp / 5)) / (mp * opp_poss)

    @staticmethod
    def calculate_block_percentage(player: Dict[str, Any], team_stats: Dict[str, Any],
                                   opp_stats: Dict[str, Any]) -> float:
        """
        Calculate Block Percentage (BLK%).

        Formula: 100 * (BLK * (Tm MP / 5)) / (MP * (Opp FGA - Opp 3PA))

        Block percentage is an estimate of the percentage of opponent two-point
        field goal attempts blocked by the player while he was on the floor.

        Args:
            player: Player statistics dictionary
            team_stats: Team statistics dictionary
            opp_stats: Opponent statistics dictionary

        Returns:
            Block percentage (0-100)
        """
        mp = player.get('total_minutes', 0)  # Already in minutes
        team_games = team_stats.get('total_games', 1)
        team_mp = team_games * 200  # 5 players * 40 minutes per game

        if mp == 0 or team_mp == 0:
            return 0.0

        blk = player.get('total_bs', 0)
        opp_fga = opp_stats.get('fg2_attempted', 0) + opp_stats.get('fg3_attempted', 0)
        opp_3pa = opp_stats.get('fg3_attempted', 0)

        denominator = mp * (opp_fga - opp_3pa)

        if denominator == 0:
            return 0.0

        return 100 * (blk * (team_mp / 5)) / denominator

    @staticmethod
    def calculate_rebound_percentage(player: Dict[str, Any], team_stats: Dict[str, Any],
                                    opp_stats: Dict[str, Any], is_offensive: bool = False) -> float:
        """
        Calculate Rebound Percentage (TRB%, ORB%, or DRB%).

        Formula for TRB%: 100 * (TRB * (Tm MP / 5)) / (MP * (Tm TRB + Opp TRB))
        Formula for ORB%: 100 * (ORB * (Tm MP / 5)) / (MP * (Tm ORB + Opp DRB))
        Formula for DRB%: 100 * (DRB * (Tm MP / 5)) / (MP * (Tm DRB + Opp ORB))

        Args:
            player: Player statistics dictionary
            team_stats: Team statistics dictionary
            opp_stats: Opponent statistics dictionary
            is_offensive: If True, calculate ORB%, otherwise DRB%

        Returns:
            Rebound percentage (0-100)
        """
        mp = player.get('total_minutes', 0)  # Already in minutes
        team_games = team_stats.get('total_games', 1)
        team_mp = team_games * 200  # 5 players * 40 minutes per game

        if mp == 0 or team_mp == 0:
            return 0.0

        if is_offensive:
            reb = player.get('total_ro', 0)
            team_reb = team_stats.get('rebounds_off', 0)
            opp_reb = opp_stats.get('rebounds_def', 0)
        else:
            reb = player.get('total_rd', 0)
            team_reb = team_stats.get('rebounds_def', 0)
            opp_reb = opp_stats.get('rebounds_off', 0)

        denominator = mp * (team_reb + opp_reb)

        if denominator == 0:
            return 0.0

        return 100 * (reb * (team_mp / 5)) / denominator

    @staticmethod
    def calculate_offensive_rating(player: Dict[str, Any], team_stats: Dict[str, Any],
                                   opp_stats: Dict[str, Any]) -> float:
        """Offensive Rating (ORtg), Basketball Reference formula; see ``advanced_ratings.offensive_rating``."""
        return offensive_rating(player, team_stats, opp_stats)

    @staticmethod
    def calculate_defensive_rating(player: Dict[str, Any], team_stats: Dict[str, Any],
                                   opp_stats: Dict[str, Any]) -> float:
        """Defensive Rating (DRtg), Basketball Reference formula; see ``advanced_ratings.defensive_rating``."""
        return defensive_rating(player, team_stats, opp_stats)

    @staticmethod
    def calculate_net_rating(player: Dict[str, Any], team_stats: Dict[str, Any],
                             opp_stats: Dict[str, Any]) -> float:
        """Net Rating = ORtg - DRtg (points differential per 100 possessions)."""
        return net_rating(player, team_stats, opp_stats)

    @staticmethod
    def calculate_pie(player: Dict[str, Any], team_stats: Dict[str, Any],
                      opp_stats: Dict[str, Any]) -> float:
        """Player Impact Estimate (PIE%); see ``advanced_ratings.pie``."""
        return pie(player, team_stats, opp_stats)

    @staticmethod
    def calculate_all_advanced_stats(player: Dict[str, Any], team_stats: Dict[str, Any],
                                     opp_stats: Dict[str, Any]) -> Dict[str, float]:
        """
        Calculate all advanced statistics for a player.

        Args:
            player: Player statistics dictionary
            team_stats: Team statistics dictionary
            opp_stats: Opponent statistics dictionary

        Returns:
            Dictionary with all advanced statistics
        """
        games_played = player.get('games_played', 0)
        total_minutes = player.get('total_minutes', 0)  # Already in minutes
        total_val = player.get('total_val', 0)

        # Basic averages
        minutes_per_game = total_minutes / games_played if games_played > 0 else 0
        points_per_game = player.get('total_pts', 0) / games_played if games_played > 0 else 0
        val_per_game = total_val / games_played if games_played > 0 else 0

        return {
            'mpg': minutes_per_game,
            'ppg': points_per_game,
            'usage': AdvancedStatsCalculator.calculate_usage_percentage(player, team_stats),
            'orating': AdvancedStatsCalculator.calculate_offensive_rating(player, team_stats, opp_stats),
            'drating': AdvancedStatsCalculator.calculate_defensive_rating(player, team_stats, opp_stats),
            'net_rtg': AdvancedStatsCalculator.calculate_net_rating(player, team_stats, opp_stats),
            'ftr': AdvancedStatsCalculator.calculate_ftr(player),
            'three_pr': AdvancedStatsCalculator.calculate_3pr(player),
            'efg': AdvancedStatsCalculator.calculate_effective_fg_percentage(player),
            'ts': AdvancedStatsCalculator.calculate_true_shooting_percentage(player),
            'ast_pct': AdvancedStatsCalculator.calculate_assist_percentage(player, team_stats),
            'tov_pct': AdvancedStatsCalculator.calculate_turnover_percentage(player),
            'stl_pct': AdvancedStatsCalculator.calculate_steal_percentage(player, team_stats, opp_stats),
            'blk_pct': AdvancedStatsCalculator.calculate_block_percentage(player, team_stats, opp_stats),
            'drb_pct': AdvancedStatsCalculator.calculate_rebound_percentage(player, team_stats, opp_stats, is_offensive=False),
            'orb_pct': AdvancedStatsCalculator.calculate_rebound_percentage(player, team_stats, opp_stats, is_offensive=True),
            'val_pg': val_per_game,
            'pie': AdvancedStatsCalculator.calculate_pie(player, team_stats, opp_stats),
        }
