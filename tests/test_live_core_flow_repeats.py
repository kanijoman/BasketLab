"""A flow alert counts only what is new since it was last said (issue #517, feedback of the 0.3.3).

Cultural–Melilla, 1st quarter: «El rival suma 4 pérdidas en los últimos 3 min» came twice within a minute. The alert is keyed by the stretch since the timeout of the team, so a
timeout (the rival's, here) opened a new stretch while the window still held the SAME four turnovers. The window now starts where the last alert of that kind ended.
"""
from src.live_core.advice import AdviceEngine
from tests.builders import OWN, RIVAL, snap


def run(eng, elapsed, log, rival_timeouts=(), own_timeouts=()):
    s = snap(elapsed=elapsed, period=1, log=log)
    s["remaining"] = 600 - elapsed
    s["teams"][RIVAL]["timeouts"] = list(rival_timeouts)
    s["teams"][OWN]["timeouts"] = list(own_timeouts)
    return eng.evaluate(s)


def by_id(alerts, alert_id):
    return [a for a in alerts if a.id == alert_id]


def engine():
    return AdviceEngine(own_team_id=OWN, rival_team_id=RIVAL)


TOV4 = [[100 + 20 * i, RIVAL, "tov", 1, "r1"] for i in range(4)]          # four turnovers of the rival between 1:40 and 2:40


def test_a_timeout_does_not_make_the_same_four_turnovers_count_again_regression():
    e = engine()
    assert by_id(run(e, 165, TOV4), "rival_turnovers")
    assert not by_id(run(e, 200, TOV4, rival_timeouts=[185]), "rival_turnovers")      # a new stretch, but the same turnovers


def test_four_new_turnovers_after_the_timeout_are_a_new_alert():
    e = engine()
    assert by_id(run(e, 165, TOV4), "rival_turnovers")
    more = TOV4 + [[260 + 10 * i, RIVAL, "tov", 1, "r1"] for i in range(4)]
    [alert] = by_id(run(e, 300, more, rival_timeouts=[185]), "rival_turnovers")
    assert alert.evidence["turnovers"] == 4


def test_the_offensive_rebounds_of_the_rival_are_not_counted_twice_either():
    e = engine()
    orbs = [[100 + 15 * i, RIVAL, "orb", 1, "r1"] for i in range(3)]
    assert by_id(run(e, 150, orbs), "rival_orb_window")
    assert not by_id(run(e, 190, orbs, own_timeouts=[170]), "rival_orb_window")


def test_what_was_said_in_one_period_does_not_hide_a_new_problem_in_the_next():
    e = engine()
    assert by_id(run(e, 165, TOV4), "rival_turnovers")
    s = snap(elapsed=900, period=2, log=TOV4 + [[800 + 10 * i, RIVAL, "tov", 1, "r1"] for i in range(4)])
    s["remaining"] = 300
    assert by_id(e.evaluate(s), "rival_turnovers")
