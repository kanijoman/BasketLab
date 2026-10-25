"""A run (parcial) does not cross the change of quarter (issue #515, feedback of the 0.3.3).

The staff read «parcial 1-9» 30 seconds into a quarter: it was a 1-7 of the previous quarter plus a rival basket. The windows of the run rules are cut at the start of the
period; a run inside the quarter is said as before.
"""
from src.live_core.advice import AdviceEngine
from tests.builders import OWN, RIVAL, snap


def evaluate(period, elapsed, log):
    return AdviceEngine(own_team_id=OWN, rival_team_id=RIVAL).evaluate(snap(elapsed=elapsed, period=period, log=log))


def by_id(alerts, alert_id):
    return [a for a in alerts if a.id == alert_id]


Q1_END = [[540, RIVAL, "pts", 3, "r1"], [570, RIVAL, "pts", 3, "r1"], [595, RIVAL, "pts", 3, "r1"]]       # 9 for the rival in the last minute of the 1st quarter


def test_a_rival_run_of_the_previous_quarter_does_not_add_to_the_first_baskets_of_the_next_one_regression():
    log = Q1_END + [[615, RIVAL, "pts", 2, "r1"]]
    assert not by_id(evaluate(2, 630, log), "rival_run")


def test_a_run_inside_the_quarter_is_said_as_always():
    log = [[610, RIVAL, "pts", 3, "r1"], [620, RIVAL, "pts", 3, "r1"], [628, RIVAL, "pts", 3, "r1"]]
    [alert] = by_id(evaluate(2, 630, log), "rival_run")
    assert alert.evidence["rival_points"] == 9 and alert.evidence["own_points"] == 0


def test_the_window_of_the_run_counts_from_the_start_of_the_quarter_not_before():
    log = Q1_END + [[610, RIVAL, "pts", 3, "r1"], [620, RIVAL, "pts", 3, "r1"], [628, OWN, "pts", 2, "p1"]]
    assert not by_id(evaluate(2, 630, log), "rival_run")                       # 6-2 inside the quarter: nothing to say yet
    log2 = Q1_END + [[610, RIVAL, "pts", 3, "r1"], [620, RIVAL, "pts", 3, "r1"], [625, RIVAL, "pts", 3, "r1"]]
    [alert] = by_id(evaluate(2, 630, log2), "rival_run")
    assert alert.evidence["rival_points"] == 9                                 # only the quarter's own 9, not the 18 of both quarters


def test_the_long_run_and_our_own_run_do_not_cross_the_quarter_either():
    long_log = [[300 + 20 * i, RIVAL, "pts", 2, "r1"] for i in range(14)]      # a long run of the rival that ends in the 1st quarter
    assert not by_id(evaluate(2, 610, long_log), "long_run")
    own = [[560, OWN, "pts", 3, "p1"], [575, OWN, "pts", 3, "p1"], [590, OWN, "pts", 3, "p1"]]
    assert not by_id(evaluate(2, 610, own), "own_run")
    assert by_id(evaluate(1, 600, own), "own_run")                             # the same points inside the quarter are a run for us


def test_overtime_starts_its_own_windows():
    log = [[2380, RIVAL, "pts", 3, "r1"], [2395, RIVAL, "pts", 3, "r1"], [2399, RIVAL, "pts", 3, "r1"]]
    assert not by_id(evaluate(5, 2410, log), "rival_run")
