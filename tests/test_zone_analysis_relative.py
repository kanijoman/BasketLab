"""ZoneAnalyzer PNG colouring relative to the league average per zone (issue #139)."""
from unittest.mock import MagicMock

import matplotlib

matplotlib.use("Agg")

import matplotlib.colors as mcolors  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import pytest  # noqa: E402

from src.shotcharts.zone_analysis import RATING_COLORS, ZoneAnalyzer  # noqa: E402


def _shots(n, made):
    """n shots next to the basket (restricted area), ``made`` of them scored."""
    return [{"x": 7.5, "y": 1.2, "made": i < made} for i in range(n)]


def _fills(fig):
    return {mcolors.to_hex(p.get_facecolor()).lower() for p in fig.axes[0].patches}


@pytest.fixture(scope="module")
def az():
    return ZoneAnalyzer()


def _plot(az, own, league=None):
    stats = az.analyze_zone_performance(own)
    league_stats = az.analyze_zone_performance(league)["zone_stats"] if league is not None else None
    fig = az.plot_zone_analysis(stats, title="t", league_stats=league_stats)
    try:
        return _fills(fig)
    finally:
        plt.close(fig)


def test_zone_above_league_is_green(az):
    fills = _plot(az, _shots(100, 80), league=_shots(1000, 400))
    assert RATING_COLORS["above"].lower() in fills
    assert RATING_COLORS["below"].lower() not in fills


def test_zone_below_league_is_red(az):
    fills = _plot(az, _shots(100, 20), league=_shots(1000, 400))
    assert RATING_COLORS["below"].lower() in fills


def test_zone_close_to_league_is_neutral(az):
    fills = _plot(az, _shots(100, 41), league=_shots(1000, 400))
    assert RATING_COLORS["average"].lower() in fills
    assert RATING_COLORS["above"].lower() not in fills


def test_a_fixed_percentage_no_longer_decides_the_colour(az):
    """40 % is 'excellent' for the old static 2PT thresholds but average vs a 40 % league."""
    fills = _plot(az, _shots(100, 40), league=_shots(1000, 400))
    assert RATING_COLORS["above"].lower() not in fills


def test_without_league_stats_the_legacy_static_colouring_is_kept(az):
    fills = _plot(az, _shots(100, 80))
    assert not fills & {c.lower() for c in RATING_COLORS.values()}


def test_league_helper_builds_zone_stats_from_a_collection(az):
    from src.shotcharts.league_zones import league_zone_stats

    coll = MagicMock()
    docs = [{"HEADER": {"TEAM": [{"id": "1"}, {"id": "2"}]},
             "SHOTCHART": {"SHOTS": [{"team": "0", "x": 3, "y": 50, "m": 1, "player": "4"}]}}]
    coll.find.return_value = iter(docs)
    stats = league_zone_stats(az, coll)
    assert sum(z["total"] for z in stats.values()) == 1


def test_league_helper_returns_none_on_failure(az):
    from src.shotcharts.league_zones import league_zone_stats

    coll = MagicMock()
    coll.find.side_effect = RuntimeError("db down")
    assert league_zone_stats(az, coll) is None
