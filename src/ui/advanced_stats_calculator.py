"""Calculator for advanced player statistics based on Basketball Reference formulas."""

from typing import Dict, Any, List
import math


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
        mp = player.get('total_minutes', 0) / 60  # Convert seconds to minutes
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

        return 100 * (player_plays * (team_mp / 5)) / (mp * team_plays)

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
            Free throw rate
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
            3-point rate
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
        mp = player.get('total_minutes', 0) / 60
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
        fga = player.get('total_p1a', 0) + player.get('total_p2a', 0) + player.get('total_p3a', 0)
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
        mp = player.get('total_minutes', 0) / 60
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
        mp = player.get('total_minutes', 0) / 60
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
        mp = player.get('total_minutes', 0) / 60
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


    def calculate_offensive_rating(player: Dict[str, Any], team_stats: Dict[str, Any],
                                   opp_stats: Dict[str, Any]) -> float:
        """
        Calculate Offensive Rating (ORtg) using Basketball Reference formula.

        Individual offensive rating is the number of points produced by a player
        per hundred total individual possessions.

        Formula: ORtg = 100 * (Points Produced / Total Possessions)

        Args:
            player: Player statistics dictionary
            team_stats: Team statistics dictionary
            opp_stats: Opponent statistics dictionary

        Returns:
            Offensive rating (points per 100 possessions)
        """
        # Player stats
        mp = player.get('total_minutes', 0) / 60  # Convert to minutes
        pts = player.get('total_pts', 0)
        fgm = player.get('total_p2m', 0) + player.get('total_p3m', 0)
        fga = player.get('total_p2a', 0) + player.get('total_p3a', 0)
        three_pm = player.get('total_p3m', 0)
        ftm = player.get('total_p1m', 0)
        fta = player.get('total_p1a', 0)
        orb = player.get('total_ro', 0)
        ast = player.get('total_assist', 0)
        tov = player.get('total_to', 0)

        # Team stats
        team_games = team_stats.get('total_games', 1)
        team_mp = team_games * 200  # 5 players * 40 minutes
        team_pts = team_stats.get('points_scored', 0)
        team_fgm = team_stats.get('fg2_made', 0) + team_stats.get('fg3_made', 0)
        team_fga = team_stats.get('fg2_attempted', 0) + team_stats.get('fg3_attempted', 0)
        team_three_pm = team_stats.get('fg3_made', 0)
        team_ftm = team_stats.get('ft_made', 0)
        team_fta = team_stats.get('ft_attempted', 0)
        team_orb = team_stats.get('rebounds_off', 0)
        team_ast = team_stats.get('assists', 0)
        team_tov = team_stats.get('turnovers', 0)

        # Opponent stats
        opp_trb = opp_stats.get('total_rebounds', 0)
        opp_orb = opp_stats.get('rebounds_off', 0)
        opp_drb = opp_trb - opp_orb

        if mp == 0 or team_mp == 0 or team_fta == 0 or team_fga == 0:
            return 100.0

        # Calculate qAST (assist quotient)
        term1 = (mp / (team_mp / 5)) * (1.14 * ((team_ast - ast) / team_fgm)) if team_fgm > 0 else 0
        term2_num = (team_ast / team_mp) * mp * 5 - ast
        term2_den = (team_fgm / team_mp) * mp * 5 - fgm
        term2 = (term2_num / term2_den * (1 - (mp / (team_mp / 5)))) if term2_den != 0 else 0
        qAST = term1 + term2

        # Calculate Team_Scoring_Poss
        team_scoring_poss = team_fgm + (1 - (1 - (team_ftm / team_fta)) ** 2) * team_fta * 0.4

        # Calculate Team_ORB%
        team_orb_pct = team_orb / (team_orb + opp_drb) if (team_orb + opp_drb) > 0 else 0

        # Calculate Team_Play%
        team_play_pct = team_scoring_poss / (team_fga + team_fta * 0.4 + team_tov) if (team_fga + team_fta * 0.4 + team_tov) > 0 else 0

        # Calculate Team_ORB_Weight
        team_orb_weight = ((1 - team_orb_pct) * team_play_pct) / ((1 - team_orb_pct) * team_play_pct + team_orb_pct * (1 - team_play_pct)) if ((1 - team_orb_pct) * team_play_pct + team_orb_pct * (1 - team_play_pct)) > 0 else 0

        # Calculate FG_Part
        fg_part = fgm * (1 - 0.5 * ((pts - ftm) / (2 * fga)) * qAST) if fga > 0 else 0

        # Calculate AST_Part
        ast_part = 0.5 * (((team_pts - team_ftm) - (pts - ftm)) / (2 * (team_fga - fga))) * ast if (team_fga - fga) > 0 else 0

        # Calculate FT_Part
        ft_part = (1 - (1 - (ftm / fta)) ** 2) * 0.4 * fta if fta > 0 else 0

        # Calculate ORB_Part
        orb_part = orb * team_orb_weight * team_play_pct

        # Calculate Scoring Possessions
        sc_poss = (fg_part + ast_part + ft_part) * (1 - (team_orb / team_scoring_poss) * team_orb_weight * team_play_pct) + orb_part if team_scoring_poss > 0 else 0

        # Calculate Missed FG Possessions
        fgx_poss = (fga - fgm) * (1 - 1.07 * team_orb_pct)

        # Calculate Missed FT Possessions
        ftx_poss = ((1 - (ftm / fta)) ** 2) * 0.4 * fta if fta > 0 else 0

        # Calculate Total Possessions
        tot_poss = sc_poss + fgx_poss + ftx_poss + tov

        if tot_poss == 0:
            return 100.0

        # Calculate Points Produced components
        pprod_fg_part = 2 * (fgm + 0.5 * three_pm) * (1 - 0.5 * ((pts - ftm) / (2 * fga)) * qAST) if fga > 0 else 0

        pprod_ast_part = 2 * ((team_fgm - fgm + 0.5 * (team_three_pm - three_pm)) / (team_fgm - fgm)) * 0.5 * (((team_pts - team_ftm) - (pts - ftm)) / (2 * (team_fga - fga))) * ast if (team_fgm - fgm) > 0 and (team_fga - fga) > 0 else 0

        pprod_orb_part = orb * team_orb_weight * team_play_pct * (team_pts / (team_fgm + (1 - (1 - (team_ftm / team_fta)) ** 2) * 0.4 * team_fta)) if (team_fgm + (1 - (1 - (team_ftm / team_fta)) ** 2) * 0.4 * team_fta) > 0 else 0

        # Calculate Points Produced
        pprod = (pprod_fg_part + pprod_ast_part + ftm) * (1 - (team_orb / team_scoring_poss) * team_orb_weight * team_play_pct) + pprod_orb_part if team_scoring_poss > 0 else 0

        # Calculate Offensive Rating
        return 100 * (pprod / tot_poss)

    @staticmethod
    def calculate_defensive_rating(player: Dict[str, Any], team_stats: Dict[str, Any],
                                   opp_stats: Dict[str, Any]) -> float:
        """
        Calculate Defensive Rating (DRtg) using Basketball Reference formula.

        Individual Defensive Rating estimates points allowed per 100 possessions
        that the player was on the floor, based on defensive stops.

        Args:
            player: Player statistics dictionary
            team_stats: Team statistics dictionary
            opp_stats: Opponent statistics dictionary

        Returns:
            Defensive rating (points allowed per 100 possessions)
        """
        # Player stats
        mp = player.get('total_minutes', 0) / 60
        stl = player.get('total_st', 0)
        blk = player.get('total_bs', 0)
        drb = player.get('total_rd', 0)
        pf = player.get('total_pf', 0)

        # Team stats
        team_games = team_stats.get('total_games', 1)
        team_mp = team_games * 200  # 5 players * 40 minutes
        team_drb = team_stats.get('rebounds_def', 0)
        team_blk = team_stats.get('blocks', 0)
        team_stl = team_stats.get('steals', 0)
        team_pf = team_stats.get('personal_fouls', 0)

        # Opponent stats
        opp_pts = opp_stats.get('points_scored', 0)
        opp_fgm = opp_stats.get('fg2_made', 0) + opp_stats.get('fg3_made', 0)
        opp_fga = opp_stats.get('fg2_attempted', 0) + opp_stats.get('fg3_attempted', 0)
        opp_ftm = opp_stats.get('ft_made', 0)
        opp_fta = opp_stats.get('ft_attempted', 0)
        opp_orb = opp_stats.get('rebounds_off', 0)
        opp_tov = opp_stats.get('turnovers', 0)
        opp_mp = team_mp  # Opponent plays same total minutes

        if mp == 0 or team_mp == 0 or opp_fga == 0 or opp_fta == 0:
            return 100.0

        # Calculate team possessions
        team_poss = opp_fga + 0.4 * opp_fta - 1.07 * (opp_orb / (opp_orb + team_drb)) * (opp_fga - opp_fgm) + opp_tov if (opp_orb + team_drb) > 0 else 100
        team_poss = team_poss if team_poss > 0 else 100

        # Calculate DOR% (Defensive Opponent Rebound %)
        dor_pct = opp_orb / (opp_orb + team_drb) if (opp_orb + team_drb) > 0 else 0

        # Calculate DFG% (Defensive Field Goal %)
        dfg_pct = opp_fgm / opp_fga if opp_fga > 0 else 0

        # Calculate FMwt (Forced Miss Weight)
        fm_wt_num = dfg_pct * (1 - dor_pct)
        fm_wt_den = dfg_pct * (1 - dor_pct) + (1 - dfg_pct) * dor_pct
        fm_wt = fm_wt_num / fm_wt_den if fm_wt_den > 0 else 0.6

        # Calculate Stops1
        stops1 = stl + blk * fm_wt * (1 - 1.07 * dor_pct) + drb * (1 - fm_wt)

        # Calculate Stops2
        stops2_term1 = ((opp_fga - opp_fgm - team_blk) / team_mp) * fm_wt * (1 - 1.07 * dor_pct)
        stops2_term2 = ((opp_tov - team_stl) / team_mp)
        stops2_term3 = (pf / team_pf) * 0.4 * opp_fta * ((1 - (opp_ftm / opp_fta)) ** 2) if team_pf > 0 and opp_fta > 0 else 0
        stops2 = (stops2_term1 + stops2_term2) * mp + stops2_term3

        # Calculate total Stops
        stops = stops1 + stops2

        # Calculate Stop%
        stop_pct = (stops * opp_mp) / (team_poss * mp) if (team_poss * mp) > 0 else 0

        # Calculate Team Defensive Rating
        team_drtg = 100 * (opp_pts / team_poss)

        # Calculate D_Pts_per_ScPoss
        opp_sc_poss = opp_fgm + (1 - ((1 - (opp_ftm / opp_fta)) ** 2)) * opp_fta * 0.4 if opp_fta > 0 else opp_fgm
        d_pts_per_sc_poss = opp_pts / opp_sc_poss if opp_sc_poss > 0 else 1.0

        # Calculate Individual Defensive Rating
        drtg = team_drtg + 0.2 * (100 * d_pts_per_sc_poss * (1 - stop_pct) - team_drtg)

        return drtg

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
        total_minutes = player.get('total_minutes', 0) / 60  # Convert to minutes
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
            'val_pg': val_per_game
        }
