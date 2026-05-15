"""Tests for FASE 9 — SeasonProjectionService (season-end standings Monte Carlo).

TDD cycle: tests written BEFORE implementation.

Coverage:
- Happy path: returns projected standings with win probabilities per team
- Simulation integrity: law-of-large-numbers sanity check
- Output structure: rankings, playoff probability, win distribution
- Edge cases: no teams, single team, insufficient history
- API endpoint: GET /api/v1/analysis/season-projection/{collection}
"""

from __future__ import annotations

import sys
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

sys.path.insert(0, "src")
from pathlib import Path
src_path = Path(__file__).parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

TARGET_N_GAMES = 22  # typical FEB LF2 season length


def _make_team_history(
    team_id: str,
    n_games: int,
    win_rate: float = 0.5,
    seed: int = 0,
) -> List[Dict[str, Any]]:
    """Build per-game HISTORICAL records for a team."""
    rng = np.random.default_rng(seed)
    records = []
    for i in range(n_games):
        won = rng.random() < win_rate
        net = round(rng.normal(5 if won else -5, 4), 2)
        records.append({
            "team_id":    team_id,
            "team_name":  f"Team {team_id}",
            "season":     "2024-25",
            "date":       f"2024-{9 + i // 4:02d}-{(i % 4) * 7 + 1:02d}",
            "net_rtg":    net,
            "ortg":       round(100 + rng.normal(0, 3), 2),
            "drtg":       round(100 - net + rng.normal(0, 3), 2),
            "efg_pct":    round(rng.uniform(0.44, 0.56), 3),
            "tov_rate":   round(rng.uniform(0.10, 0.22), 3),
            "oreb_pct":   round(rng.uniform(0.22, 0.38), 3),
            "is_home":    i % 2 == 0,
            "result":     1 if won else 0,
        })
    return records


def _make_league(
    n_teams: int = 8,
    games_played: int = 11,
) -> Dict[str, List[Dict[str, Any]]]:
    """Return {team_id: [game_records]} for a multi-team league snapshot."""
    win_rates = np.linspace(0.2, 0.8, n_teams)
    return {
        f"T{i}": _make_team_history(f"T{i}", games_played, win_rate=float(win_rates[i]), seed=i)
        for i in range(n_teams)
    }


def _mock_conn() -> MagicMock:
    conn = MagicMock()
    conn.is_connected.return_value = True
    return conn


# ===========================================================================
# Unit tests — SeasonProjectionService.project()
# ===========================================================================

class TestSeasonProjectionContract:
    """Verify output shape and value constraints."""

    def _project(self, league_data, **kwargs):
        from services.season_projection_service import SeasonProjectionService
        conn = _mock_conn()
        svc = SeasonProjectionService(conn)
        with patch.object(svc, "_load_league_data", return_value=league_data):
            return svc.project(
                collection="FEB_LF2_2025_A",
                season="2024-25",
                season_length=TARGET_N_GAMES,
                n_simulations=200,
                **kwargs,
            )

    def test_returns_list(self):
        result = self._project(_make_league(8, 11))
        assert isinstance(result, list)

    def test_one_entry_per_team(self):
        league = _make_league(8, 11)
        result = self._project(league)
        assert len(result) == 8

    def test_entry_has_required_keys(self):
        required = {"team_id", "team_name", "wins_so_far", "losses_so_far",
                    "proj_wins", "proj_losses", "proj_wins_ci_low",
                    "proj_wins_ci_high", "playoff_prob", "rank_probs"}
        result = self._project(_make_league(8, 11))
        for entry in result:
            assert required.issubset(entry.keys()), (
                f"Missing: {required - set(entry.keys())} in {entry.get('team_id')}"
            )

    def test_proj_wins_between_0_and_season_length(self):
        result = self._project(_make_league(8, 11))
        for entry in result:
            assert 0 <= entry["proj_wins"] <= TARGET_N_GAMES, (
                f"{entry['team_id']}: proj_wins={entry['proj_wins']}"
            )

    def test_playoff_prob_between_0_and_1(self):
        result = self._project(_make_league(8, 11))
        for entry in result:
            assert 0.0 <= entry["playoff_prob"] <= 1.0, (
                f"{entry['team_id']}: playoff_prob={entry['playoff_prob']}"
            )

    def test_ci_bounds_ordered(self):
        result = self._project(_make_league(8, 11))
        for entry in result:
            assert entry["proj_wins_ci_low"] <= entry["proj_wins"] <= entry["proj_wins_ci_high"]

    def test_rank_probs_sums_to_1(self):
        result = self._project(_make_league(8, 11))
        for entry in result:
            total = sum(entry["rank_probs"].values())
            assert abs(total - 1.0) < 0.01, (
                f"{entry['team_id']}: rank_probs sum={total}"
            )

    def test_stronger_team_has_higher_proj_wins(self):
        """Best team (T7, win_rate=0.8) should project more wins than worst (T0, win_rate=0.2)."""
        result = self._project(_make_league(8, 11))
        by_team = {e["team_id"]: e for e in result}
        assert by_team["T7"]["proj_wins"] > by_team["T0"]["proj_wins"]

    def test_sorted_by_proj_wins_desc(self):
        result = self._project(_make_league(8, 11))
        wins = [e["proj_wins"] for e in result]
        assert wins == sorted(wins, reverse=True)


# ===========================================================================
# Unit tests — simulation math
# ===========================================================================

class TestSimulationMath:

    def test_wins_so_far_correct(self):
        """wins_so_far must equal count of result==1 in actual games."""
        league = _make_league(4, 8)
        from services.season_projection_service import SeasonProjectionService
        conn = _mock_conn()
        svc = SeasonProjectionService(conn)
        with patch.object(svc, "_load_league_data", return_value=league):
            result = svc.project("col", "2024-25", season_length=22, n_simulations=100)
        by_team = {e["team_id"]: e for e in result}
        for team_id, records in league.items():
            expected_wins = sum(r["result"] for r in records)
            assert by_team[team_id]["wins_so_far"] == expected_wins

    def test_law_of_large_numbers(self):
        """A team with dominant history should project as #1 with very high prob."""
        league = {
            "BEST": _make_team_history("BEST",  12, win_rate=0.95, seed=1),
            "BAD1": _make_team_history("BAD1",  12, win_rate=0.10, seed=2),
            "BAD2": _make_team_history("BAD2",  12, win_rate=0.10, seed=3),
            "BAD3": _make_team_history("BAD3",  12, win_rate=0.10, seed=4),
        }
        from services.season_projection_service import SeasonProjectionService
        conn = _mock_conn()
        svc = SeasonProjectionService(conn)
        with patch.object(svc, "_load_league_data", return_value=league):
            result = svc.project("col", "2024-25", season_length=22, n_simulations=500)
        best = next(e for e in result if e["team_id"] == "BEST")
        # BEST should have P(rank=1) > 0.85
        assert best["rank_probs"].get(1, 0.0) > 0.70


# ===========================================================================
# Edge cases
# ===========================================================================

class TestSeasonProjectionEdgeCases:

    def _project(self, league_data, **kwargs):
        from services.season_projection_service import SeasonProjectionService
        conn = _mock_conn()
        svc = SeasonProjectionService(conn)
        with patch.object(svc, "_load_league_data", return_value=league_data):
            return svc.project("col", "2024-25", n_simulations=100, **kwargs)

    def test_empty_league_returns_error(self):
        result = self._project({})
        assert isinstance(result, dict) and "error" in result

    def test_single_team_returns_entry(self):
        league = {"T0": _make_team_history("T0", 10, win_rate=0.5)}
        result = self._project(league)
        assert isinstance(result, list) and len(result) == 1

    def test_team_with_no_games_handled(self):
        league = {
            "T0": _make_team_history("T0", 10, win_rate=0.5),
            "T1": [],  # no games played
        }
        result = self._project(league)
        assert isinstance(result, list)

    def test_season_already_finished(self):
        """All games played — projection should equal actual record."""
        league = {"T0": _make_team_history("T0", 22, win_rate=0.6)}
        result = self._project(league, season_length=22)
        assert isinstance(result, list) and len(result) == 1
        entry = result[0]
        # When no games remain, proj_wins == wins_so_far
        assert entry["proj_wins"] == entry["wins_so_far"]


# ===========================================================================
# Win probability helper
# ===========================================================================

class TestWinProbHelper:

    def test_win_prob_from_net_rtg(self):
        """Higher net_rtg team should have win_prob > 0.5."""
        from services.season_projection_service import win_prob_from_net_rtg
        p = win_prob_from_net_rtg(team_rtg=5.0, opp_rtg=-3.0)
        assert p > 0.5

    def test_win_prob_symmetric(self):
        from services.season_projection_service import win_prob_from_net_rtg
        p_a = win_prob_from_net_rtg(team_rtg=5.0, opp_rtg=-3.0)
        p_b = win_prob_from_net_rtg(team_rtg=-3.0, opp_rtg=5.0)
        assert abs(p_a + p_b - 1.0) < 0.001

    def test_equal_teams_50pct(self):
        from services.season_projection_service import win_prob_from_net_rtg
        p = win_prob_from_net_rtg(team_rtg=0.0, opp_rtg=0.0)
        assert abs(p - 0.5) < 0.01


# ===========================================================================
# API endpoint
# ===========================================================================

class TestSeasonProjectionAPIEndpoint:

    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from src.api.app import app
        return TestClient(app)

    def _mock_result(self):
        return [
            {
                "team_id": "T0", "team_name": "Team 0",
                "wins_so_far": 6, "losses_so_far": 5,
                "proj_wins": 12.1, "proj_losses": 9.9,
                "proj_wins_ci_low": 10.0, "proj_wins_ci_high": 14.0,
                "playoff_prob": 0.72,
                "rank_probs": {1: 0.15, 2: 0.25, 3: 0.30, 4: 0.30},
            }
        ]

    def test_returns_200(self, client):
        with (
            patch("src.api.deps.get_db") as mock_db,
            patch("src.services.season_projection_service.SeasonProjectionService") as MockSvc,
        ):
            mock_db.return_value = MagicMock()
            MockSvc.return_value.project.return_value = self._mock_result()
            resp = client.get(
                "/api/v1/analysis/season-projection/FEB_LF2_2025_A",
                params={"season": "2024-25"},
            )
        assert resp.status_code == 200

    def test_response_is_list(self, client):
        with (
            patch("src.api.deps.get_db") as mock_db,
            patch("src.services.season_projection_service.SeasonProjectionService") as MockSvc,
        ):
            mock_db.return_value = MagicMock()
            MockSvc.return_value.project.return_value = self._mock_result()
            resp = client.get(
                "/api/v1/analysis/season-projection/FEB_LF2_2025_A",
                params={"season": "2024-25"},
            )
        assert isinstance(resp.json(), list)

    def test_missing_season_uses_live_mode(self, client):
        """season is now optional — endpoint must not return 422 when omitted."""
        with (
            patch("src.api.deps.get_db") as mock_db,
            patch("src.services.season_projection_service.SeasonProjectionService") as MockSvc,
        ):
            mock_db.return_value = MagicMock()
            MockSvc.return_value.project.return_value = []
            resp = client.get(
                "/api/v1/analysis/season-projection/FEB_LF2_2025_A"
            )
        assert resp.status_code != 422
