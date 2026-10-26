"""The radar of the individual scouting report with a player who lacks a figure (reported 26/10/2026):
«Radar chart generation failed: unsupported operand type(s) for -: 'NoneType' and 'float'».

A player without attempts of a kind (or without minutes) has ``None`` where the rest have a number. A missing figure is not zero (zero turnovers would look like the best of the league):
the bar sits on the league average, which says «no data», and the chart is drawn.
"""
import matplotlib

matplotlib.use("Agg")

import pytest  # noqa: E402

from src.visualization.radar_chart import RadarChart  # noqa: E402


def stats(**over):
    base = dict(games_played=10, total_minutes=6000, ts=55.0, total_p3m=20, total_p3a=60, total_p2m=60, total_p2a=110, total_p1m=30, total_p1a=40,
                ast_pct=15.0, tov_pct=12.0, stl_pct=2.0, blk_pct=1.0, drb_pct=18.0, drating=102.0, total_assist=40, total_to=25,
                three_pr=30.0, ftr=25.0, usage=22.0)
    base.update(over)
    return base


def league(radar, n=8):
    return [radar.calculate_metrics_from_stats(stats(ts=45 + i * 2, tov_pct=8 + i, ast_pct=10 + i)) for i in range(n)]


def test_a_player_with_a_missing_figure_still_gets_a_chart_regression():
    radar = RadarChart(figsize=(6, 5))
    player = radar.calculate_metrics_from_stats(stats(ts=None, tov_pct=None, drating=None))
    fig = radar.create_chart(player, league(radar), "Jugadora sin datos")
    assert fig is not None


def test_a_missing_figure_is_drawn_on_the_league_average_not_at_zero_or_as_the_best():
    radar = RadarChart(figsize=(6, 5))
    values, averages = radar.normalize_values({"ts": None, "tov_pct": None}, league(radar))
    for metric in ("TS%", "TO%"):
        i = radar.all_metrics.index(metric)
        assert values[i] == pytest.approx(averages[i])            # neutral, also for «lower is better» metrics


def test_figures_that_are_there_keep_being_normalised_as_before():
    radar = RadarChart(figsize=(6, 5))
    pool = league(radar)
    best = max(pool, key=lambda m: m["ts"])
    values, _ = radar.normalize_values(best, pool)
    assert values[radar.all_metrics.index("TS%")] == pytest.approx(100)


def test_raw_stats_with_none_in_the_counters_do_not_break_the_metrics():
    radar = RadarChart(figsize=(6, 5))
    metrics = radar.calculate_metrics_from_stats(stats(total_minutes=None, total_p3a=None, total_assist=None, total_to=None, usage=None))
    assert isinstance(metrics, dict) and metrics["fg3_pct"] is None and metrics["fg2_pct"] > 0
