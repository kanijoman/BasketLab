"""The turnover alerts do not cross the change of quarter (feedback of the 0.5.2, Valencia Basket–León, 2524501).

The staff read «5 pérdidas propias en los últimos 5 min» 1:40 into the 3rd quarter: three of them were León's at the end of the 2nd quarter (6:52, 7:31 and 7:54)
and two of the 3rd (0:52 and 1:18), with the half-time break in between. The runs were already cut at the start of the period (#515); the own turnover streak and the
flow windows of the last 3 minutes (rival offensive rebounds, points after our turnovers, rival turnovers) are cut the same way now, and when the quarter is younger than
the window the alert says the span it really counted.
"""
from tests.builders import OWN, RIVAL, Match


def by_id(alerts, alert_id):
    return [a for a in alerts if a.id == alert_id]


def leon_valencia_to(at):
    """The turnovers of the own team around the half of 2524501, at their real game seconds (the scores keep the play realistic)."""
    m = Match().lineup(OWN, ["p1", "p2", "p3", "p4", "p5"]).lineup(RIVAL, ["r1", "r2", "r3", "r4", "r5"])
    m.score(OWN, 2, at=900).score(RIVAL, 2, at=930)
    for second, player in ((1012, "p1"), (1051, "p2"), (1074, "p3")):
        m.turnover(OWN, at=second, player=player)
    m.period_end(2)
    for second, player in ((1252, "p4"), (1278, "p1")):
        if second <= at:
            m.turnover(OWN, at=second, player=player)
    return m


def test_turnovers_of_the_previous_quarter_do_not_make_a_streak_in_the_next_one_regression():
    assert not by_id(leon_valencia_to(1300).evaluate(), "turnover_streak")


def test_five_turnovers_inside_the_quarter_are_a_streak_said_with_the_span_it_counted():
    m = Match().lineup(OWN, ["p1", "p2", "p3", "p4", "p5"]).lineup(RIVAL, ["r1", "r2", "r3", "r4", "r5"]).period_end(2)
    for i, player in enumerate(["p1", "p2", "p3", "p4", "p5"]):
        m.turnover(OWN, at=1210 + 18 * i, player=player)
    m.score(RIVAL, 2, at=1300)
    [alert] = by_id(m.evaluate(), "turnover_streak")
    assert alert.evidence["turnovers"] == 5 and alert.evidence["window_s"] == 100
    assert "1:40" in alert.message and "5 min" not in alert.message


def test_a_streak_in_the_middle_of_a_quarter_still_counts_the_last_five_minutes():
    m = Match().lineup(OWN, ["p1", "p2", "p3", "p4", "p5"]).lineup(RIVAL, ["r1", "r2", "r3", "r4", "r5"])
    for i, player in enumerate(["p1", "p2", "p3", "p4", "p5"]):
        m.turnover(OWN, at=200 + 40 * i, player=player)
    [alert] = by_id(m.evaluate(), "turnover_streak")
    assert alert.evidence["window_s"] == 300 and "en los últimos 5 min" in alert.message


def test_the_flow_windows_of_the_last_minutes_do_not_cross_the_quarter_either():
    m = Match().lineup(OWN, ["p1", "p2", "p3", "p4", "p5"]).lineup(RIVAL, ["r1", "r2", "r3", "r4", "r5"])
    for second in (1140, 1160, 1180):
        m.turnover(RIVAL, at=second)                                  # three rival turnovers in the last minute of the 2nd quarter
    m.period_end(2).turnover(RIVAL, at=1215)                          # and one 15 s into the 3rd
    assert not by_id(m.evaluate(), "rival_turnovers")
    m.turnover(RIVAL, at=1230).turnover(RIVAL, at=1245).turnover(RIVAL, at=1260)
    [alert] = by_id(m.evaluate(), "rival_turnovers")
    assert alert.evidence["turnovers"] == 4 and "1:00" in alert.message
