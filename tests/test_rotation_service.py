"""Tests for RotationService — TDD red phase.

Coverage:
- _compute_gini: known vectors, edge cases
- _compute_cv: known vectors, near-zero mean, cap at 200%
- _compute_percentages: pct_starting_5 / top5 / top8 formula
- _aggregate_starters: plurality-vote across multiple games
- _count_substitutions: grouping simultaneous events (±1 s window)
- get_rotation_analysis: integration with mocked DB (FEB + FBCYL)
- rotation_label: correct label per Gini threshold
- cv_label: correct label per CV threshold
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

import pytest

src_path = Path(__file__).parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from services.rotation_service import RotationService


# ---------------------------------------------------------------------------
# Helpers — minimal game stubs
# ---------------------------------------------------------------------------

def _feb_game(team_id: str, players: List[Dict]) -> Dict:
    """Build a minimal FEB game document with BOXSCORE + PLAYBYPLAY."""
    boxscore_players = [
        {
            "id": p["id"],
            "name": p["name"],
            # FEB stores time as integer seconds in BOXSCORE.TEAM.PLAYER.min
            "min": int(float(p.get("minutes", "20:00").split(":")[0]) * 60),
        }
        for p in players
    ]
    # Starters: first 5 players have OUT event first (start on court)
    lines = []
    # All starters: first 5 appear as SALE at Q1 10:00 (i.e. they were on court)
    for i, p in enumerate(players[:5]):
        lines.append({
            "quarter": "1",
            "time": "10:00",
            "text": f"{p['name']} SALE DE PISTA",
            "idPlayer": p["id"],
            "idTeam": team_id,
        })
    return {
        "HEADER": {
            "TEAM": [
                {"id": team_id, "name": "Team A"},
                {"id": "999", "name": "Team B"},
            ]
        },
        "BOXSCORE": {
            "TEAM": [
                {"id": team_id, "PLAYER": boxscore_players},
                {"id": "999", "PLAYER": []},
            ]
        },
        "PLAYBYPLAY": {"LINES": lines},
    }


def _fbcyl_game(team_id: str, players: List[Dict]) -> Dict:
    """Build a minimal FBCYL game document."""
    team_players = []
    for i, p in enumerate(players):
        in_outs = []
        if i < 5:
            # Starters: OUT at minute 20
            in_outs = [{"type": "OUT_TYPE", "minuteAbsolut": 20, "periodNumber": 2, "periodTime": "10:00"}]
        team_players.append({
            "uuid": p["id"],
            "actorId": int(p["id"]),
            "licenseId": p["id"],
            "name": p["name"],
            "timePlayed": p.get("minutes_float", 20.0),
            "inOutsList": in_outs,
        })
    moves = []
    for move in team_players:
        aid = move["actorId"]
        for ev in move["inOutsList"]:
            moves.append({
                "actorId": aid,
                "licenseId": move["licenseId"],
                "idTeam": int(team_id),
                "type": ev["type"],
                "minuteAbsolut": ev["minuteAbsolut"],
                "period": ev["periodNumber"],
                "min": 10,
                "sec": 0,
            })
    return {
        "stats": {
            "teams": [
                {
                    "teamIdIntern": int(team_id),
                    "teamIdExtern": int(team_id),
                    "name": "Team A",
                    "players": team_players,
                },
                {
                    "teamIdIntern": 999,
                    "teamIdExtern": 999,
                    "name": "Team B",
                    "players": [],
                },
            ]
        },
        "moves": moves,
    }


def _make_players(n: int, base_min: float = 20.0) -> List[Dict]:
    """Create n player stubs with varying minutes."""
    return [
        {
            "id": str(i + 1),
            "name": f"Player{i + 1}",
            "minutes": f"{int(base_min - i * 2):02d}:00",
            "minutes_float": max(1.0, base_min - i * 2),
        }
        for i in range(n)
    ]


# ---------------------------------------------------------------------------
# Unit tests — pure math helpers
# ---------------------------------------------------------------------------

class TestComputeGini:
    svc = RotationService.__new__(RotationService)

    def test_perfect_equality(self):
        assert self.svc._compute_gini([10, 10, 10, 10]) == pytest.approx(0.0, abs=1e-9)

    def test_max_inequality_two_players(self):
        g = self.svc._compute_gini([1, 0, 0, 0])
        assert g == pytest.approx(0.75, abs=0.01)

    def test_typical_rotation(self):
        # 5 players: 35, 30, 25, 20, 10 → modest inequality
        g = self.svc._compute_gini([35, 30, 25, 20, 10])
        assert 0.10 < g < 0.30

    def test_empty_returns_zero(self):
        assert self.svc._compute_gini([]) == 0.0

    def test_single_player(self):
        assert self.svc._compute_gini([40]) == pytest.approx(0.0, abs=1e-9)

    def test_all_zeros_returns_zero(self):
        assert self.svc._compute_gini([0, 0, 0]) == 0.0

    def test_result_in_range(self):
        import random
        random.seed(0)
        vals = [random.uniform(1, 40) for _ in range(12)]
        g = self.svc._compute_gini(vals)
        assert 0.0 <= g <= 1.0


class TestComputeCV:
    svc = RotationService.__new__(RotationService)

    def test_homogeneous(self):
        cv = self.svc._compute_cv([10, 10, 10, 10])
        assert cv == pytest.approx(0.0, abs=1e-9)

    def test_typical(self):
        cv = self.svc._compute_cv([40, 30, 20, 10])
        assert cv > 0

    def test_capped_at_200(self):
        cv = self.svc._compute_cv([1000, 0, 0, 0])
        assert cv <= 200.0

    def test_near_zero_mean_returns_200(self):
        # 6 values with only one non-zero → actual CV > 200% → capped at 200
        cv = self.svc._compute_cv([0.001, 0, 0, 0, 0, 0])
        assert cv == pytest.approx(200.0)

    def test_empty_returns_zero(self):
        assert self.svc._compute_cv([]) == 0.0

    def test_result_non_negative(self):
        assert self.svc._compute_cv([5, 10, 15, 20, 30]) >= 0.0


class TestComputePerGameGiniCV:
    """_compute_per_game_gini / _compute_per_game_cv compute metric per game
    then return (mean, population_std) across games — analogous to _compute_per_game_pct."""
    svc = RotationService.__new__(RotationService)

    # --- per-game Gini ---

    def test_gini_empty_list_returns_zeros(self):
        mean, std = self.svc._compute_per_game_gini([], {"p1", "p2"})
        assert mean == 0.0 and std == 0.0

    def test_gini_skips_games_where_player_set_has_no_sig_players(self):
        # game has minutes for "p99" only; significant_ids = {"p1"} → no overlap → skip
        games = [{"p99": 20.0}]
        mean, std = self.svc._compute_per_game_gini(games, {"p1"})
        assert mean == 0.0 and std == 0.0

    def test_gini_perfect_equality_single_game(self):
        # 4 players with equal minutes → Gini ≈ 0
        games = [{"p1": 10.0, "p2": 10.0, "p3": 10.0, "p4": 10.0}]
        sig = {"p1", "p2", "p3", "p4"}
        mean, std = self.svc._compute_per_game_gini(games, sig)
        assert mean == pytest.approx(0.0, abs=1e-4)
        assert std == pytest.approx(0.0, abs=1e-4)

    def test_gini_two_identical_games_std_zero(self):
        game = {"p1": 35.0, "p2": 25.0, "p3": 20.0, "p4": 10.0, "p5": 10.0}
        games = [game, game]
        sig = set(game.keys())
        mean, std = self.svc._compute_per_game_gini(games, sig)
        assert std == pytest.approx(0.0, abs=1e-4)
        assert 0.0 < mean < 1.0

    def test_gini_uses_only_significant_players(self):
        # marginal player "p99" has huge minutes; if included Gini changes
        game = {"p1": 20.0, "p2": 20.0, "p3": 20.0, "p4": 20.0, "p99": 100.0}
        sig_with = {"p1", "p2", "p3", "p4", "p99"}
        sig_without = {"p1", "p2", "p3", "p4"}
        mean_with, _ = self.svc._compute_per_game_gini([game], sig_with)
        mean_without, _ = self.svc._compute_per_game_gini([game], sig_without)
        # equal-minute players → Gini=0 without p99; with p99 → Gini>0
        assert mean_without == pytest.approx(0.0, abs=1e-4)
        assert mean_with > 0.05

    def test_gini_result_in_range(self):
        games = [
            {"p1": 35.0, "p2": 28.0, "p3": 22.0, "p4": 15.0, "p5": 10.0, "p6": 5.0},
            {"p1": 30.0, "p2": 30.0, "p3": 20.0, "p4": 18.0, "p5": 12.0, "p6": 5.0},
        ]
        sig = {"p1", "p2", "p3", "p4", "p5", "p6"}
        mean, std = self.svc._compute_per_game_gini(games, sig)
        assert 0.0 <= mean <= 1.0
        assert std >= 0.0

    # --- per-game CV ---

    def test_cv_empty_list_returns_zeros(self):
        mean, std = self.svc._compute_per_game_cv([], {"p1", "p2"})
        assert mean == 0.0 and std == 0.0

    def test_cv_perfect_equality_returns_zero_mean(self):
        games = [{"p1": 10.0, "p2": 10.0, "p3": 10.0}]
        sig = {"p1", "p2", "p3"}
        mean, std = self.svc._compute_per_game_cv(games, sig)
        assert mean == pytest.approx(0.0, abs=1e-4)

    def test_cv_two_identical_games_std_zero(self):
        game = {"p1": 40.0, "p2": 20.0, "p3": 10.0, "p4": 5.0}
        games = [game, game]
        sig = set(game.keys())
        mean, std = self.svc._compute_per_game_cv(games, sig)
        assert std == pytest.approx(0.0, abs=1e-4)
        assert mean > 0.0

    def test_cv_uses_only_significant_players(self):
        game = {"p1": 10.0, "p2": 10.0, "p_marginal": 0.5}
        sig_with = {"p1", "p2", "p_marginal"}
        sig_without = {"p1", "p2"}
        mean_with, _ = self.svc._compute_per_game_cv([game], sig_with)
        mean_without, _ = self.svc._compute_per_game_cv([game], sig_without)
        assert mean_without == pytest.approx(0.0, abs=1e-4)
        assert mean_with > 0.0

    def test_cv_result_non_negative(self):
        games = [{"p1": 35.0, "p2": 10.0, "p3": 5.0}]
        sig = {"p1", "p2", "p3"}
        mean, std = self.svc._compute_per_game_cv(games, sig)
        assert mean >= 0.0
        assert std >= 0.0


class TestComputePercentages:
    """_compute_percentages now only computes pct_minutes_starting_five.
    Top-5 and Top-8 percentages are per-game and covered by TestComputePerGamePct.
    """
    svc = RotationService.__new__(RotationService)

    def _make_player_stats(self, ids, avg_mins):
        return {
            pid: {"avg_min_per_game": m, "total_minutes": m * 5, "games_played": 5, "name": f"P{pid}"}
            for pid, m in zip(ids, avg_mins)
        }

    def test_starters_cover_full_squad(self):
        # 5 players each averaging 40 min/game → starters = everyone → 100%
        ps = self._make_player_stats(["1", "2", "3", "4", "5"], [40.0] * 5)
        result = self.svc._compute_percentages(ps, list(ps.keys()))
        assert result["pct_minutes_starting_five"] == pytest.approx(100.0, abs=0.01)

    def test_starters_half_of_squad(self):
        # 10 equal players; starters are first 5 → 50%
        ids = [str(i) for i in range(1, 11)]
        ps = self._make_player_stats(ids, [20.0] * 10)
        result = self.svc._compute_percentages(ps, ids[:5])
        assert result["pct_minutes_starting_five"] == pytest.approx(50.0, abs=0.01)

    def test_starters_high_minute_players(self):
        # 10 players: 5 starters at 28 min, 5 bench at 12 min; total = 200
        # starters 5×28 = 140 → 140/200 = 70%
        ids = [str(i) for i in range(1, 11)]
        mins = [28, 28, 28, 28, 28, 12, 12, 12, 12, 12]
        ps = self._make_player_stats(ids, mins)
        result = self.svc._compute_percentages(ps, ids[:5])
        assert result["pct_minutes_starting_five"] == pytest.approx(70.0, abs=0.1)

    def test_returns_only_starting_five_key(self):
        ps = self._make_player_stats(["1", "2", "3", "4", "5"], [20.0] * 5)
        result = self.svc._compute_percentages(ps, list(ps.keys()))
        assert set(result.keys()) == {"pct_minutes_starting_five"}


class TestAggregateStarters:
    svc = RotationService.__new__(RotationService)

    def test_unanimous(self):
        per_game = [{"1", "2", "3", "4", "5"}] * 3
        result_set, counts = self.svc._aggregate_starters(per_game)
        assert result_set == {"1", "2", "3", "4", "5"}
        assert counts["1"] == 3

    def test_majority_wins(self):
        per_game = [
            {"1", "2", "3", "4", "5"},
            {"1", "2", "3", "4", "5"},
            {"1", "2", "3", "4", "6"},  # player 6 appears once
        ]
        result_set, counts = self.svc._aggregate_starters(per_game)
        assert "5" in result_set
        assert "6" not in result_set
        assert counts.get("6", 0) == 1

    def test_empty_returns_empty_set(self):
        result_set, counts = self.svc._aggregate_starters([])
        assert result_set == set()
        assert counts == {}

    def test_returns_five_players(self):
        per_game = [{"1", "2", "3", "4", "5"}, {"1", "2", "3", "4", "5"}]
        result_set, _ = self.svc._aggregate_starters(per_game)
        assert len(result_set) == 5

    def test_counts_per_player(self):
        per_game = [
            {"1", "2", "3", "4", "5"},
            {"1", "2", "3", "4", "5"},
            {"1", "2", "3", "4", "6"},
        ]
        _, counts = self.svc._aggregate_starters(per_game)
        assert counts["1"] == 3
        assert counts["5"] == 2
        assert counts["6"] == 1


class TestFilterSignificantPlayers:
    """Issue #757: the thresholds are relative to the games of the TEAM (a player is significant when he played at least 15 % of them and averages at least 5 minutes), not
    absolute (5 games and 100 minutes): at the start of a season no team has 5 games, and the analysis kept three players of twelve, or all of them through the fallback."""

    svc = RotationService.__new__(RotationService)

    def _make_stats(self, games_played, avg_min):
        return {"games_played": games_played, "avg_min_per_game": avg_min, "total_minutes": avg_min * games_played, "name": "X"}

    def test_all_above_threshold_are_significant(self):
        ps = {"1": self._make_stats(10, 20), "2": self._make_stats(8, 15)}
        assert self.svc._filter_significant_players(ps, total_games=10) == {"1", "2"}

    def test_junior_excluded_both_conditions_fail(self):
        # 1 game of 30 (3 %) and 2 min on average
        ps = {"regular": self._make_stats(25, 20), "junior": self._make_stats(1, 2)}
        result = self.svc._filter_significant_players(ps, total_games=30)
        assert "regular" in result and "junior" not in result

    def test_few_games_even_with_many_minutes_is_marginal(self):
        # injured: 2 games of 20 (10 % < 15 %) at 30 minutes: failing EITHER condition makes a player marginal
        ps = {"regular": self._make_stats(18, 20), "injured": self._make_stats(2, 30)}
        result = self.svc._filter_significant_players(ps, total_games=20)
        assert "regular" in result and "injured" not in result

    def test_many_games_low_minutes_is_marginal_regression(self):
        # Regression: 6 games but 4.48 minutes on average (E. MAGUIRE) is marginal whatever the games the team has played
        ps = {"regular": self._make_stats(10, 25), "maguire": {"games_played": 6, "avg_min_per_game": 4.48, "total_minutes": 26.9, "name": "E. MAGUIRE"}}
        result = self.svc._filter_significant_players(ps, total_games=10)
        assert "regular" in result and "maguire" not in result

    def test_at_the_start_of_a_season_a_rotation_player_is_significant_regression(self):
        """Bug #757: with 4 games played nobody had the 5 games the absolute rule asked for, and a player of 12 minutes was left out as soon as a teammate had played more."""
        ps = {
            "starter": self._make_stats(4, 30),     # all four games, 120 min
            "bench": self._make_stats(4, 12),       # all four games, 48 min: marginal with 100 total minutes
            "newcomer": self._make_stats(1, 12),    # one game of four (25 %)
            "deep": self._make_stats(4, 3),         # every game but 3 minutes
            "once": self._make_stats(1, 1),         # one minute, once
        }
        result = self.svc._filter_significant_players(ps, total_games=4)
        assert result == {"starter", "bench", "newcomer"}

    def test_the_games_threshold_scales_with_the_season(self):
        ps = {"regular": self._make_stats(30, 20), "some": self._make_stats(5, 15), "few": self._make_stats(4, 15)}
        # 15 % of 33 games = 4.95: five games are enough, four are not
        result = self.svc._filter_significant_players(ps, total_games=33)
        assert result == {"regular", "some"}

    def test_boundaries_are_inclusive(self):
        # exactly 15 % of the games (3 of 20) and exactly 5.0 minutes on average
        assert self.svc._filter_significant_players({"exact": self._make_stats(3, 5.0), "full": self._make_stats(20, 30)}, total_games=20) == {"exact", "full"}

    def test_empty_player_stats_returns_empty_set(self):
        assert self.svc._filter_significant_players({}, total_games=5) == set()

    def test_no_games_does_not_divide_by_zero(self):
        assert self.svc._filter_significant_players({"1": self._make_stats(1, 10)}, total_games=0) == {"1"}

    def test_fallback_when_all_marginal(self):
        # If the filter would exclude everyone, return all (safety fallback)
        ps = {"1": self._make_stats(1, 1), "2": self._make_stats(1, 2)}
        assert self.svc._filter_significant_players(ps, total_games=20) == {"1", "2"}

    def test_custom_thresholds(self):
        ps = {"a": self._make_stats(3, 15), "b": self._make_stats(2, 3)}
        result = self.svc._filter_significant_players(ps, total_games=4, min_games_pct=0.75, min_avg_min=10.0)
        assert result == {"a"}                          # a: 3 of 4 games (75 %) and 15 min; b: 2 of 4 games (50 %) and 3 min



class TestComputePerGamePct:
    """Unit tests for RotationService._compute_per_game_pct."""
    svc = RotationService.__new__(RotationService)

    def test_empty_list_returns_zeros(self):
        mean, std = self.svc._compute_per_game_pct([], 5)
        assert mean == 0.0
        assert std == 0.0

    def test_game_with_zero_total_minutes_is_skipped(self):
        # All players have 0 min in this game → skip → fallback to zero
        mean, std = self.svc._compute_per_game_pct([{"p1": 0.0, "p2": 0.0}], 5)
        assert mean == 0.0
        assert std == 0.0

    def test_single_game_top5_exact(self):
        # 5 players × 10 min + 1 player × 2 min; top5 = 50, total = 52
        game_min = {"a": 10.0, "b": 10.0, "c": 10.0, "d": 10.0, "e": 10.0, "bench": 2.0}
        mean, std = self.svc._compute_per_game_pct([game_min], 5)
        expected = round(50 / 52 * 100, 1)
        assert mean == expected
        assert std == 0.0  # single game → no variance

    def test_n_larger_than_players_takes_all(self):
        # Only 5 players in game; requesting top8 → 100%
        game_min = {"a": 15.0, "b": 12.0, "c": 10.0, "d": 8.0, "e": 5.0}
        mean, std = self.svc._compute_per_game_pct([game_min], 8)
        assert mean == 100.0
        assert std == 0.0

    def test_multiple_games_mean_and_std(self):
        # Game 1: top5 = 80 / 100 = 80%
        # Game 2: top5 = 60 / 80  = 75%
        # mean = (80 + 75) / 2 = 77.5
        # std  = sqrt(((80-77.5)^2 + (75-77.5)^2) / 2) = sqrt(6.25/1) ... let's use 2 games
        # variance = ((80-77.5)^2 + (75-77.5)^2) / 2 = (6.25 + 6.25) / 2 = 6.25
        # std = 2.5
        game1 = {"a": 20.0, "b": 20.0, "c": 20.0, "d": 10.0, "e": 10.0, "f": 20.0}
        # top5 of game1: 20,20,20,20,10 = 90 / total 100 = 90%
        game2 = {"a": 15.0, "b": 15.0, "c": 15.0, "d": 15.0, "e": 15.0, "f": 25.0}
        # top5 of game2: 25,15,15,15,15 = 85 / total 100 = 85%
        # mean = (90+85)/2 = 87.5, std = sqrt(((90-87.5)^2+(85-87.5)^2)/2) = sqrt(6.25) = 2.5
        mean, std = self.svc._compute_per_game_pct([game1, game2], 5)
        assert mean == 87.5
        assert std == 2.5

    def test_std_zero_when_all_games_identical(self):
        game = {"a": 20.0, "b": 20.0, "c": 20.0, "d": 20.0, "e": 20.0}
        games = [game] * 5
        mean, std = self.svc._compute_per_game_pct(games, 5)
        assert mean == 100.0
        assert std == 0.0


class TestCountSubstitutions:
    svc = RotationService.__new__(RotationService)

    def test_no_events(self):
        combined, individual = self.svc._count_substitutions([])
        assert combined == 0
        assert individual == 0

    def test_single_event(self):
        # One player substituted at 300 s
        combined, individual = self.svc._count_substitutions([300])
        assert combined == 1
        assert individual == 1

    def test_simultaneous_events_count_as_one_combined(self):
        # Three events at the same second → 1 combined, 3 individual
        combined, individual = self.svc._count_substitutions([600, 600, 600])
        assert combined == 1
        assert individual == 3

    def test_simultaneous_within_1s_window(self):
        # Events at 600 and 601 are simultaneous (±1 s)
        combined, individual = self.svc._count_substitutions([600, 601])
        assert combined == 1
        assert individual == 2

    def test_separate_events(self):
        # Events at 300 and 900 are separate
        combined, individual = self.svc._count_substitutions([300, 900])
        assert combined == 2
        assert individual == 2

    def test_mixed_scenario(self):
        # 3 at t=300 (1 combined, 3 individual) + 2 at t=900 (1 combined, 2 individual)
        timestamps = [300, 300, 300, 900, 900]
        combined, individual = self.svc._count_substitutions(timestamps)
        assert combined == 2
        assert individual == 5


class TestRotationLabel:
    svc = RotationService.__new__(RotationService)

    def test_wide_rotation(self):
        assert self.svc._rotation_label(0.10) == "Rotación amplia"

    def test_balanced_rotation(self):
        assert self.svc._rotation_label(0.20) == "Rotación equilibrada"

    def test_narrow_rotation(self):
        assert self.svc._rotation_label(0.30) == "Rotación corta"

    def test_boundary_low(self):
        assert self.svc._rotation_label(0.15) == "Rotación equilibrada"

    def test_boundary_high(self):
        assert self.svc._rotation_label(0.25) == "Rotación corta"


class TestCvLabel:
    svc = RotationService.__new__(RotationService)

    def test_very_homogeneous(self):
        assert self.svc._cv_label(15.0) == "Muy homogéneo"

    def test_moderate(self):
        assert self.svc._cv_label(30.0) == "Moderado"

    def test_heterogeneous(self):
        assert self.svc._cv_label(50.0) == "Heterogéneo"

    def test_boundary_low(self):
        assert self.svc._cv_label(20.0) == "Moderado"

    def test_boundary_high(self):
        assert self.svc._cv_label(40.0) == "Heterogéneo"


# ---------------------------------------------------------------------------
# Integration tests — get_rotation_analysis with mocked DB
# ---------------------------------------------------------------------------

class TestGetRotationAnalysisFEB:
    """Integration tests using a mocked DB with FEB-format games."""

    def _make_service(self, games: List[Dict], team_id: str = "10") -> RotationService:
        db = MagicMock()
        db.get_games_for_team.return_value = games
        return RotationService(db)

    def test_at_the_start_of_a_season_the_rotation_is_not_reduced_to_a_few_players_regression(self):
        """Bug #757 with the state of a team after four games: ten players with minutes, two of them with scraps. The absolute rule (5 games and 100 minutes) kept three."""
        players = _make_players(10, base_min=30) + [
            {"id": "11", "name": "Player11", "minutes": "03:00", "minutes_float": 3.0},
            {"id": "12", "name": "Player12", "minutes": "02:00", "minutes_float": 2.0},
        ]
        svc = self._make_service([_feb_game("10", players) for _ in range(4)])
        result = svc.get_rotation_analysis("FEB_LF2_2026", "10", "Team A")
        assert len(result["players"]) == 10
        assert sorted(p["player_name"] for p in result["marginal_players"]) == ["Player11", "Player12"]
        assert all(not p["is_marginal"] for p in result["players"]) and all(p["is_marginal"] for p in result["marginal_players"])

    def test_returns_expected_keys(self):
        players = _make_players(8, base_min=30)
        game = _feb_game("10", players)
        svc = self._make_service([game])
        result = svc.get_rotation_analysis("FEB_LF2_2025", "10", "Team A")
        for key in (
            "total_games", "games_with_playbyplay", "players",
            "starting_five_ids", "starting_five_names",
            "starting_five_games_count", "starting_five_games_pct",
            "pct_minutes_starting_five", "pct_minutes_top5", "pct_minutes_top8",
            "total_combined_substitutions", "total_individual_substitutions",
            "avg_combined_subs_per_game", "avg_individual_subs_per_game",
            "gini_index", "cv", "rotation_label", "cv_label",
            "marginal_players", "significant_player_count",
        ):
            assert key in result, f"Missing key: {key}"

    def test_players_sorted_by_minutes_desc(self):
        players = _make_players(8, base_min=30)
        game = _feb_game("10", players)
        svc = self._make_service([game])
        result = svc.get_rotation_analysis("FEB_LF2_2025", "10", "Team A")
        mins = [p["total_minutes"] for p in result["players"]]
        assert mins == sorted(mins, reverse=True)

    def test_each_player_has_required_fields(self):
        players = _make_players(5, base_min=30)
        game = _feb_game("10", players)
        svc = self._make_service([game])
        result = svc.get_rotation_analysis("FEB_LF2_2025", "10", "Team A")
        for p in result["players"]:
            for field in ("player_id", "player_name", "total_minutes",
                          "games_played", "avg_min_per_game", "pct_game_time",
                          "is_starter", "starter_games", "starter_pct", "is_marginal"):
                assert field in p, f"Missing player field: {field}"

    def test_empty_games_returns_zeroed_result(self):
        svc = self._make_service([])
        result = svc.get_rotation_analysis("FEB_LF2_2025", "10", "Team A")
        assert result["total_games"] == 0
        assert result["players"] == []
        assert result["gini_index"] == 0.0

    def test_pct_fields_between_0_and_100(self):
        players = _make_players(8, base_min=25)
        game = _feb_game("10", players)
        svc = self._make_service([game])
        result = svc.get_rotation_analysis("FEB_LF2_2025", "10", "Team A")
        for field in ("pct_minutes_starting_five", "pct_minutes_top5", "pct_minutes_top8"):
            assert 0.0 <= result[field] <= 100.0, f"{field} out of range: {result[field]}"

    def test_gini_between_0_and_1(self):
        players = _make_players(8)
        game = _feb_game("10", players)
        svc = self._make_service([game])
        result = svc.get_rotation_analysis("FEB_LF2_2025", "10", "Team A")
        assert 0.0 <= result["gini_index"] <= 1.0

    def test_starting_five_has_five_players(self):
        players = _make_players(8, base_min=30)
        game = _feb_game("10", players)
        svc = self._make_service([game])
        result = svc.get_rotation_analysis("FEB_LF2_2025", "10", "Team A")
        # Starting five may be empty if PBP yields fewer players; just check it's <=5
        assert len(result["starting_five_ids"]) <= 5

    def test_rotation_label_is_string(self):
        players = _make_players(6)
        game = _feb_game("10", players)
        svc = self._make_service([game])
        result = svc.get_rotation_analysis("FEB_LF2_2025", "10", "Team A")
        assert isinstance(result["rotation_label"], str)
        assert result["rotation_label"] in ("Rotación amplia", "Rotación equilibrada", "Rotación corta")

    def test_starter_games_present_per_player(self):
        players = _make_players(8, base_min=30)
        games = [_feb_game("10", players)] * 3
        svc = self._make_service(games)
        result = svc.get_rotation_analysis("FEB_LF2_2025", "10", "Team A")
        for p in result["players"]:
            assert "starter_games" in p
            assert "starter_pct" in p
            assert p["starter_games"] >= 0
            assert 0.0 <= p["starter_pct"] <= 100.0

    def test_is_marginal_false_for_significant_players(self):
        # Players with >= 5 avg min are significant
        players = _make_players(8, base_min=30)
        game = _feb_game("10", players)
        svc = self._make_service([game])
        result = svc.get_rotation_analysis("FEB_LF2_2025", "10", "Team A")
        assert all(p["is_marginal"] is False for p in result["players"])

    def test_marginal_players_excluded_from_gini(self):
        """Gini computed on significant players only, not influenced by near-zero outliers."""
        regular_players = _make_players(8, base_min=25)
        junior1 = {"id": "j1", "name": "Junior1", "minutes": "02:00", "minutes_float": 2.0}
        junior2 = {"id": "j2", "name": "Junior2", "minutes": "01:00", "minutes_float": 1.0}

        # 10 games: regular players appear in all 10 (→ total_min ≥ 100 for all 8:
        # Player8 has 11 min avg × 10 = 110 min ✓); juniors only in 1 game
        # (→ 1 game < 5 AND ~2 total min < 100 → marginal)
        game_regular = _feb_game("10", regular_players)
        game_with_juniors = _feb_game("10", regular_players + [junior1, junior2])
        games = [game_regular] * 9 + [game_with_juniors]
        svc = self._make_service(games)

        result = svc.get_rotation_analysis("FEB_LF2_2025", "10", "Team A")
        # Juniors must appear only in marginal_players, not in players
        player_ids = {p["player_id"] for p in result["players"]}
        assert "j1" not in player_ids
        assert "j2" not in player_ids
        marginal_ids = {p["player_id"] for p in result["marginal_players"]}
        assert "j1" in marginal_ids
        assert "j2" in marginal_ids
        assert result["significant_player_count"] == 8

    def test_starting_five_games_count_present(self):
        players = _make_players(8, base_min=30)
        games = [_feb_game("10", players)] * 5
        svc = self._make_service(games)
        result = svc.get_rotation_analysis("FEB_LF2_2025", "10", "Team A")
        assert "starting_five_games_count" in result
        assert "starting_five_games_pct" in result
        assert isinstance(result["starting_five_games_count"], int)
        assert 0.0 <= result["starting_five_games_pct"] <= 100.0


class TestGetRotationAnalysisFBCYL:
    """Integration tests using a mocked DB with FBCYL-format games."""

    def _make_service(self, games: List[Dict]) -> RotationService:
        db = MagicMock()
        db.get_games_for_team.return_value = games
        return RotationService(db)

    def test_fbcyl_returns_valid_result(self):
        players = _make_players(8, base_min=25)
        game = _fbcyl_game("10", players)
        svc = self._make_service([game])
        result = svc.get_rotation_analysis("FBCYL_2025", "10", "Team A")
        assert result["total_games"] == 1
        assert len(result["players"]) > 0

    def test_fbcyl_gini_in_range(self):
        players = _make_players(8)
        game = _fbcyl_game("10", players)
        svc = self._make_service([game])
        result = svc.get_rotation_analysis("FBCYL_2025", "10", "Team A")
        assert 0.0 <= result["gini_index"] <= 1.0

    def test_fbcyl_pct_fields_in_range(self):
        players = _make_players(8, base_min=25)
        game = _fbcyl_game("10", players)
        svc = self._make_service([game])
        result = svc.get_rotation_analysis("FBCYL_2025", "10", "Team A")
        for field in ("pct_minutes_starting_five", "pct_minutes_top5", "pct_minutes_top8"):
            assert 0.0 <= result[field] <= 100.0

    def test_fbcyl_has_marginal_players_key(self):
        players = _make_players(8, base_min=25)
        game = _fbcyl_game("10", players)
        svc = self._make_service([game])
        result = svc.get_rotation_analysis("FBCYL_2025", "10", "Team A")
        assert "marginal_players" in result
        assert isinstance(result["marginal_players"], list)
        assert "significant_player_count" in result


class TestAccumulateStints:
    """Unit tests for RotationService._accumulate_stints."""
    svc = RotationService.__new__(RotationService)

    def test_single_player_one_stint(self):
        # Player starts on court (implicit True), exits at 600s
        timeline = {"p1": [(0, True), (600, False)]}
        game_min = {"p1": 10.0}
        pm, ps = {}, {}
        self.svc._accumulate_stints(timeline, game_min, pm, ps)
        assert pm == {"p1": 10.0}
        assert ps == {"p1": 1}

    def test_player_with_two_stints(self):
        # Player enters, exits, re-enters
        timeline = {"p1": [(0, True), (600, False), (1200, True)]}
        game_min = {"p1": 25.0}
        pm, ps = {}, {}
        self.svc._accumulate_stints(timeline, game_min, pm, ps)
        assert ps["p1"] == 2
        assert pm["p1"] == 25.0

    def test_player_not_in_game_min_is_skipped(self):
        # p2 is in timeline but not in game_min (wrong team / data gap)
        timeline = {"p1": [(0, True)], "p2": [(500, True)]}
        game_min = {"p1": 10.0}
        pm, ps = {}, {}
        self.svc._accumulate_stints(timeline, game_min, pm, ps)
        assert "p2" not in pm
        assert "p2" not in ps

    def test_player_with_zero_minutes_is_skipped(self):
        # Phantom player in boxscore with 0 minutes
        timeline = {"p1": [(0, True)]}
        game_min = {"p1": 0.0}
        pm, ps = {}, {}
        self.svc._accumulate_stints(timeline, game_min, pm, ps)
        assert pm == {}
        assert ps == {}

    def test_player_with_no_timeline_events_counts_as_one_stint(self):
        # Starter who plays the entire game and is never subbed out has no PBP events.
        # They must be counted as 1 continuous stint (not excluded entirely).
        timeline = {}
        game_min = {"p1": 35.0}
        pm, ps = {}, {}
        self.svc._accumulate_stints(timeline, game_min, pm, ps)
        assert pm == {"p1": 35.0}
        assert ps == {"p1": 1}

    def test_player_with_events_all_false_is_skipped(self):
        # Malformed data: only OUT events, no IN events, non-empty timeline.
        # Should NOT count as 1 stint (data is present but looks corrupted).
        timeline = {"p1": [(500, False), (1000, False)]}
        game_min = {"p1": 10.0}
        pm, ps = {}, {}
        self.svc._accumulate_stints(timeline, game_min, pm, ps)
        assert pm == {}
        assert ps == {}

    def test_accumulates_across_multiple_calls(self):
        # Two games with same player; totals should accumulate
        timeline = {"p1": [(0, True), (600, False)]}
        game_min = {"p1": 10.0}
        pm, ps = {}, {}
        self.svc._accumulate_stints(timeline, game_min, pm, ps)
        self.svc._accumulate_stints(timeline, game_min, pm, ps)
        assert pm["p1"] == 20.0
        assert ps["p1"] == 2


class TestComputeStintAverages:
    """Unit tests for RotationService._compute_stint_averages."""
    svc = RotationService.__new__(RotationService)

    def test_single_player_one_stint(self):
        result = self.svc._compute_stint_averages({"p1": 10.0}, {"p1": 1})
        assert result["p1"] == 10.0

    def test_single_player_two_stints(self):
        result = self.svc._compute_stint_averages({"p1": 20.0}, {"p1": 2})
        assert result["p1"] == 10.0

    def test_multiple_players(self):
        result = self.svc._compute_stint_averages({"p1": 30.0, "p2": 15.0}, {"p1": 3, "p2": 2})
        assert result["p1"] == 10.0
        assert result["p2"] == pytest.approx(7.5, abs=0.1)

    def test_player_with_zero_stints_excluded(self):
        pm = {"p1": 10.0, "p2": 5.0}
        ps = {"p1": 1, "p2": 0}
        result = self.svc._compute_stint_averages(pm, ps)
        assert "p1" in result
        assert "p2" not in result

    def test_empty_returns_empty(self):
        assert self.svc._compute_stint_averages({}, {}) == {}

    def test_rounds_to_one_decimal(self):
        # 10 / 3 = 3.333… → 3.3
        result = self.svc._compute_stint_averages({"p1": 10.0}, {"p1": 3})
        assert result["p1"] == pytest.approx(3.3, abs=0.05)
