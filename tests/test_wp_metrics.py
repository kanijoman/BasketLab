"""Metrics of the win-probability calibration (issue #255): Brier, log loss, reliability by deciles, MAE."""

import math

import pytest

from src.live_prep.wp_metrics import brier, log_loss, mae, max_decile_gap, reliability


def test_brier_by_hand():
    assert brier([0.5, 0.5], [1, 0]) == pytest.approx(0.25)
    assert brier([1.0, 0.0], [1, 0]) == 0.0
    assert brier([0.8, 0.3], [1, 0]) == pytest.approx((0.04 + 0.09) / 2)


def test_log_loss_by_hand_and_clipped():
    assert log_loss([0.5], [1]) == pytest.approx(math.log(2))
    assert log_loss([0.9, 0.2], [1, 0]) == pytest.approx(-(math.log(0.9) + math.log(0.8)) / 2)
    assert math.isfinite(log_loss([0.0], [1]))   # a certain wrong answer is penalised, not infinite


def test_empty_inputs_give_none_not_a_crash():
    assert brier([], []) is None and log_loss([], []) is None and mae([], []) is None


def test_mae():
    assert mae([3.0, -2.0], [5.0, -2.0]) == pytest.approx(1.0)


def test_reliability_puts_each_probability_in_its_decile():
    rows = reliability([0.05, 0.08, 0.55, 0.95, 1.0], [0, 1, 1, 1, 1])
    assert [r["bin"] for r in rows] == [0, 5, 9]
    first = rows[0]
    assert first["n"] == 2 and first["mean_p"] == pytest.approx(0.065) and first["freq"] == pytest.approx(0.5)
    assert rows[2]["n"] == 2   # 1.0 belongs to the last decile, not to an eleventh


def test_max_decile_gap_in_points_ignoring_tiny_bins():
    rows = [{"bin": 1, "n": 40, "mean_p": 0.15, "freq": 0.20}, {"bin": 8, "n": 2, "mean_p": 0.85, "freq": 0.0}]
    assert max_decile_gap(rows, min_n=10) == pytest.approx(5.0)
    assert max_decile_gap(rows, min_n=100) is None
