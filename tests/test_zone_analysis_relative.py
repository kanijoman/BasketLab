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
    """``league`` is the shots of each entity (team or player) of the competition."""
    stats = az.analyze_zone_performance(own)
    entities = [az.analyze_zone_performance(shots)["zone_stats"] for shots in league] if league is not None else None
    fig = az.plot_zone_analysis(stats, title="t", league_stats=entities)
    try:
        return _fills(fig)
    finally:
        plt.close(fig)


# eight entities shooting 40, 42, … 54 % in the restricted area: the quartiles are 43 and 51 %
COMPETITION = [_shots(100, 40 + 2 * i) for i in range(8)]


def test_zone_above_the_upper_quartile_of_the_competition_is_green(az):
    fills = _plot(az, _shots(100, 70), league=COMPETITION)
    assert RATING_COLORS["above"].lower() in fills
    assert RATING_COLORS["below"].lower() not in fills


def test_zone_below_the_lower_quartile_is_red(az):
    fills = _plot(az, _shots(100, 20), league=COMPETITION)
    assert RATING_COLORS["below"].lower() in fills


def test_zone_between_the_quartiles_is_neutral(az):
    fills = _plot(az, _shots(100, 47), league=COMPETITION)
    assert RATING_COLORS["average"].lower() in fills
    assert RATING_COLORS["above"].lower() not in fills and RATING_COLORS["below"].lower() not in fills


def test_a_fixed_percentage_no_longer_decides_the_colour(az):
    """40 % is 'excellent' for the old static 2PT thresholds, and in a competition where everybody shoots 40 % it is average."""
    fills = _plot(az, _shots(100, 40), league=[_shots(100, 40)] * 6)
    assert RATING_COLORS["above"].lower() not in fills


def test_a_shot_sample_of_one_does_not_move_the_quartiles(az):
    """No minimum of shots (#760): a single-shot entity at 100 % weighs one shot among hundreds."""
    fills = _plot(az, _shots(100, 47), league=COMPETITION + [_shots(1, 1)])
    assert RATING_COLORS["average"].lower() in fills and RATING_COLORS["below"].lower() not in fills


def test_without_league_stats_the_legacy_static_colouring_is_kept(az):
    fills = _plot(az, _shots(100, 80))
    assert not fills & {c.lower() for c in RATING_COLORS.values()}
