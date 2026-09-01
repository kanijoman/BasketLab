"""TDD tests for rival possession stats.

Verifies that PossessionRepositoryMixin.get_team_possession_stats() returns
rival_pct_fast/medium/slow and rival_oer_fast/medium/slow — i.e., how
opponents attack when playing against a given team.

Red cycle: run BEFORE implementing _accumulate_rival_possession_stats.
Green cycle: run AFTER implementation.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

src_path = Path(__file__).parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from database.repository_possession import PossessionRepositoryMixin


# ---------------------------------------------------------------------------
# Minimal concrete class that inherits the mixin
# ---------------------------------------------------------------------------

class FakeRepo(PossessionRepositoryMixin):
    def __init__(self, connection, games=None):
        self.connection = connection
        self._games = games or []

    def get_games_for_team(self, collection_name, team_id,
                           only_with_playbyplay=False, projection=None):
        return self._games


def _connected():
    m = MagicMock()
    m.is_connected.return_value = True
    return m


def _feb_game(team_id="t1", opp_id="t2"):
    """Minimal FEB-format game doc with HEADER.TEAM needed by rival stat helper."""
    return {
        "HEADER": {"TEAM": [{"id": team_id}, {"id": opp_id}]},
        "PLAYBYPLAY": {"LINES": []},
    }


def _make_poss_stats(total=6, avg_dur=10.0,
                     fast_c=2, fast_pts=4,
                     med_c=2, med_pts=3,
                     slow_c=2, slow_pts=2):
    return {
        "total_possessions": total,
        "avg_duration": avg_dur,
        "possessions_by_duration": {
            "<=8s":  {"count": fast_c, "total_points": fast_pts},
            "8-16s": {"count": med_c,  "total_points": med_pts},
            ">16s":  {"count": slow_c, "total_points": slow_pts},
        },
    }


def _run_with_mocks(repo, own_stats_list, rival_stats_list,
                   collection="FEB_LF2_2025_A", team_id="t1"):
    """Run get_team_possession_stats with mocked PossessionAnalyzer.

    For N games, _accumulate_possession_stats creates N instances (own),
    then _accumulate_rival_possession_stats creates N more instances (rival).
    The mock side_effect cycles through own instances then rival instances.
    """
    def _make_inst(stats):
        inst = MagicMock()
        inst.calculate_possessions.return_value = stats
        return inst

    instances = (
        [_make_inst(s) for s in own_stats_list] +
        [_make_inst(s) for s in rival_stats_list]
    )

    with patch("database.playbyplay_analyzer.PossessionAnalyzer") as MockPA:
        MockPA.side_effect = instances
        result = repo.get_team_possession_stats(collection, team_id)
    return result


# ---------------------------------------------------------------------------
# Rival stats keys are present in the result
# ---------------------------------------------------------------------------

class TestRivalStatsKeysPresent:
    """Result dict must contain all six rival stats fields when PBP data exists."""

    def test_rival_pct_fast_key_exists(self):
        game = _feb_game("t1", "t2")
        repo = FakeRepo(_connected(), games=[game])
        result = _run_with_mocks(repo, [_make_poss_stats()], [_make_poss_stats()])
        assert "rival_pct_fast" in result

    def test_rival_pct_medium_key_exists(self):
        game = _feb_game("t1", "t2")
        repo = FakeRepo(_connected(), games=[game])
        result = _run_with_mocks(repo, [_make_poss_stats()], [_make_poss_stats()])
        assert "rival_pct_medium" in result

    def test_rival_pct_slow_key_exists(self):
        game = _feb_game("t1", "t2")
        repo = FakeRepo(_connected(), games=[game])
        result = _run_with_mocks(repo, [_make_poss_stats()], [_make_poss_stats()])
        assert "rival_pct_slow" in result

    def test_rival_oer_fast_key_exists(self):
        game = _feb_game("t1", "t2")
        repo = FakeRepo(_connected(), games=[game])
        result = _run_with_mocks(repo, [_make_poss_stats()], [_make_poss_stats()])
        assert "rival_oer_fast" in result

    def test_rival_oer_medium_key_exists(self):
        game = _feb_game("t1", "t2")
        repo = FakeRepo(_connected(), games=[game])
        result = _run_with_mocks(repo, [_make_poss_stats()], [_make_poss_stats()])
        assert "rival_oer_medium" in result

    def test_rival_oer_slow_key_exists(self):
        game = _feb_game("t1", "t2")
        repo = FakeRepo(_connected(), games=[game])
        result = _run_with_mocks(repo, [_make_poss_stats()], [_make_poss_stats()])
        assert "rival_oer_slow" in result


# ---------------------------------------------------------------------------
# Rival pct values
# ---------------------------------------------------------------------------

class TestRivalPctValues:
    def test_rival_pct_values_sum_to_100(self):
        rival_stats = _make_poss_stats(
            total=10, fast_c=3, fast_pts=6, med_c=4, med_pts=7, slow_c=3, slow_pts=4
        )
        game = _feb_game("t1", "t2")
        repo = FakeRepo(_connected(), games=[game])
        result = _run_with_mocks(repo, [_make_poss_stats()], [rival_stats])
        total_pct = (result["rival_pct_fast"] or 0) + \
                    (result["rival_pct_medium"] or 0) + \
                    (result["rival_pct_slow"] or 0)
        assert pytest.approx(total_pct, abs=0.2) == 100.0

    def test_rival_pct_fast_matches_proportion(self):
        # 3 fast out of 10 total = 30%
        rival_stats = _make_poss_stats(
            total=10, fast_c=3, fast_pts=6, med_c=4, med_pts=7, slow_c=3, slow_pts=4
        )
        game = _feb_game("t1", "t2")
        repo = FakeRepo(_connected(), games=[game])
        result = _run_with_mocks(repo, [_make_poss_stats()], [rival_stats])
        assert pytest.approx(result["rival_pct_fast"], abs=0.2) == 30.0

    def test_rival_pct_values_not_own_stats(self):
        own_stats = _make_poss_stats(fast_c=1, med_c=1, slow_c=8)   # mostly slow own
        rival_stats = _make_poss_stats(fast_c=8, med_c=1, slow_c=1)  # mostly fast rival
        game = _feb_game("t1", "t2")
        repo = FakeRepo(_connected(), games=[game])
        result = _run_with_mocks(repo, [own_stats], [rival_stats])
        # Rival pct_fast should reflect rival_stats (8/10=80%), not own (1/10=10%)
        assert (result["rival_pct_fast"] or 0) > 70.0


# ---------------------------------------------------------------------------
# Rival OER formula
# ---------------------------------------------------------------------------

class TestRivalOerFormula:
    def test_rival_oer_fast_formula(self):
        # 4 fast possessions, 8 points → OER = (8/4)*100 = 200
        rival_stats = _make_poss_stats(
            total=4, fast_c=4, fast_pts=8, med_c=0, med_pts=0, slow_c=0, slow_pts=0
        )
        game = _feb_game("t1", "t2")
        repo = FakeRepo(_connected(), games=[game])
        result = _run_with_mocks(repo, [_make_poss_stats()], [rival_stats])
        assert pytest.approx(result["rival_oer_fast"]) == 200.0

    def test_rival_oer_zero_when_no_possessions_in_bucket(self):
        # Only slow possessions → fast OER should be 0 (no data)
        rival_stats = _make_poss_stats(
            total=5, fast_c=0, fast_pts=0, med_c=0, med_pts=0, slow_c=5, slow_pts=8
        )
        game = _feb_game("t1", "t2")
        repo = FakeRepo(_connected(), games=[game])
        result = _run_with_mocks(repo, [_make_poss_stats()], [rival_stats])
        assert result["rival_oer_fast"] == 0.0 or result["rival_oer_fast"] is None

    def test_rival_oer_aggregated_across_games(self):
        # 2 games: each with 2 fast possessions scoring 4 points
        # Combined: 4 fast possessions, 8 points → OER = 200
        rival_g1 = _make_poss_stats(fast_c=2, fast_pts=4, med_c=0, med_pts=0, slow_c=0, slow_pts=0, total=2)
        rival_g2 = _make_poss_stats(fast_c=2, fast_pts=4, med_c=0, med_pts=0, slow_c=0, slow_pts=0, total=2)
        game1 = _feb_game("t1", "t2")
        game2 = _feb_game("t1", "t2")
        own_g = _make_poss_stats()
        repo = FakeRepo(_connected(), games=[game1, game2])
        result = _run_with_mocks(repo, [own_g, own_g], [rival_g1, rival_g2])
        assert pytest.approx(result["rival_oer_fast"]) == 200.0


# ---------------------------------------------------------------------------
# No PBP games → rival stats are None/zero
# ---------------------------------------------------------------------------

class TestRivalStatsNoPbp:
    def test_rival_pct_fast_none_when_no_games(self):
        repo = FakeRepo(_connected(), games=[])
        result = repo.get_team_possession_stats("FEB_LF2_2025_A", "t1")
        # When no games, result comes from _empty_possession_result
        assert result.get("rival_pct_fast") is None

    def test_rival_oer_fast_none_when_no_games(self):
        repo = FakeRepo(_connected(), games=[])
        result = repo.get_team_possession_stats("FEB_LF2_2025_A", "t1")
        assert result.get("rival_oer_fast") is None


# ---------------------------------------------------------------------------
# Opponent ID detection (FEB)
# ---------------------------------------------------------------------------

class TestOpponentIdDetection:
    def test_opponent_is_other_header_team(self):
        """Rival stats must reflect the OTHER team (t2), not t1."""
        own_stats  = _make_poss_stats(fast_c=1, fast_pts=1, med_c=0, med_pts=0, slow_c=0, slow_pts=0, total=1)
        rival_stats = _make_poss_stats(fast_c=5, fast_pts=10, med_c=0, med_pts=0, slow_c=0, slow_pts=0, total=5)
        game = _feb_game("t1", "t2")
        repo = FakeRepo(_connected(), games=[game])
        result = _run_with_mocks(repo, [own_stats], [rival_stats], team_id="t1")
        # rival_pct_fast should be 100% (all 5 rival possessions are fast)
        assert pytest.approx(result["rival_pct_fast"], abs=0.5) == 100.0

    def test_rival_stats_use_correct_opp_id_regression(self):
        """Regression: rival stats must NOT equal own stats when they differ."""
        own_stats   = _make_poss_stats(fast_c=1, med_c=8, slow_c=1, fast_pts=2, med_pts=16, slow_pts=2, total=10)
        rival_stats = _make_poss_stats(fast_c=8, med_c=1, slow_c=1, fast_pts=16, med_pts=2, slow_pts=2, total=10)
        game = _feb_game("t1", "t2")
        repo = FakeRepo(_connected(), games=[game])
        result = _run_with_mocks(repo, [own_stats], [rival_stats], team_id="t1")
        # own pct_fast ≈ 10%, rival pct_fast ≈ 80%
        assert (result.get("rival_pct_fast") or 0) > (result.get("pct_fast") or 0) + 50
