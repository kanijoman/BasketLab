"""A comeback is told by what WE did, not by the run that started it (issue #516, feedback of the 0.3.3).

With a comeback inside the quarter the summary opened with «Remontada: de -12 a +12» and then said «Parcial en contra: -12», the same fall: the staff read the rival run and little of
our own. Now the key says our run (what went well) and the conceded run that is just the origin of the comeback is not said again; a fall AFTER the comeback still is.
"""
from tests.test_live_core_closing import OWN, RIVAL, by_id, end_of, engine, flat, pts


def run(team, start, n, step=20, value=2):
    return flat(*[pts(team, start + step * i, value) for i in range(n)])


def summary(period, log):
    [alert] = by_id(engine().evaluate(end_of(period, log)), "period_summary")
    return alert


def test_the_comeback_says_our_run_and_does_not_repeat_the_rival_run_that_started_it():
    # Q3 opens: the rival goes +12 (6 baskets) and we answer with +24 (12 baskets): -12 → +12 inside the quarter
    alert = summary(3, [run(RIVAL, 1210, 6, 40), run(OWN, 1500, 12, 20)])
    assert alert.evidence["keys"][0] == "comeback"
    assert "Remontada en el cuarto: de -12 a +12" in alert.message and "parcial propio de +24" in alert.message
    assert "collapse" not in alert.evidence["keys"] and "Parcial en contra" not in alert.message


def test_a_fall_after_the_comeback_is_still_a_key():
    log = [run(RIVAL, 1210, 6, 20), run(OWN, 1350, 12, 15), run(RIVAL, 1600, 7, 20)]      # -12 → +12 → +10 → ... the rival answers with 14 more
    alert = summary(3, log)
    assert "comeback" in alert.evidence["keys"] and "collapse" in alert.evidence["keys"]
    assert "Parcial en contra: -14" in alert.message


def test_the_rival_run_alone_without_a_comeback_is_said_as_before():
    alert = summary(2, [run(OWN, 650, 2, 20), run(RIVAL, 700, 7, 40), run(OWN, 1000, 1)])
    assert "collapse" in alert.evidence["keys"] and "Parcial en contra: -14" in alert.message and "comeback" not in alert.evidence["keys"]


def test_the_proposal_of_a_comeback_asks_to_repeat_what_made_it():
    alert = summary(3, [run(RIVAL, 1210, 6, 40), run(OWN, 1500, 12, 20)])
    assert any("Mantener lo que ha funcionado" in p["message"] or "Repetir" in p["message"] for p in alert.proposal)
