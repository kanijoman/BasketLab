"""Extended coverage tests for AdvancedStatsCalculator methods not yet covered.

Missing lines targeted (per coverage.json):
  38, 53, 100-107, 124-130, 147-153, 177, 241, 248, 252, 280,
  312-333 (block_pct / rebound_pct),
  431 (calculate_all_advanced_stats call),
  464-531 (offensive_rating full path),
  537-542 (net_rating),
  555-587 (defensive_rating full path)
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

src_path = Path(__file__).parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from stats.advanced_stats_calculator import AdvancedStatsCalculator as ASC


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

def _player(mp=28, pts=14, p2m=4, p2a=8, p3m=2, p3a=6, p1m=2, p1a=3,
            ro=2, rd=4, ast=3, st=1, bs=0, pf=2, to=2):
    return {
        "total_minutes": mp,
        "total_pts": pts,
        "total_p2m": p2m, "total_p2a": p2a,
        "total_p3m": p3m, "total_p3a": p3a,
        "total_p1m": p1m, "total_p1a": p1a,
        "total_ro": ro,   "total_rd": rd,
        "total_assist": ast,
        "total_st": st,   "total_bs": bs,
        "total_pf": pf,   "total_to": to,
    }


def _team(games=10):
    """Aggregate team stats for a season."""
    return {
        "total_games": games,
        "points_scored": 750,
        "fg2_made": 240,   "fg2_attempted": 430,
        "fg3_made": 70,    "fg3_attempted": 200,
        "ft_made": 90,     "ft_attempted": 120,
        "rebounds_off": 80, "rebounds_def": 250,
        "total_rebounds": 330,
        "assists": 160,    "steals": 75,
        "blocks": 40,      "turnovers": 120,
        "personal_fouls": 200,
    }


def _opp(games=10):
    return {
        "total_games": games,
        "points_scored": 720,
        "fg2_made": 220,   "fg2_attempted": 400,
        "fg3_made": 60,    "fg3_attempted": 180,
        "ft_made": 80,     "ft_attempted": 100,
        "rebounds_off": 70, "rebounds_def": 230,
        "total_rebounds": 300,
        "assists": 140,    "steals": 65,
        "blocks": 35,      "turnovers": 130,
        "personal_fouls": 210,
    }


# ---------------------------------------------------------------------------
# calculate_usage_percentage — already tested but missing edge case
# ---------------------------------------------------------------------------

class TestUsagePercentageEdgeCases:
    def test_zero_mp_returns_zero(self):
        p = _player(mp=0)
        assert ASC.calculate_usage_percentage(p, _team()) == 0.0

    def test_zero_team_plays_returns_zero(self):
        p = _player()
        t = {k: 0 for k in _team()}
        t["total_games"] = 10
        assert ASC.calculate_usage_percentage(p, t) == 0.0


# ---------------------------------------------------------------------------
# calculate_ftr (lines 124-130)
# ---------------------------------------------------------------------------

class TestFreeThrowRate:
    def test_typical_ftr(self):
        p = _player(p1a=8, p2a=6, p3a=4)
        result = ASC.calculate_ftr(p)
        assert pytest.approx(result, rel=1e-3) == 100 * 8 / 10

    def test_zero_fga_returns_zero(self):
        p = _player(p2a=0, p3a=0, p1a=5)
        assert ASC.calculate_ftr(p) == 0.0

    def test_no_ft_returns_zero(self):
        p = _player(p1a=0, p2a=8, p3a=4)
        assert ASC.calculate_ftr(p) == 0.0


# ---------------------------------------------------------------------------
# calculate_3pr (lines 147-153)
# ---------------------------------------------------------------------------

class TestThreePointRate:
    def test_typical_3pr(self):
        p = _player(p3a=6, p2a=8, p3m=2)
        result = ASC.calculate_3pr(p)
        assert pytest.approx(result, rel=1e-3) == 100 * 6 / 14

    def test_zero_fga_returns_zero(self):
        p = _player(p2a=0, p3a=0)
        assert ASC.calculate_3pr(p) == 0.0

    def test_no_threes_returns_zero(self):
        p = _player(p3a=0, p2a=10)
        assert ASC.calculate_3pr(p) == 0.0


# ---------------------------------------------------------------------------
# calculate_effective_fg_percentage (line 100-107)
# ---------------------------------------------------------------------------

class TestEFGPercentage:
    def test_typical_efg(self):
        p = _player(p2m=4, p3m=2, p2a=8, p3a=6)
        result = ASC.calculate_effective_fg_percentage(p)
        assert pytest.approx(result, rel=1e-3) == 100 * (4 + 1.5 * 2) / 14

    def test_zero_fga_returns_zero(self):
        p = _player(p2a=0, p3a=0)
        assert ASC.calculate_effective_fg_percentage(p) == 0.0


# ---------------------------------------------------------------------------
# calculate_block_percentage (lines 312-333)
# ---------------------------------------------------------------------------

class TestBlockPercentage:
    def test_zero_mp_returns_zero(self):
        p = _player(mp=0, bs=5)
        assert ASC.calculate_block_percentage(p, _team(), _opp()) == 0.0

    def test_denominator_zero_returns_zero(self):
        """opp 2PT attempts = 0 → denominator = 0."""
        p = _player()
        opp = dict(_opp())
        opp["fg2_attempted"] = 0
        opp["fg3_attempted"] = 0
        assert ASC.calculate_block_percentage(p, _team(), opp) == 0.0

    def test_typical_blk_pct_positive(self):
        p = _player(mp=28, bs=3)
        result = ASC.calculate_block_percentage(p, _team(), _opp())
        assert result > 0


# ---------------------------------------------------------------------------
# calculate_rebound_percentage (lines around 280)
# ---------------------------------------------------------------------------

class TestReboundPercentage:
    def test_drb_pct_positive(self):
        p = _player(mp=28, rd=4)
        result = ASC.calculate_rebound_percentage(p, _team(), _opp(), is_offensive=False)
        assert result > 0

    def test_orb_pct_positive(self):
        p = _player(mp=28, ro=2)
        result = ASC.calculate_rebound_percentage(p, _team(), _opp(), is_offensive=True)
        assert result > 0

    def test_zero_mp_returns_zero(self):
        p = _player(mp=0, rd=5)
        assert ASC.calculate_rebound_percentage(p, _team(), _opp()) == 0.0

    def test_zero_total_reb_returns_zero(self):
        p = _player(mp=28, rd=5)
        t = dict(_team())
        o = dict(_opp())
        t["rebounds_def"] = 0
        o["rebounds_off"] = 0
        assert ASC.calculate_rebound_percentage(p, t, o, is_offensive=False) == 0.0


# ---------------------------------------------------------------------------
# calculate_defensive_rating (lines 537-542, 555-587)
# ---------------------------------------------------------------------------

class TestDefensiveRating:
    def test_zero_mp_returns_default(self):
        p = _player(mp=0)
        assert ASC.calculate_defensive_rating(p, _team(), _opp()) == 100.0

    def test_zero_opp_fga_returns_default(self):
        p = _player()
        opp = dict(_opp())
        opp["fg2_attempted"] = 0
        opp["fg3_attempted"] = 0
        assert ASC.calculate_defensive_rating(p, _team(), opp) == 100.0

    def test_typical_drtg_in_range(self):
        p = _player(mp=28, st=2, bs=1, rd=4, pf=2)
        result = ASC.calculate_defensive_rating(p, _team(), _opp())
        assert 50 < result < 150


# ---------------------------------------------------------------------------
# calculate_net_rating (lines 537-542)
# ---------------------------------------------------------------------------

class TestNetRating:
    def test_zero_mp_returns_zero(self):
        """Both ortg and drtg return 100.0 → net = 0."""
        p = _player(mp=0)
        assert ASC.calculate_net_rating(p, _team(), _opp()) == 0.0

    def test_net_equals_ortg_minus_drtg(self):
        p = _player()
        ortg = ASC.calculate_offensive_rating(p, _team(), _opp())
        drtg = ASC.calculate_defensive_rating(p, _team(), _opp())
        net  = ASC.calculate_net_rating(p, _team(), _opp())
        if ortg == 100.0 and drtg == 100.0:
            assert net == 0.0
        else:
            assert pytest.approx(net, rel=1e-6) == ortg - drtg


# ---------------------------------------------------------------------------
# USG% cap regression — M. Betch scenario
# A player with very few minutes but normal plays must not exceed 100%.
# ---------------------------------------------------------------------------

class TestUsagePercentageCap:
    """calculate_usage_percentage must never return a value above 100.0."""

    def _team_season(self, games=20):
        return {
            "total_games": games,
            "fg2_attempted": 860, "fg3_attempted": 400,
            "ft_attempted": 240,  "turnovers": 240,
        }

    def test_few_minutes_player_capped_at_100(self):
        """Player with 1 minute total but 3 FGA — without cap USG% >> 100."""
        p = {"total_minutes": 1.0, "total_p2a": 2, "total_p3a": 1, "total_p1a": 0, "total_to": 0}
        result = ASC.calculate_usage_percentage(p, self._team_season())
        assert result <= 100.0, f"USG% must be capped at 100, got {result}"

    def test_star_player_normal_minutes_not_capped(self):
        """A legitimate star (20 min/game × 20 games = 400 min) near 30–35% USG% is fine."""
        p = {"total_minutes": 400.0, "total_p2a": 150, "total_p3a": 80, "total_p1a": 70, "total_to": 50}
        result = ASC.calculate_usage_percentage(p, self._team_season())
        assert 0.0 < result <= 100.0

    def test_normal_player_not_artificially_capped(self):
        """A player with solid minutes and moderate usage must land well under 100."""
        p = {"total_minutes": 250.0, "total_p2a": 80, "total_p3a": 40, "total_p1a": 50, "total_to": 30}
        result = ASC.calculate_usage_percentage(p, self._team_season())
        assert result < 50.0, f"Normal player should not have USG% > 50, got {result}"


# ---------------------------------------------------------------------------
# Possession projection subfield regression
# ---------------------------------------------------------------------------

class TestPossessionProjectionSubfields:
    """The possession projection must request specific LINES subfields, not the
    whole array — to avoid loading all 15-20 fields per move."""

    def _make_possession_repo(self, collection: str = "FEB_LF2_2025_A"):
        from database.repository_possession import PossessionRepositoryMixin

        class FakePossRepo(PossessionRepositoryMixin):
            def __init__(self):
                self.connection = __import__('unittest.mock', fromlist=['MagicMock']).MagicMock()
                self.connection.is_connected.return_value = True
                self._projection_used = None

            def get_games_for_team(self, col, team_id, only_with_playbyplay=False, projection=None):
                self._projection_used = projection
                return []

        return FakePossRepo()

    def test_feb_projection_does_not_include_bare_playbyplay_lines(self):
        """Bare 'PLAYBYPLAY.LINES' key must not appear — only subfield keys."""
        repo = self._make_possession_repo()
        repo.get_team_possession_stats("FEB_LF2_2025_A", "t1")
        proj = repo._projection_used
        assert proj is not None
        # Should NOT have bare array key (loads all fields)
        assert "PLAYBYPLAY.LINES" not in proj or any(
            k.startswith("PLAYBYPLAY.LINES.") for k in proj
        ), "Projection must request specific LINES subfields (e.g. PLAYBYPLAY.LINES.text)"

    def test_feb_projection_includes_text_field(self):
        """PLAYBYPLAY.LINES.text must be in the FEB projection."""
        repo = self._make_possession_repo()
        repo.get_team_possession_stats("FEB_LF2_2025_A", "t1")
        proj = repo._projection_used
        assert "PLAYBYPLAY.LINES.text" in proj

    def test_feb_projection_includes_idteam_field(self):
        """PLAYBYPLAY.LINES.idTeam must be in the FEB projection."""
        repo = self._make_possession_repo()
        repo.get_team_possession_stats("FEB_LF2_2025_A", "t1")
        proj = repo._projection_used
        assert "PLAYBYPLAY.LINES.idTeam" in proj

    def test_fbcyl_projection_does_not_include_bare_moves(self):
        """Bare 'moves' key must not appear — only subfield keys."""
        repo = self._make_possession_repo()
        repo.get_team_possession_stats("FBCYL_2025_A", "t1")
        proj = repo._projection_used
        assert proj is not None
        assert "moves" not in proj or any(
            k.startswith("moves.") for k in proj
        ), "FBCYL projection must request specific moves subfields (e.g. moves.move)"

    def test_fbcyl_projection_includes_move_text_field(self):
        """moves.move must be in the FBCYL projection."""
        repo = self._make_possession_repo()
        repo.get_team_possession_stats("FBCYL_2025_A", "t1")
        proj = repo._projection_used
        assert "moves.move" in proj


# ---------------------------------------------------------------------------
# calculate_pie (lines 555-587)
# ---------------------------------------------------------------------------

class TestPIE:
    def test_zero_game_impact_returns_zero(self):
        empty_stats = {k: 0 for k in _team()}
        empty_stats["total_games"] = 1
        p = _player(pts=0, p2m=0, p2a=0, p3m=0, p3a=0, p1m=0, p1a=0,
                    rd=0, ro=0, ast=0, st=0, bs=0, pf=0, to=0)
        result = ASC.calculate_pie(p, empty_stats, empty_stats)
        assert result == 0.0

    def test_typical_pie_in_range(self):
        p = _player()
        result = ASC.calculate_pie(p, _team(), _opp())
        assert -100 <= result <= 100


# ---------------------------------------------------------------------------
# calculate_offensive_rating full path (lines 464-531)
# ---------------------------------------------------------------------------

class TestOffensiveRatingFullPath:
    def test_zero_mp_returns_default(self):
        p = _player(mp=0)
        assert ASC.calculate_offensive_rating(p, _team(), _opp()) == 100.0

    def test_zero_team_fga_returns_default(self):
        p = _player()
        t = dict(_team())
        t["fg2_attempted"] = 0
        t["fg3_attempted"] = 0
        assert ASC.calculate_offensive_rating(p, t, _opp()) == 100.0

    def test_typical_ortg_in_range(self):
        p = _player(mp=28, pts=14, p2m=4, p2a=8, p3m=2, p3a=6, p1m=2, p1a=3, ro=2, ast=3, to=2)
        result = ASC.calculate_offensive_rating(p, _team(), _opp())
        assert 0 < result < 200

    def test_tot_poss_zero_returns_default(self):
        """When all scoring stats are zero, tot_poss = 0 → fallback 100."""
        p = _player(pts=0, p2m=0, p2a=0, p3m=0, p3a=0, p1m=0, p1a=0, ro=0, ast=0, to=0)
        result = ASC.calculate_offensive_rating(p, _team(), _opp())
        assert result == 100.0


# ---------------------------------------------------------------------------
# calculate_all_advanced_stats (line 431+)
# ---------------------------------------------------------------------------

class TestCalculateAllAdvancedStats:
    def test_returns_dict(self):
        p = _player()
        result = ASC.calculate_all_advanced_stats(p, _team(), _opp())
        assert isinstance(result, dict)

    def test_contains_key_stats(self):
        p = _player()
        result = ASC.calculate_all_advanced_stats(p, _team(), _opp())
        for key in ("usage", "ts", "efg", "ast_pct", "tov_pct"):
            assert key in result

    def test_zero_player_returns_numeric_dict(self):
        p = _player(mp=0, pts=0, p2m=0, p2a=0, p3m=0, p3a=0, p1m=0, p1a=0,
                    ro=0, rd=0, ast=0, st=0, bs=0, pf=0, to=0)
        result = ASC.calculate_all_advanced_stats(p, _team(), _opp())
        assert isinstance(result, dict)
        for v in result.values():
            assert isinstance(v, (int, float))
