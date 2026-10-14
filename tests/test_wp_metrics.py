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


# -- bootstrap by game (issue #261): is a decile gap distinguishable from zero? ----------------------------------

import random

from src.live_prep.wp_metrics import bootstrap_reliability


def _games(n_games, p, freq, cuts=1, seed=1):
    """``n_games`` games each with ``cuts`` cuts of forecast ``p`` whose outcome happens with probability ``freq``."""
    rng = random.Random(seed)
    ps, ys, games = [], [], []
    for g in range(n_games):
        outcome = int(rng.random() < freq)
        for _ in range(cuts):
            ps.append(p)
            ys.append(outcome)
            games.append(f"g{g}")
    return ps, ys, games


def test_a_calibrated_forecast_has_an_interval_around_zero():
    ps, ys, games = _games(600, 0.35, 0.35)
    [row] = bootstrap_reliability(ps, ys, games, resamples=300, seed=0)
    assert row["bin"] == 3 and row["n"] == 600
    assert row["lo"] < 0 < row["hi"]
    assert abs(row["gap"]) < 5


def test_a_biased_forecast_has_an_interval_that_excludes_zero():
    ps, ys, games = _games(600, 0.35, 0.50)
    [row] = bootstrap_reliability(ps, ys, games, resamples=300, seed=0)
    assert row["gap"] == pytest.approx(15, abs=5) and row["lo"] > 0


def test_gap_is_frequency_minus_forecast_in_points():
    [row] = bootstrap_reliability([0.35, 0.35], [1, 0], ["a", "b"], resamples=50, seed=0)
    assert row["gap"] == pytest.approx(15.0)
    assert row["freq"] == pytest.approx(0.5) and row["mean_p"] == pytest.approx(0.35)


def test_cuts_of_one_game_count_as_one_game_so_the_interval_is_wider():
    """Resampling whole games respects that the cuts of a game share the outcome."""
    one_each = bootstrap_reliability(*_games(200, 0.35, 0.35, cuts=1, seed=3), resamples=300, seed=0)[0]
    seven_each = bootstrap_reliability(*_games(200, 0.35, 0.35, cuts=7, seed=3), resamples=300, seed=0)[0]
    assert seven_each["n"] == 1400 and one_each["n"] == 200
    assert (seven_each["hi"] - seven_each["lo"]) == pytest.approx(one_each["hi"] - one_each["lo"], rel=0.35)   # same games: same width


def test_it_is_deterministic_for_a_seed_and_empty_input_is_empty():
    data = _games(100, 0.65, 0.6)
    assert bootstrap_reliability(*data, resamples=100, seed=7) == bootstrap_reliability(*data, resamples=100, seed=7)
    assert bootstrap_reliability([], [], [], resamples=10, seed=0) == []
