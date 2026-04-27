"""FASE C quality coverage — PlayerStatsService CV formula regressions.

Covers the abs(mean)/floor/cap fix applied in the same session as FASE B but
in a different service:

  player_stats_service.get_consistency()    — FEB branch
  player_stats_service._get_consistency_fbcyl() — FBCYL branch

Bug fixed: old formula used ``if mean > 0`` which returned cv=0 for negative-
mean metrics (not applicable to player stats) and produced absurdly large CV
for near-zero means (e.g. very few turnovers per game).

Fix: ``cv = (std / abs(mean) * 100) if abs(mean) >= 1.0 else 0.0``
     ``cv = min(cv, 200.0)``

Also documents the FBCYL phantom-player guard logic (``_player_minutes_played``
in repository_inout.py) as a regression suite.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

src_path = Path(__file__).parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _feb_player_row(player_id: str, to: float, pts: float = 10.0) -> dict:
    """Minimal FEB per-player per-game row in the format expected by FIELD_MAP."""
    return {
        "player_id": player_id,
        "pts": pts,
        "rt": 5.0, "ro": 1.0, "rd": 4.0,
        "assist": 3.0, "st": 1.0, "to": to, "bs": 0.5,
        "pf": 2.0, "val": 10.0, "pllss_game": 5.0,
        "minutes": 25.0,
        "fg1_pct_game": 75.0, "fg2_pct_game": 45.0, "fg3_pct_game": 33.0,
        "efg_pct_game": 50.0, "ts_pct_game": 55.0,
        "ftr_game": 0.2, "three_pr_game": 0.3, "tov_pct_game": 12.0,
        "usg_pct_game": 20.0, "ast_pct_game": 15.0,
        "orb_pct_game": 5.0, "drb_pct_game": 20.0,
        "stl_pct_game": 2.0, "blk_pct_game": 1.0,
    }


def _fbcyl_player_row(player_id: str, to: float, pts: float = 10.0) -> dict:
    """Minimal FBCYL per-player per-game row (pre-enrich format).

    Uses the same field names as FBCYL_FIELD_MAP so enrich is effectively
    a no-op for the fields being tested here (``to`` is a direct field).
    Provides zeros for enrichment inputs (p1m/p2m/p3m etc.) so enrich does
    not raise.
    """
    return {
        "player_id": player_id,
        "pts": pts,
        "rt": 5.0, "ro": 1.0, "rd": 4.0,
        "assist": 3.0, "st": 1.0, "to": to, "bs": 0.5,
        "pf": 2.0, "val": 10.0, "minutes": 25.0,
        # enrichment inputs (kept at safe defaults so enrich doesn't crash)
        "p1a": 2, "p1m": 1, "p2a": 8, "p2m": 4, "p3a": 6, "p3m": 2,
    }


def _make_feb_service(rows: list[dict]):
    """Return a PlayerStatsService with aggregate() mocked to yield rows."""
    from services.player_stats_service import PlayerStatsService

    mock_coll = MagicMock()
    mock_coll.aggregate.return_value = rows
    db_handler = MagicMock()
    db_handler.connection.get_collection.return_value = mock_coll
    return PlayerStatsService(db_handler)


def _make_fbcyl_service(rows: list[dict]):
    """Return a PlayerStatsService for a FBCYL collection, aggregate mocked."""
    from services.player_stats_service import PlayerStatsService

    mock_coll = MagicMock()
    mock_coll.aggregate.return_value = rows
    db_handler = MagicMock()
    db_handler.connection.get_collection.return_value = mock_coll
    return PlayerStatsService(db_handler)


# ---------------------------------------------------------------------------
# 1. FEB branch CV formula regressions
# ---------------------------------------------------------------------------

class TestPlayerStatsCvFormulaFEB:
    """Regression for the abs(mean)/floor/cap CV formula — FEB branch.

    Player stats are always non-negative so negative-mean is not tested;
    the critical regressions are the near-zero floor and the 200% cap.
    """

    def test_near_zero_mean_cv_is_zero(self):
        """abs(mean) < 1 → CV = 0.0.

        Regression: old formula cv = std/mean*100 when mean > 0 would give
        huge values for e.g. turnovers_per_game ≈ 0.5.
        """
        # to values oscillate between 0 and 1 → mean = 0.5, abs(mean) < 1
        rows = [_feb_player_row("p01", to=float(i % 2)) for i in range(10)]
        svc = _make_feb_service(rows)
        result = svc.get_consistency("FEB_COL")
        assert result, "Service returned empty"
        p = result.get("p01", {})
        assert "turnovers_per_game" in p, "turnovers_per_game missing from consistency output"
        cv = p["turnovers_per_game"]["cv"]
        assert cv == 0.0, f"Expected cv=0.0 for near-zero mean turnovers, got {cv}"

    def test_huge_variability_cv_capped_at_200(self):
        """std >> mean → CV capped at 200%.

        Construction: pts = [0,0,...,0,10] → mean=1.0, std=3.0, raw cv=300%.
        """
        pts_values = [0.0] * 9 + [10.0]  # mean=1.0, std=3.0 → raw cv=300%
        rows = [_feb_player_row("p02", to=1.0, pts=v) for v in pts_values]
        svc = _make_feb_service(rows)
        result = svc.get_consistency("FEB_COL")
        assert result, "Service returned empty"
        p = result.get("p02", {})
        assert "points_per_game" in p
        cv = p["points_per_game"]["cv"]
        assert cv <= 200.0, f"CV for points_per_game exceeded cap: {cv}"

    def test_cv_is_positive_for_real_variability(self):
        """Normal variability produces a positive CV > 0."""
        # pts values vary realistically between 8 and 22
        pts_values = [8.0, 12.0, 15.0, 20.0, 10.0, 18.0, 9.0, 22.0, 11.0, 14.0]
        rows = [_feb_player_row("p03", to=1.0, pts=v) for v in pts_values]
        svc = _make_feb_service(rows)
        result = svc.get_consistency("FEB_COL")
        assert result, "Service returned empty"
        p = result.get("p03", {})
        assert "points_per_game" in p
        cv = p["points_per_game"]["cv"]
        assert 0 < cv <= 200.0

    def test_cv_computed_as_std_over_abs_mean(self):
        """Verify the exact formula: cv = std/abs(mean)*100, rounded to 1 dp."""
        pts_values = [10.0, 12.0, 8.0, 14.0, 6.0, 10.0, 12.0, 8.0, 14.0, 6.0]
        rows = [_feb_player_row("p04", to=1.0, pts=v) for v in pts_values]
        svc = _make_feb_service(rows)
        result = svc.get_consistency("FEB_COL")
        assert result, "Service returned empty"
        p = result.get("p04", {})
        assert "points_per_game" in p

        arr = np.array(pts_values)
        expected_cv = round(float(np.std(arr)) / abs(float(np.mean(arr))) * 100, 1)
        assert p["points_per_game"]["cv"] == expected_cv

    def test_min_sample_guard_three_games(self):
        """Fewer than 3 games → no CV entry for that player."""
        rows = [_feb_player_row("p05", to=1.0) for _ in range(2)]
        svc = _make_feb_service(rows)
        result = svc.get_consistency("FEB_COL")
        p = result.get("p05", {})
        assert p == {}, "Player with <3 games should not produce any CV entries"

    def test_cv_non_negative_for_all_fields(self):
        """Every CV entry must be non-negative regardless of stat."""
        rows = [_feb_player_row("p06", to=float(i % 3), pts=float(10 + i)) for i in range(10)]
        svc = _make_feb_service(rows)
        result = svc.get_consistency("FEB_COL")
        assert result
        p = result.get("p06", {})
        for field, entry in p.items():
            assert entry["cv"] >= 0, f"Negative CV for field '{field}': {entry['cv']}"


# ---------------------------------------------------------------------------
# 2. FBCYL branch CV formula regressions
# ---------------------------------------------------------------------------

class TestPlayerStatsCvFormulaFBCYL:
    """Regression for the abs(mean)/floor/cap CV formula — FBCYL branch."""

    def test_near_zero_mean_cv_is_zero(self):
        """abs(mean) < 1 → CV = 0.0 for FBCYL turnovers."""
        rows = [_fbcyl_player_row("uuid-01", to=float(i % 2)) for i in range(10)]
        svc = _make_fbcyl_service(rows)
        result = svc.get_consistency("FBCYL_SE_COL")
        assert result, "FBCYL service returned empty"
        p = result.get("uuid-01", {})
        assert "turnovers_per_game" in p, "turnovers_per_game missing for FBCYL player"
        cv = p["turnovers_per_game"]["cv"]
        assert cv == 0.0, f"Expected 0.0 for near-zero mean turnovers (FBCYL), got {cv}"

    def test_huge_variability_cv_capped_at_200(self):
        """std >> mean → CV capped at 200% for FBCYL points."""
        pts_values = [0.0] * 9 + [10.0]
        rows = [_fbcyl_player_row("uuid-02", to=1.0, pts=v) for v in pts_values]
        svc = _make_fbcyl_service(rows)
        result = svc.get_consistency("FBCYL_SE_COL")
        assert result, "FBCYL service returned empty"
        p = result.get("uuid-02", {})
        assert "points_per_game" in p
        cv = p["points_per_game"]["cv"]
        assert cv <= 200.0, f"CV for FBCYL points exceeded cap: {cv}"

    def test_cv_is_positive_for_real_variability(self):
        """Normal variability produces a positive CV for FBCYL players."""
        pts_values = [8.0, 12.0, 15.0, 20.0, 10.0, 18.0, 9.0, 22.0, 11.0, 14.0]
        rows = [_fbcyl_player_row("uuid-03", to=1.0, pts=v) for v in pts_values]
        svc = _make_fbcyl_service(rows)
        result = svc.get_consistency("FBCYL_SE_COL")
        assert result
        p = result.get("uuid-03", {})
        assert "points_per_game" in p
        cv = p["points_per_game"]["cv"]
        assert 0 < cv <= 200.0

    def test_cv_computed_as_std_over_abs_mean(self):
        """Verify exact formula for FBCYL branch."""
        pts_values = [10.0, 12.0, 8.0, 14.0, 6.0, 10.0, 12.0, 8.0, 14.0, 6.0]
        rows = [_fbcyl_player_row("uuid-04", to=1.0, pts=v) for v in pts_values]
        svc = _make_fbcyl_service(rows)
        result = svc.get_consistency("FBCYL_SE_COL")
        assert result
        p = result.get("uuid-04", {})
        assert "points_per_game" in p

        arr = np.array(pts_values)
        expected_cv = round(float(np.std(arr)) / abs(float(np.mean(arr))) * 100, 1)
        assert p["points_per_game"]["cv"] == expected_cv

    def test_min_sample_guard(self):
        """FBCYL: fewer than 3 games → no CV entry."""
        rows = [_fbcyl_player_row("uuid-05", to=1.0) for _ in range(2)]
        svc = _make_fbcyl_service(rows)
        result = svc.get_consistency("FBCYL_SE_COL")
        p = result.get("uuid-05", {})
        assert p == {}, "FBCYL player with <3 games should not produce any CV entries"

    def test_cv_non_negative_for_all_fields(self):
        """Every FBCYL CV entry must be non-negative."""
        rows = [_fbcyl_player_row("uuid-06", to=float(i % 3), pts=float(10 + i)) for i in range(10)]
        svc = _make_fbcyl_service(rows)
        result = svc.get_consistency("FBCYL_SE_COL")
        assert result
        p = result.get("uuid-06", {})
        for field, entry in p.items():
            assert entry["cv"] >= 0, f"Negative FBCYL CV for '{field}': {entry['cv']}"


# ---------------------------------------------------------------------------
# 3. PlayerStatsService FIELD_MAP regression
# ---------------------------------------------------------------------------

class TestPlayerStatsFieldMapRegression:
    """Regression: key field names from FIELD_MAP must appear in get_consistency output.

    These tests document the mapping between the stat keys the frontend/API
    expects and the raw fields in the per-game pipeline output.
    """

    def _make_rows(self, n=10):
        return [_feb_player_row("p_map", to=float(i % 5)) for i in range(n)]

    def _get_player_data(self):
        svc = _make_feb_service(self._make_rows())
        result = svc.get_consistency("FEB_COL")
        return result.get("p_map", {})

    def test_points_per_game_present(self):
        assert "points_per_game" in self._get_player_data()

    def test_turnovers_per_game_present(self):
        assert "turnovers_per_game" in self._get_player_data()

    def test_assists_per_game_present(self):
        assert "assists_per_game" in self._get_player_data()

    def test_rebounds_per_game_present(self):
        assert "rebounds_per_game" in self._get_player_data()

    def test_fg3_percentage_present(self):
        assert "fg3_percentage" in self._get_player_data()

    def test_efg_percentage_present(self):
        assert "efg_percentage" in self._get_player_data()

    def test_true_shooting_present(self):
        assert "true_shooting" in self._get_player_data()

    def test_minutes_per_game_present(self):
        assert "minutes_per_game" in self._get_player_data()

    def test_all_cv_entries_have_required_keys(self):
        """Every CV entry must have mean, std, cv, n."""
        p = self._get_player_data()
        assert p, "No CV data returned"
        for field, entry in p.items():
            for key in ("mean", "std", "cv", "n"):
                assert key in entry, f"Key '{key}' missing from CV entry for '{field}'"


# ---------------------------------------------------------------------------
# 4. FBCYL phantom-player guard logic (repository_inout.py regression)
# ---------------------------------------------------------------------------

# This function mirrors the guard inside _player_minutes_played() for FBCYL.
# It is defined here as a pure helper so the logic can be tested in isolation.
# The actual implementation lives as a nested closure in
# InOutRepositoryMixin.get_player_in_out_stats() — any changes there should
# also be reflected here to keep the regression green.

_PHANTOM_ACTIVITY_KEYS = (
    'score', 'shotsOfTwoAttempted', 'shotsOfThreeAttempted',
    'shotsOfOneAttempted', 'offensiveRebound', 'defensiveRebound',
    'assists', 'lost', 'block', 'steals',
)


def _fbcyl_player_minutes(player_data: dict) -> float:
    """Mirror of the FBCYL branch of _player_minutes_played in repository_inout.py.

    Returns the effective minutes played, treating phantom players
    (timePlayed=40, all activity stats=0) as having played 0 minutes.
    """
    m = player_data.get('timePlayed')
    if m is None:
        return 0.0
    minutes = float(m)
    if minutes == 40.0:
        data = player_data.get('data', {}) or {}
        activity = sum(data.get(k, 0) or 0 for k in _PHANTOM_ACTIVITY_KEYS)
        if activity == 0:
            return 0.0
    return minutes


class TestFBCYLPhantomPlayerGuardLogic:
    """Regression for the FBCYL phantom-player guard in _player_minutes_played.

    FBCYL assigns timePlayed=40 to inscribed-but-never-played players while
    every activity stat remains 0.  These players must be excluded from
    in/out analyses by returning 0.0 minutes.
    """

    def _phantom(self) -> dict:
        return {
            'timePlayed': 40,
            'data': {k: 0 for k in _PHANTOM_ACTIVITY_KEYS},
        }

    def _real_40min(self) -> dict:
        return {
            'timePlayed': 40,
            'data': {'score': 18, 'shotsOfTwoAttempted': 8, 'assists': 3},
        }

    def _real_partial(self) -> dict:
        return {
            'timePlayed': 25,
            'data': {'score': 12, 'shotsOfTwoAttempted': 5},
        }

    def test_phantom_returns_zero_minutes(self):
        """timePlayed=40, all stats=0 → must return 0.0."""
        assert _fbcyl_player_minutes(self._phantom()) == 0.0

    def test_real_40min_player_not_excluded(self):
        """timePlayed=40 with activity → must return 40.0."""
        assert _fbcyl_player_minutes(self._real_40min()) == 40.0

    def test_real_partial_player_not_affected(self):
        """timePlayed=25 → guard only applies to timePlayed=40."""
        assert _fbcyl_player_minutes(self._real_partial()) == 25.0

    def test_none_time_played_returns_zero(self):
        """Missing timePlayed field → 0.0."""
        assert _fbcyl_player_minutes({'data': {'score': 5}}) == 0.0

    def test_partial_activity_stats_not_phantom(self):
        """Only one activity stat >0 is enough to be non-phantom."""
        p = {'timePlayed': 40, 'data': {'score': 0, 'assists': 1}}
        assert _fbcyl_player_minutes(p) == 40.0

    def test_null_data_dict_treated_as_zeros(self):
        """data=None is treated as {} (all zeros) → phantom."""
        p = {'timePlayed': 40, 'data': None}
        assert _fbcyl_player_minutes(p) == 0.0

    def test_missing_activity_key_treated_as_zero(self):
        """Activity key absent in data dict → counts as 0 (phantom if all missing)."""
        p = {'timePlayed': 40, 'data': {}}
        assert _fbcyl_player_minutes(p) == 0.0

    def test_stat_none_treated_as_zero(self):
        """Activity stat with value None → treated as 0."""
        p = {'timePlayed': 40, 'data': {k: None for k in _PHANTOM_ACTIVITY_KEYS}}
        assert _fbcyl_player_minutes(p) == 0.0
