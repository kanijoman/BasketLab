"""Unit tests for _weekly_report_helpers.py — FASE B quality coverage.

Covers new functions added in the dark-theme / CV-badge implementation:
- _cv_badge_color(): threshold logic matching CVBadge.tsx
- _CV_FIELD_ALIAS: key-mapping correctness for table→CV-data lookup
- _CV_NO_BADGE: net_rating excluded from CV badge display
- apply_cv_overlay(): badge insertion, alias resolution, no-badge skip
- render_table_png(): returns valid PNG bytes, dark background
- q_color(): quartile colouring with and without reverse
- calc_quartiles(): percentile calculation
"""

from __future__ import annotations

import io
import struct
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

src_path = Path(__file__).parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from services._weekly_report_helpers import (
    _cv_badge_color,
    _CV_FIELD_ALIAS,
    _CV_NO_BADGE,
    _CELL_BG,
    _CELL_TEXT,
    _FIG_BG,
    apply_cv_overlay,
    calc_quartiles,
    q_color,
    render_table_png,
    BASIC_FIELDS,
    ADV_FIELDS,
)


# ---------------------------------------------------------------------------
# _cv_badge_color
# ---------------------------------------------------------------------------

class TestCvBadgeColor:
    """Mirrors the CVBadge.tsx logic: thresholds at 15% and 30%."""

    def test_below_lo_is_slate(self):
        assert _cv_badge_color(10.0) == '#9ca3af'

    def test_at_lo_threshold_is_amber(self):
        assert _cv_badge_color(15.0) == '#fbbf24'

    def test_between_thresholds_is_amber(self):
        assert _cv_badge_color(22.0) == '#fbbf24'

    def test_at_hi_threshold_is_red(self):
        assert _cv_badge_color(30.0) == '#ef4444'

    def test_above_hi_is_red(self):
        assert _cv_badge_color(55.0) == '#ef4444'

    def test_zero_cv_is_slate(self):
        assert _cv_badge_color(0.0) == '#9ca3af'


# ---------------------------------------------------------------------------
# _CV_FIELD_ALIAS and _CV_NO_BADGE
# ---------------------------------------------------------------------------

class TestFieldAliasMap:
    """_CV_FIELD_ALIAS maps table keys to CV-data keys from TeamStatsService."""

    def test_points_scored_maps_to_per_game_key(self):
        assert _CV_FIELD_ALIAS['points_scored'] == 'points_per_game'

    def test_total_rebounds_maps_to_per_game_key(self):
        assert _CV_FIELD_ALIAS['total_rebounds'] == 'rebounds_per_game'

    def test_assists_maps_to_per_game_key(self):
        assert _CV_FIELD_ALIAS['assists'] == 'assists_per_game'

    def test_turnovers_maps_to_per_game_key(self):
        assert _CV_FIELD_ALIAS['turnovers'] == 'turnovers_per_game'

    def test_points_received_maps_to_against(self):
        assert _CV_FIELD_ALIAS['points_received'] == 'points_against_per_game'

    def test_all_basic_fields_resolvable(self):
        """Every BASIC_FIELDS key must resolve either via alias or directly."""
        for field, _ in BASIC_FIELDS:
            resolved = _CV_FIELD_ALIAS.get(field, field)
            assert isinstance(resolved, str) and resolved, f"Empty resolution for '{field}'"


class TestCvNoBadge:
    def test_net_rating_in_no_badge_set(self):
        """net_rating must be excluded — CV is meaningless for signed metrics."""
        assert 'net_rating' in _CV_NO_BADGE

    def test_no_badge_is_frozenset(self):
        assert isinstance(_CV_NO_BADGE, frozenset)

    def test_standard_stats_not_in_no_badge(self):
        """Meaningful stats like points_per_game must NOT be excluded."""
        for field in ('points_per_game', 'efg_percentage', 'fg3_percentage'):
            assert field not in _CV_NO_BADGE


# ---------------------------------------------------------------------------
# apply_cv_overlay
# ---------------------------------------------------------------------------

def _make_texts():
    """Two-team, four-stat table text fixture."""
    return [
        ['Alpha', '10', '3', '2', '80.5', '35.0'],
        ['Beta',  '10', '2', '3', '72.0', '32.0'],
    ]


def _make_cv_data(cv_pts=20.0, cv_fg3=10.0):
    """Minimal CV data keyed by standard team-stats field names."""
    return {
        'Alpha': {
            'points_per_game':  {'mean': 80.0, 'std': 16.0, 'cv': cv_pts, 'n': 10},
            'fg3_percentage':   {'mean': 35.0, 'std':  3.5, 'cv': cv_fg3, 'n': 10},
        },
        'Beta': {
            'points_per_game':  {'mean': 72.0, 'std': 14.4, 'cv': cv_pts, 'n': 10},
            'fg3_percentage':   {'mean': 32.0, 'std':  3.2, 'cv': cv_fg3, 'n': 10},
        },
    }


# fields matching columns 4 and 5 in _make_texts (n_meta=4)
_OVERLAY_FIELDS = [('points_scored', False), ('fg3_percentage', False)]


class TestApplyCvOverlay:
    def test_returns_same_length_texts(self):
        texts = _make_texts()
        new_texts, _ = apply_cv_overlay(texts, _make_cv_data(), _OVERLAY_FIELDS, n_meta=4)
        assert len(new_texts) == len(texts)

    def test_returns_text_colors_same_shape(self):
        texts = _make_texts()
        new_texts, text_colors = apply_cv_overlay(texts, _make_cv_data(), _OVERLAY_FIELDS, n_meta=4)
        assert len(text_colors) == len(new_texts)
        assert all(len(row_c) == len(row_t) for row_c, row_t in zip(text_colors, new_texts))

    def test_badge_appended_when_cv_available(self):
        """σXX% is appended to the cell when CV data is present."""
        texts = _make_texts()
        new_texts, _ = apply_cv_overlay(texts, _make_cv_data(), _OVERLAY_FIELDS, n_meta=4)
        # column 4 = points_scored → resolves to points_per_game via alias
        assert '\n' in new_texts[0][4], "Badge (newline-separated) not found in cell"
        assert 'σ' in new_texts[0][4]

    def test_badge_color_amber_for_medium_cv(self):
        """CV=20% → amber badge colour."""
        texts = _make_texts()
        _, text_colors = apply_cv_overlay(texts, _make_cv_data(cv_pts=20.0), _OVERLAY_FIELDS, n_meta=4)
        assert text_colors[0][4] == '#fbbf24'

    def test_badge_color_red_for_high_cv(self):
        """CV=40% → red badge colour."""
        _, text_colors = apply_cv_overlay(_make_texts(), _make_cv_data(cv_pts=40.0), _OVERLAY_FIELDS, n_meta=4)
        assert text_colors[0][4] == '#ef4444'

    def test_badge_color_slate_for_low_cv(self):
        """CV=8% → slate badge colour."""
        _, text_colors = apply_cv_overlay(_make_texts(), _make_cv_data(cv_pts=8.0), _OVERLAY_FIELDS, n_meta=4)
        assert text_colors[0][4] == '#9ca3af'

    def test_no_badge_for_missing_team(self):
        """Team not in cv_data → no badge, default text colour."""
        cv_data = _make_cv_data()
        del cv_data['Alpha']
        texts = _make_texts()
        new_texts, text_colors = apply_cv_overlay(texts, cv_data, _OVERLAY_FIELDS, n_meta=4)
        assert '\n' not in new_texts[0][4], "Badge unexpectedly added for team with no CV data"
        assert text_colors[0][4] == _CELL_TEXT

    def test_no_badge_when_n_less_than_3(self):
        """CV entries with n<3 are unreliable and must be skipped."""
        cv_data = {
            'Alpha': {'points_per_game': {'mean': 80.0, 'std': 5.0, 'cv': 6.0, 'n': 2}},
            'Beta':  {'points_per_game': {'mean': 72.0, 'std': 5.0, 'cv': 6.0, 'n': 2}},
        }
        new_texts, _ = apply_cv_overlay(_make_texts(), cv_data, _OVERLAY_FIELDS, n_meta=4)
        assert '\n' not in new_texts[0][4]

    def test_empty_cv_data_returns_original_texts(self):
        texts = _make_texts()
        new_texts, text_colors = apply_cv_overlay(texts, {}, _OVERLAY_FIELDS, n_meta=4)
        assert new_texts == texts
        assert text_colors == []

    def test_empty_texts_returns_empty(self):
        new_texts, text_colors = apply_cv_overlay([], _make_cv_data(), _OVERLAY_FIELDS, n_meta=4)
        assert new_texts == []
        assert text_colors == []

    def test_net_rating_skipped_no_badge(self):
        """net_rating is in _CV_NO_BADGE → no badge even if CV data exists."""
        cv_data = {'Alpha': {'net_rating': {'mean': 5.0, 'std': 8.0, 'cv': 160.0, 'n': 10}}}
        texts = [['Alpha', '10', '5.0']]
        fields = [('net_rating', False)]
        new_texts, text_colors = apply_cv_overlay(texts, cv_data, fields, n_meta=2)
        assert '\n' not in new_texts[0][2], "net_rating should never receive CV badge"

    def test_field_alias_resolves_for_basic_fields(self):
        """points_scored (table key) must resolve to points_per_game (CV key)."""
        cv_data = {'Alpha': {'points_per_game': {'mean': 80.0, 'std': 16.0, 'cv': 20.0, 'n': 10}}}
        texts = [['Alpha', '10', '80.5']]
        fields = [('points_scored', False)]   # uses alias
        new_texts, text_colors = apply_cv_overlay(texts, cv_data, fields, n_meta=2)
        assert 'σ' in new_texts[0][2], "Alias resolution failed — badge not added for points_scored"


# ---------------------------------------------------------------------------
# render_table_png
# ---------------------------------------------------------------------------

def _png_signature(data: bytes) -> bool:
    """Return True if data starts with the 8-byte PNG signature."""
    return data[:8] == b'\x89PNG\r\n\x1a\n'


class TestRenderTablePng:
    _HEADERS = ['Equipo', 'PJ', 'Pts', 'Reb']
    _ROWS    = [['Alpha', '10', '80.5', '35.0'], ['Beta', '10', '72.0', '30.0']]
    _COLORS  = [[_CELL_BG, _CELL_BG, '#14532d', _CELL_BG],
                [_CELL_BG, _CELL_BG, '#500000', _CELL_BG]]

    def test_returns_bytes(self):
        result = render_table_png(self._HEADERS, self._ROWS, self._COLORS, 'Test')
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_output_is_valid_png(self):
        result = render_table_png(self._HEADERS, self._ROWS, self._COLORS, 'Test')
        assert _png_signature(result), "Output is not a valid PNG file"

    def test_empty_rows_returns_valid_png(self):
        result = render_table_png(self._HEADERS, [], [], 'Empty')
        assert _png_signature(result)

    def test_text_colors_param_does_not_raise(self):
        text_colors = [[_CELL_TEXT] * 4, [_CELL_TEXT] * 4]
        result = render_table_png(
            self._HEADERS, self._ROWS, self._COLORS, 'With CV', text_colors=text_colors
        )
        assert _png_signature(result)

    def test_larger_output_with_cv_rows(self):
        """With text_colors (CV badges), row_h is bigger → image is larger."""
        without_cv = render_table_png(self._HEADERS, self._ROWS, self._COLORS, 'No CV')
        text_colors = [['#fbbf24', _CELL_TEXT, '#ef4444', _CELL_TEXT],
                       [_CELL_TEXT, _CELL_TEXT, '#9ca3af', _CELL_TEXT]]
        with_cv = render_table_png(
            self._HEADERS, self._ROWS, self._COLORS, 'With CV', text_colors=text_colors
        )
        # Images with taller rows should generally be larger
        assert len(with_cv) >= len(without_cv)

    def test_many_columns_produces_wider_image(self):
        """More columns → larger figure width."""
        wide_headers = [f'Col{i}' for i in range(20)]
        wide_rows    = [['V'] * 20]
        wide_colors  = [[_CELL_BG] * 20]
        narrow = render_table_png(['A', 'B'], [['X', 'Y']], [[_CELL_BG] * 2], 'Narrow')
        wide   = render_table_png(wide_headers, wide_rows, wide_colors, 'Wide')
        assert len(wide) > len(narrow)


# ---------------------------------------------------------------------------
# q_color and calc_quartiles
# ---------------------------------------------------------------------------

class TestQColor:
    _Q = [25.0, 50.0, 75.0]  # Q1, Q2, Q3

    def test_best_value_gets_q4_color(self):
        color = q_color(80.0, self._Q, reverse=False)
        from services._weekly_report_helpers import _Q_COLORS
        assert color == _Q_COLORS[3]

    def test_worst_value_gets_q1_color(self):
        color = q_color(10.0, self._Q, reverse=False)
        from services._weekly_report_helpers import _Q_COLORS
        assert color == _Q_COLORS[0]

    def test_reverse_swaps_best_worst(self):
        """reverse=True means low values are good (e.g. turnovers)."""
        color_best  = q_color(10.0, self._Q, reverse=True)
        color_worst = q_color(80.0, self._Q, reverse=True)
        from services._weekly_report_helpers import _Q_COLORS
        assert color_best  == _Q_COLORS[3], "Low value (good) should get Q4 colour when reversed"
        assert color_worst == _Q_COLORS[0], "High value (bad) should get Q1 colour when reversed"


class TestCalcQuartiles:
    def test_returns_three_values(self):
        result = calc_quartiles([10, 20, 30, 40, 50])
        assert len(result) == 3

    def test_q1_le_q2_le_q3(self):
        result = calc_quartiles([5, 10, 15, 20, 25, 30, 35, 40])
        assert result[0] <= result[1] <= result[2]

    def test_empty_list_returns_zeros(self):
        result = calc_quartiles([])
        assert result == [0.0, 0.0, 0.0]

    def test_none_values_ignored(self):
        result = calc_quartiles([None, 10, 20, 30])
        assert result[0] <= result[1] <= result[2]


# ---------------------------------------------------------------------------
# CV formula regression (team_stats_service._build_cv_map)
# Tests mock collection.aggregate() to return pre-built per-game rows,
# exercising the abs(mean)/floor/cap logic added in the FASE B fix.
# ---------------------------------------------------------------------------

class TestCvFormulaRegression:
    """Regression tests for the CV formula fix in TeamStatsService.

    Bug: old formula used ``if mean > 0`` → negative-mean metrics (net_rating)
    returned cv=0; near-zero mean produced division-by-~0 extreme values.
    Fix: use abs(mean) with a floor of 1.0 and cap at 200%.
    """

    def _make_service_with_rows(self, rows: list[dict]):
        """Return a TeamStatsService whose aggregate() yields the given rows."""
        from services.team_stats_service import TeamStatsService

        mock_coll = MagicMock()
        mock_coll.aggregate.return_value = rows
        db_handler = MagicMock()
        db_handler.connection.get_collection.return_value = mock_coll
        return TeamStatsService(db_handler)

    def _game_row(self, team: str, net_game: float, points: float = 75.0) -> dict:
        """Minimal per-game row in the format expected by _build_cv_map."""
        return {
            "team_name": team,
            "net_game":  net_game,
            "points":    points,
            "opponent_points": points - net_game,
            "fg3_pct_game": 33.0, "fg2_pct_game": 50.0, "ft_pct_game": 75.0,
            "fg3_attempts": 15, "total_rebounds": 35,
            "off_rebounds": 8, "def_rebounds": 27,
            "assists": 18, "steals": 7, "turnovers": 12, "blocks": 3,
            "possessions": 90.0,
            "oer_game": 110.0, "der_game": 105.0,
            "efg_pct_game": 50.0, "ts_pct_game": 55.0,
            "tov_pct_game": 13.0, "three_point_rate_game": 0.3,
        }

    def test_negative_mean_cv_uses_abs_mean(self):
        """CV for a negative-mean metric must use abs(mean), not return 0."""
        rows = [self._game_row("Alpha", net_game=-3.0 + 0.2 * i) for i in range(10)]
        svc = self._make_service_with_rows(rows)
        result = svc.get_consistency("FEB_COL")
        assert result, "Service returned empty — rows not processed"
        alpha = result.get("own", {}).get("Alpha", {})
        assert "net_rating" in alpha, "net_rating missing from consistency output"
        cv = alpha["net_rating"]["cv"]
        # mean ≈ -2.1, std ≈ 0.6 → raw CV ≈ 28% (using abs(mean)) — must be >0
        assert cv > 0, f"CV should be >0 for negative-mean net_rating, got {cv}"

    def test_near_zero_mean_cv_is_zero(self):
        """When abs(mean) < 1.0, CV is 0.0 to avoid absurdly large values."""
        # net_game oscillates around 0 → mean ≈ 0
        rows = [self._game_row("Beta", net_game=(-1) ** i * 0.4) for i in range(10)]
        svc = self._make_service_with_rows(rows)
        result = svc.get_consistency("FEB_COL")
        assert result, "Service returned empty"
        beta = result.get("own", {}).get("Beta", {})
        assert "net_rating" in beta, "net_rating missing"
        cv = beta["net_rating"]["cv"]
        assert cv == 0.0, f"CV should be 0 when abs(mean)<1, got {cv}"

    def test_cv_capped_at_200(self):
        """When std >> mean, CV must be capped at 200%."""
        # mean ≈ 1.0, std ≈ 5.5 → raw CV ≈ 550%  →  must be capped at 200
        net_values = [1.0, 6.0, -4.0, 7.0, -5.0, 3.0, -6.0, 8.0, -4.0, 5.0]
        rows = [self._game_row("Gamma", net_game=v) for v in net_values]
        svc = self._make_service_with_rows(rows)
        result = svc.get_consistency("FEB_COL")
        assert result, "Service returned empty"
        gamma = result.get("own", {}).get("Gamma", {})
        for field, entry in gamma.items():
            if "cv" not in entry:
                # derived index entries (volatilidad_triple, sostenibilidad_efg)
                # don't have cv — skip them
                continue
            assert entry["cv"] <= 200.0, f"CV for '{field}' exceeded cap: {entry['cv']}"
