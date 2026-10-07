"""Game clock helpers. FEB reports the time REMAINING in the period ("mm:ss");
periods 1-4 last 10 minutes, overtimes 5."""

import pytest

from src.live_core.clock import elapsed_seconds, parse_clock, period_length, period_start


@pytest.mark.parametrize("period, expected", [(1, 600), (2, 600), (4, 600), (5, 300), (6, 300)])
def test_period_length(period, expected):
    assert period_length(period) == expected


@pytest.mark.parametrize("period, expected", [(1, 0), (2, 600), (4, 1800), (5, 2400), (6, 2700)])
def test_period_start(period, expected):
    assert period_start(period) == expected


@pytest.mark.parametrize("text, expected", [("10:00", 600), ("00:33", 33), ("05:48", 348), ("0:05", 5)])
def test_parse_clock(text, expected):
    assert parse_clock(text) == expected


@pytest.mark.parametrize("bad", [None, "", "FINAL", "ab:cd", "10"])
def test_parse_clock_invalid_returns_none(bad):
    assert parse_clock(bad) is None


@pytest.mark.parametrize(
    "period, remaining, expected",
    [(1, 600, 0), (1, 0, 600), (2, 600, 600), (4, 33, 2367), (5, 300, 2400), (5, 0, 2700)],
)
def test_elapsed_seconds(period, remaining, expected):
    assert elapsed_seconds(period, remaining) == expected
