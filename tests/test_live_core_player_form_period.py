"""A player's streak does not cross the change of quarter (feedback 0.4.2, same family as #515).

Cultural–Melilla: «D. Bulto lleva 7 puntos consecutivos en los últimos 2:30» came at the start of the 2nd quarter, when most of those points were of the 1st. The window of a
player's form is cut at the start of the period, like the run windows; a streak inside the quarter is said as before.
"""
import pytest

from src.live_core.clock import period_start
from tests.builders import OWN, RIVAL, Match


def by_id(alerts, alert_id):
    return [a for a in alerts if a.id == alert_id]


def q1_closing_streak(team, player):
    """7 points in a row of ``player`` in the last minute of the 1st quarter (3 baskets: 3 + 2 + 2)."""
    m = Match()
    m.lineup(OWN, ["p1"], at=0).lineup(RIVAL, ["r1"], at=0)
    return m.score(team, 3, at=540, player=player).score(team, 2, at=565, player=player).score(team, 2, at=590, player=player)


@pytest.mark.parametrize("team, player, alert_id", [(RIVAL, "r1", "rival_hot_run"), (OWN, "p1", "own_hot_player")])
def test_a_streak_of_the_previous_quarter_is_not_said_at_the_start_of_the_next_one_regression(team, player, alert_id):
    m = q1_closing_streak(team, player)
    assert by_id(m.evaluate(), alert_id), "inside the quarter the streak is said"          # the 1st quarter, 10 s after the last basket
    m.period_end(1)
    m.turnover(OWN, at=period_start(2) + 20)
    assert not by_id(m.evaluate(), alert_id)


def test_the_streak_counts_the_points_of_the_new_quarter_only():
    m = q1_closing_streak(RIVAL, "r1")
    m.period_end(1)
    start = period_start(2)
    m.score(RIVAL, 2, at=start + 20, player="r1").score(RIVAL, 3, at=start + 40, player="r1").score(RIVAL, 2, at=start + 60, player="r1")
    [hot] = by_id(m.evaluate(), "rival_hot_run")
    assert hot.evidence["pts"] == 7 and hot.evidence["made_in_row"] == 3
