"""Rating formulas of the advanced player statistics (Basketball Reference): ORtg, DRtg, net rating and PIE.

Plain functions; ``AdvancedStatsCalculator`` keeps the ``calculate_*`` static methods as thin wrappers.
"""

from typing import Any, Dict


def team_minutes(team_stats: Dict[str, Any]) -> float:
    """Minutes the five players of the team have played: 200 per game (5 x 40) in the season totals, or ``team_minutes`` when a game is still being played (#593)."""
    return team_stats.get('team_minutes') or team_stats.get('total_games', 1) * 200


def offensive_rating(player: Dict[str, Any], team_stats: Dict[str, Any],
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
    mp = player.get('total_minutes', 0)  # Already in minutes
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
    team_mp = team_minutes(team_stats)
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


def defensive_rating(player: Dict[str, Any], team_stats: Dict[str, Any],
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
    mp = player.get('total_minutes', 0)  # Already in minutes
    stl = player.get('total_st', 0)
    blk = player.get('total_bs', 0)
    drb = player.get('total_rd', 0)
    pf = player.get('total_pf', 0)

    # Team stats
    team_games = team_stats.get('total_games', 1)
    team_mp = team_minutes(team_stats)
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


def net_rating(player: Dict[str, Any], team_stats: Dict[str, Any],
                         opp_stats: Dict[str, Any]) -> float:
    """Net Rating = ORtg − DRtg (points differential per 100 possessions)."""
    ortg = offensive_rating(player, team_stats, opp_stats)
    drtg = defensive_rating(player, team_stats, opp_stats)
    # Only meaningful when both ratings are non-default
    if ortg == 100.0 and drtg == 100.0:
        return 0.0
    return ortg - drtg


def pie(player: Dict[str, Any], team_stats: Dict[str, Any],
                  opp_stats: Dict[str, Any]) -> float:
    """
    Player Impact Estimate (PIE%).

    Formula (Basketball Reference):
      PIE = player_impact / game_impact * 100
      where impact = PTS + FGM + FTM - FGA - FTA + DRB + 0.5*ORB + AST + STL + 0.5*BLK - PF - TOV
    """
    # Player season totals
    pts = player.get('total_pts', 0)
    fgm = player.get('total_p2m', 0) + player.get('total_p3m', 0)
    fga = player.get('total_p2a', 0) + player.get('total_p3a', 0)
    ftm = player.get('total_p1m', 0)
    fta = player.get('total_p1a', 0)
    drb = player.get('total_rd', 0)
    orb = player.get('total_ro', 0)
    ast = player.get('total_assist', 0)
    stl = player.get('total_st', 0)
    blk = player.get('total_bs', 0)
    pf = player.get('total_pf', 0)
    tov = player.get('total_to', 0)
    player_impact = pts + fgm + ftm - fga - fta + drb + 0.5 * orb + ast + stl + 0.5 * blk - pf - tov

    def _stats_impact(stats: Dict[str, Any]) -> float:
        t_pts = stats.get('points_scored', 0)
        t_fgm = stats.get('fg2_made', 0) + stats.get('fg3_made', 0)
        t_fga = stats.get('fg2_attempted', 0) + stats.get('fg3_attempted', 0)
        t_ftm = stats.get('ft_made', 0)
        t_fta = stats.get('ft_attempted', 0)
        t_drb = stats.get('rebounds_def', 0)
        t_orb = stats.get('rebounds_off', 0)
        t_ast = stats.get('assists', 0)
        t_stl = stats.get('steals', 0)
        t_blk = stats.get('blocks', 0)
        t_pf = stats.get('personal_fouls', 0)
        t_tov = stats.get('turnovers', 0)
        return t_pts + t_fgm + t_ftm - t_fga - t_fta + t_drb + 0.5 * t_orb + t_ast + t_stl + 0.5 * t_blk - t_pf - t_tov

    game_impact = _stats_impact(team_stats) + _stats_impact(opp_stats)
    if game_impact == 0:
        return 0.0
    return 100.0 * (player_impact / game_impact)
