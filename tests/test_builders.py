"""The match builder of the tests (issue #543): it plays events through the real state machine, so a test can only be in a state the engine can reach.

Hand-written snapshot dicts (``snap``) can describe impossible states (a timeout in the middle of two periods, a rebound with nothing missed). The builder refuses them.
"""
import pytest

from tests.builders import OWN, RIVAL, Match


def test_the_period_and_the_clock_come_from_the_second_not_from_the_test():
    snapshot = Match().score(OWN, 2, at=650).snapshot()
    assert (snapshot["period"], snapshot["remaining"], snapshot["elapsed"]) == (2, 550, 650)
    assert snapshot["score"] == {OWN: 2, RIVAL: 0}


def test_a_made_basket_is_in_the_score_the_log_and_the_ball_of_the_state_machine():
    snapshot = Match().score(OWN, 3, at=100, player="p1").score(RIVAL, 2, at=120).snapshot()
    assert snapshot["score"] == {OWN: 3, RIVAL: 2}
    assert [e[:4] for e in snapshot["log"] if e[2] == "pts"] == [[100, OWN, "pts", 3], [120, RIVAL, "pts", 2]]
    assert snapshot["ball"]["team_id"] == OWN                      # the rival scored: the ball goes to us


def test_time_never_goes_back_because_a_feed_never_does():
    match = Match().score(OWN, 2, at=100)
    with pytest.raises(ValueError, match="atrás|backwards|back"):
        match.score(RIVAL, 2, at=90)


def test_a_rebound_needs_a_missed_shot_before_it():
    with pytest.raises(ValueError, match="rebote|rebound"):
        Match().rebound(OWN, at=100)
    snapshot = Match().miss(RIVAL, at=100).rebound(OWN, at=105).snapshot()
    assert any(e[2] == "orb" or e[2] == "drb" for e in snapshot["log"]) or snapshot["ball"]["team_id"] == OWN


def test_an_unknown_team_is_an_error_not_a_silent_third_team():
    with pytest.raises(ValueError, match="equipo|team"):
        Match().score("T3", 2, at=10)


def test_a_timeout_is_in_the_team_and_in_the_log_like_the_engine_writes_it():
    snapshot = Match().score(RIVAL, 2, at=300).timeout(OWN, at=310).snapshot()
    assert snapshot["teams"][OWN]["timeouts"] == [310]
    assert [310, OWN, "timeout", 1, None] in snapshot["log"]


def test_a_lineup_puts_five_players_on_court_and_a_substitution_changes_it():
    match = Match().lineup(OWN, ["p1", "p2", "p3", "p4", "p5"], at=0)
    on_court = {pid for pid, p in match.snapshot()["players"].items() if p["on_court"] and p["team_id"] == OWN}
    assert on_court == {"p1", "p2", "p3", "p4", "p5"}
    match.substitution(OWN, out="p5", into="p6", at=200)
    on_court = {pid for pid, p in match.snapshot()["players"].items() if p["on_court"] and p["team_id"] == OWN}
    assert on_court == {"p1", "p2", "p3", "p4", "p6"}


def test_evaluate_runs_the_real_alert_engine_over_the_state():
    """A run of the rival of 9-0 in the two minutes before our timeout: the state is built by playing it."""
    match = Match()
    for at, points in ((1100, 2), (1130, 3), (1160, 2), (1190, 2)):
        match.score(RIVAL, points, at=at)
    match.timeout(OWN, at=1195)
    alerts = {a.id: a for a in match.evaluate()}
    assert alerts["timeout_review"].evidence["reason"] == "run"


def test_the_evaluation_can_be_repeated_as_the_match_goes_on():
    """The same engine keeps its memory between evaluations, as in the app: a timeout is reviewed once."""
    match = Match().score(RIVAL, 2, at=100).timeout(OWN, at=150)
    engine = match.engine()
    first = [a.id for a in engine.evaluate(match.snapshot())]
    second = [a.id for a in engine.evaluate(match.snapshot())]
    assert "timeout_review" in first and "timeout_review" not in second


def test_a_period_can_be_closed_with_its_end_event_as_the_summary_of_the_quarter_needs():
    match = Match().score(OWN, 2, at=100).period_end(1)
    snapshot = match.snapshot()
    assert (snapshot["period"], snapshot["remaining"], snapshot["elapsed"]) == (1, 0, 600)
    with pytest.raises(ValueError):
        match.score(OWN, 2, at=500)          # the clock does not go back into the closed quarter
