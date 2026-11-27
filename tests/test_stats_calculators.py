"""Tests for StatsCalculator, PlayerStatsCalculator and AdvancedStatsCalculator.

These are pure unit tests — no DB, no Qt required.
Two tests intentionally expose real bugs found during the audit:
  - test_turnover_percentage_correct_formula  (BUG: wrong fga field key)
  - test_offensive_rating_callable_as_static  (BUG: missing @staticmethod)
"""

import unittest

from src.stats.advanced_stats_calculator import AdvancedStatsCalculator


# ---------------------------------------------------------------------------
# Helpers — minimal player/team dicts that match the field key conventions
# ---------------------------------------------------------------------------

def _make_team(pts=80, p2m=20, p2a=35, p3m=8, p3a=20, p1m=12, p1a=16,
               ro=10, rd=25, assist=18, st=7, to=12, bs=3):
    return dict(pts=pts, p2m=p2m, p2a=p2a, p3m=p3m, p3a=p3a,
                p1m=p1m, p1a=p1a, ro=ro, rd=rd, assist=assist,
                st=st, to=to, bs=bs)


def _make_opp(pts=72, p2m=18, p2a=32, p3m=6, p3a=18, p1m=10, p1a=14,
              ro=8, rd=22, assist=15, st=5, to=14, bs=2):
    return dict(pts=pts, p2m=p2m, p2a=p2a, p3m=p3m, p3a=p3a,
                p1m=p1m, p1a=p1a, ro=ro, rd=rd, assist=assist,
                st=st, to=to, bs=bs)


def _make_player_advanced(mp=1200, pts=15, p2m=4, p2a=8, p3m=2, p3a=5,
                           p1m=3, p1a=4, ast=3, ro=1, to=2, st=1, bs=0):
    """Player dict using the total_* key convention in AdvancedStatsCalculator."""
    return {
        "total_minutes": mp,
        "total_pts": pts,
        "total_p2m": p2m, "total_p2a": p2a,
        "total_p3m": p3m, "total_p3a": p3a,
        "total_p1m": p1m, "total_p1a": p1a,
        "total_assist": ast,
        "total_ro": ro,
        "total_to": to,
        "total_st": st,
        "total_bs": bs,
    }


def _make_team_adv(mp=12000, fg2m=200, fg2a=350, fg3m=80, fg3a=200,
                   ftm=120, fta=160, ast=180, ro=100, rd=250, to=120):
    """Team dict used by AdvancedStatsCalculator helper methods."""
    return {
        "total_minutes": mp,
        "total_fg2m": fg2m, "total_fg2a": fg2a,
        "total_fg3m": fg3m, "total_fg3a": fg3a,
        "total_ftm": ftm, "total_fta": fta,
        "total_ast": ast,
        "rebounds_off": ro, "rebounds_def": rd,
        "total_to": to,
    }


# ===========================================================================
# StatsCalculator
# ===========================================================================





# ===========================================================================
# PlayerStatsCalculator
# ===========================================================================



# ===========================================================================
# AdvancedStatsCalculator — general methods
# ===========================================================================

class TestAdvancedStatsCalculatorGeneral(unittest.TestCase):

    def test_calculate_true_shooting_percentage_basic(self):
        """TS% = pts / (2 * (fga + 0.44*fta)), expressed as 0–100."""
        player = _make_player_advanced(pts=20, p2m=4, p2a=8, p3m=2, p3a=5, p1m=4, p1a=5)
        ts = AdvancedStatsCalculator.calculate_true_shooting_percentage(player)
        self.assertGreater(ts, 0.0)
        self.assertLessEqual(ts, 100.0)

    def test_calculate_true_shooting_percentage_zero_attempts(self):
        player = _make_player_advanced(pts=0, p2m=0, p2a=0, p3m=0, p3a=0, p1m=0, p1a=0)
        ts = AdvancedStatsCalculator.calculate_true_shooting_percentage(player)
        self.assertEqual(ts, 0.0)

    def test_calculate_assist_percentage_in_range(self):
        player = _make_player_advanced(ast=5)
        team = _make_team_adv(fg2m=200, fg3m=80)
        ast_pct = AdvancedStatsCalculator.calculate_assist_percentage(player, team)
        self.assertGreaterEqual(ast_pct, 0.0)

    def test_calculate_steal_percentage_in_range(self):
        player = _make_player_advanced(st=2)
        team = _make_team_adv()
        opp = _make_team_adv()
        stl_pct = AdvancedStatsCalculator.calculate_steal_percentage(player, team, opp)
        self.assertGreaterEqual(stl_pct, 0.0)

    def test_calculate_block_percentage_in_range(self):
        player = _make_player_advanced(bs=1)
        team = _make_team_adv()
        opp = _make_team_adv()
        blk_pct = AdvancedStatsCalculator.calculate_block_percentage(player, team, opp)
        self.assertGreaterEqual(blk_pct, 0.0)


# ===========================================================================
# BUG #1 — calculate_turnover_percentage uses wrong field key for FGA
# ===========================================================================

class TestTurnoverPercentageBug(unittest.TestCase):
    """
    BUG: fga = p1a + p2a + p3a (includes free throw attempts in field goal count).
    Correct formula: fga = p2a + p3a only; fta = p1a.

    This test documents the bug: with distinctive values we can detect whether
    p1a leaked into the fga calculation.
    """

    def test_turnover_percentage_correct_formula(self):
        """
        Player: p1a (FTA)=10, p2a=8, p3a=6, tov=4
        Correct: fga=14, fta=10, denominator=14 + 0.44*10 + 4 = 22.4
                 TOV% = 100 * 4 / 22.4 ≈ 17.86
        Buggy:   fga=24, fta=10, denominator=24 + 0.44*10 + 4 = 32.4
                 TOV% = 100 * 4 / 32.4 ≈ 12.35
        """
        player = {
            "total_to": 4,
            "total_p1a": 10,  # free throw attempts
            "total_p2a": 8,   # 2pt attempts
            "total_p3a": 6,   # 3pt attempts
        }
        tov_pct = AdvancedStatsCalculator.calculate_turnover_percentage(player)

        # With the correct formula the answer is ~17.86
        # With the buggy formula it would be ~12.35
        self.assertAlmostEqual(tov_pct, 17.86, delta=0.5,
                               msg="TOV% suggests p1a (FTA) is wrongly counted in FGA")

    def test_turnover_percentage_zero_denominator(self):
        player = {"total_to": 0, "total_p1a": 0, "total_p2a": 0, "total_p3a": 0}
        result = AdvancedStatsCalculator.calculate_turnover_percentage(player)
        self.assertEqual(result, 0.0)


# ===========================================================================
# BUG #2 — calculate_offensive_rating missing @staticmethod
# ===========================================================================

class TestOffensiveRatingStaticMethodBug(unittest.TestCase):
    """
    BUG: calculate_offensive_rating is defined without @staticmethod.
    Calling AdvancedStatsCalculator.calculate_offensive_rating(player, team, opp)
    will pass `player` as `self`, shift all remaining args, and produce TypeError.
    """

    def test_offensive_rating_callable_as_static(self):
        """Must be callable on the class without instantiation."""
        player = _make_player_advanced()
        team = _make_team_adv()
        opp = _make_team_adv()
        try:
            result = AdvancedStatsCalculator.calculate_offensive_rating(player, team, opp)
            self.assertIsInstance(result, (int, float))
        except TypeError as exc:
            self.fail(
                f"calculate_offensive_rating is not a proper @staticmethod — "
                f"got TypeError: {exc}"
            )

    def test_offensive_rating_returns_non_negative(self):
        player = _make_player_advanced()
        team = _make_team_adv()
        opp = _make_team_adv()
        result = AdvancedStatsCalculator.calculate_offensive_rating(player, team, opp)
        self.assertGreaterEqual(result, 0.0)


# ===========================================================================
# REGRESSION — total_minutes double-division bug (BUG fixed: pipeline already
# outputs minutes; dividing again by 60 gave stats ~60× too small)
# ===========================================================================

class TestTotalMinutesAlreadyInMinuteRegression(unittest.TestCase):
    """
    Before the fix, AdvancedStatsCalculator divided total_minutes by 60 again
    even though the MongoDB pipeline had already converted seconds→minutes.
    A player with 600 total minutes (15 seasons × 40 min) would be treated as
    if they had played only 10 minutes, producing near-zero usage/assist/steal/
    block percentages.

    Regression: with total_minutes in minutes, all percentage stats must fall
    within a realistic basketball range (> 1%).
    """

    def _make_usage_team(self, total_games=20):
        return {
            'total_games': total_games,
            'fg2_attempted': 400,
            'fg3_attempted': 200,
            'ft_attempted': 160,
            'turnovers': 120,
        }

    def _make_assist_team(self, total_games=20):
        return {
            'total_games': total_games,
            'fg2_made': 200,
            'fg3_made': 80,
        }

    def _make_pct_team(self, total_games=20):
        return {
            'total_games': total_games,
            'fg2_attempted': 400,
            'fg3_attempted': 200,
            'ft_attempted': 160,
        }

    def test_usage_percentage_not_near_zero_regression(self):
        """
        Bug: total_minutes was divided by 60 inside the calculator even though
        the pipeline already returns minutes.  With the old code and
        total_minutes=600 the denominator would be 600/60=10 min → usage ≈ 0.4%.
        After the fix, 600 min × 20 games → usage ≈ 15-16 %.
        """
        player = {
            'total_minutes': 600,    # 600 minutes over the season (already minutes)
            'games_played': 20,
            'total_p2a': 80,
            'total_p3a': 40,
            'total_p1a': 32,
            'total_to': 40,
        }
        team = self._make_usage_team()
        usg = AdvancedStatsCalculator.calculate_usage_percentage(player, team)
        self.assertGreater(usg, 1.0,
            msg="Usage % is near-zero — total_minutes may still be divided by 60 "
                "even though the pipeline already outputs minutes.")
        self.assertLess(usg, 60.0, msg="Usage % out of realistic range")

    def test_assist_percentage_not_near_zero_regression(self):
        """Same bug: AST% would be inflated when denominator shrank by ×60."""
        player = {
            'total_minutes': 600,
            'total_assist': 90,
            'total_p2m': 60,
            'total_p3m': 20,
        }
        team = self._make_assist_team()
        ast_pct = AdvancedStatsCalculator.calculate_assist_percentage(player, team)
        # If minutes were /60 again → mp=10 → team_mp/5=80 → ratio=10/80=0.125
        # → denominator = 0.125*280 - 80 = 35-80 = -45 → returns 0.0 (wrong)
        # With correct minutes: mp=600 → ratio=600/800=0.75 → denom=0.75*280-80=210-80=130
        # → ast_pct = 100*90/130 ≈ 69% (can be high for a playmaker — just check non-zero)
        self.assertGreater(ast_pct, 0.0,
            msg="AST% returned 0 — likely denominator went negative due to double /60.")

    def test_steal_percentage_not_near_zero_regression(self):
        """STL% must be non-negligible for a player with real steal volume."""
        player = {'total_minutes': 600, 'total_st': 30}
        team = {'total_games': 20}
        opp = {
            'total_games': 20,
            'fg2_attempted': 400,
            'fg3_attempted': 200,
            'ft_attempted': 160,
        }
        stl_pct = AdvancedStatsCalculator.calculate_steal_percentage(player, team, opp)
        self.assertGreater(stl_pct, 0.1,
            msg="STL% is near-zero — total_minutes may still be divided extra /60.")

    def test_block_percentage_not_near_zero_regression(self):
        """BLK% must be non-negligible for a shot-blocker."""
        player = {'total_minutes': 600, 'total_bs': 20}
        team = {'total_games': 20}
        opp = {
            'total_games': 20,
            'fg2_attempted': 400,
            'fg3_attempted': 200,
        }
        blk_pct = AdvancedStatsCalculator.calculate_block_percentage(player, team, opp)
        self.assertGreater(blk_pct, 0.1,
            msg="BLK% is near-zero — total_minutes may still be divided extra /60.")

    def test_offensive_rating_not_returning_default_for_valid_input_regression(self):
        """
        ORtg must NOT return the fallback 100.0 when valid player and team data
        are provided — that would indicate a bug (e.g., zero mp from /60 giving
        an early return before the real formula runs).

        Note: ORtg can be negative with certain stat distributions; we only check
        it escapes the 100.0 sentinel/default value.
        """
        player = {
            'total_minutes': 600,
            'games_played': 20,
            'total_pts': 300,
            'total_p2m': 60, 'total_p2a': 120,
            'total_p3m': 20, 'total_p3a': 60,
            'total_p1m': 60, 'total_p1a': 80,
            'total_ro': 20, 'total_assist': 40, 'total_to': 40,
        }
        team = {
            'total_games': 20,
            'points_scored': 1600,
            'fg2_made': 200, 'fg2_attempted': 400,
            'fg3_made': 80,  'fg3_attempted': 200,
            'ft_made': 120,  'ft_attempted': 160,
            'rebounds_off': 80, 'rebounds_def': 220,
            'assists': 200, 'turnovers': 120,
        }
        opp = {
            'total_games': 20,
            'total_rebounds': 260,   # opp_trb used to compute opp_drb
            'rebounds_off': 60,
            'rebounds_def': 200,
        }
        ortg = AdvancedStatsCalculator.calculate_offensive_rating(player, team, opp)
        self.assertNotAlmostEqual(ortg, 100.0, delta=0.01,
            msg="ORtg returned sentinel 100.0 — likely mp==0 due to double /60.")


if __name__ == "__main__":
    unittest.main()
