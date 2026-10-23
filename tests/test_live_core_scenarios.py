"""Scenarios played through the real state machine (issue #543): the same bugs that were found with real matches, now as tests that can only be in reachable states.

Each one mirrors a regression test written with hand-made snapshots (``test_live_core_runs_period``, ``..._flow_repeats``, ``..._summary_comeback``, ``..._timeout_review``):
what is new is that the clock, the periods, the log, the stints and the timeouts come from ``LiveGame``, not from numbers typed in the test.
"""
from tests.builders import OWN, RIVAL, Match


def by_id(alerts, alert_id):
    return [a for a in alerts if a.id == alert_id]


def test_a_rival_run_at_the_end_of_a_quarter_is_not_added_to_the_first_baskets_of_the_next_one():
    match = Match()
    for at in (540, 570, 595):
        match.score(RIVAL, 3, at=at)                               # 0-9 in the last minute of the 1st quarter
    match.period_end(1).score(RIVAL, 2, at=615)
    assert not by_id(match.evaluate(), "rival_run")                # 2 points of the 2nd quarter: not a run of 11


def test_the_same_four_turnovers_are_not_counted_again_after_a_timeout_of_the_rival():
    match = Match()
    engine = match.engine()
    said = []
    for at in (100, 120, 140, 160):
        match.turnover(RIVAL, at=at)
        said += by_id(engine.evaluate(match.snapshot()), "rival_turnovers")
    match.timeout(RIVAL, at=185)
    said += by_id(engine.evaluate(match.snapshot()), "rival_turnovers")
    match.score(OWN, 2, at=200)
    said += by_id(engine.evaluate(match.snapshot()), "rival_turnovers")
    assert len(said) == 1 and said[0].evidence["turnovers"] == 4


def test_a_comeback_in_a_quarter_is_told_by_our_run_and_the_rival_run_that_started_it_is_not_said_again():
    match = Match()
    for at in range(1210, 1330, 20):
        match.score(RIVAL, 2, at=at)                               # -12 at the start of the 3rd quarter
    for at in range(1350, 1350 + 12 * 15, 15):
        match.score(OWN, 2, at=at)                                 # +24 for us: +12 at the end
    summary = by_id(match.period_end(3).evaluate(), "period_summary")[0]
    assert "Remontada en el cuarto: de -12 a +12 (parcial propio de +24)" in summary.message
    assert "Parcial en contra" not in summary.message


def test_a_player_who_has_not_come_off_for_fifteen_minutes_is_the_reason_of_the_timeout_and_he_is_named():
    """The fatigue is not a number written in the snapshot: it comes from a stint that the substitutions of the match built."""
    match = Match().lineup(OWN, ["Ana", "Bea", "Cora", "Dora", "Eva"], at=0).lineup(RIVAL, ["r1", "r2", "r3", "r4", "r5"], at=0)
    match.score(OWN, 2, at=700, player="Bea").score(RIVAL, 2, at=760, player="r1").score(OWN, 2, at=820, player="Ana").score(RIVAL, 2, at=860, player="r2")
    match.timeout(OWN, at=900)
    [review] = by_id(match.evaluate(), "timeout_review")
    assert review.evidence["reason"] == "fatigue" and "Ana" in review.message


def test_a_timeout_right_after_a_period_has_closed_belongs_to_the_next_period_and_looks_at_the_new_one_only():
    """The corner that my first hand-made tests got wrong: a timeout at second 1200 is the 3rd quarter's, and its window does not reach back into the 2nd."""
    match = Match()
    for at in (1100, 1130, 1160, 1190):
        match.score(RIVAL, 2, at=at)
    match.period_end(2).timeout(OWN, at=1200)
    [review] = by_id(match.evaluate(), "timeout_review")
    assert review.evidence["reason"] != "run" and review.evidence["rival_points"] == 0
