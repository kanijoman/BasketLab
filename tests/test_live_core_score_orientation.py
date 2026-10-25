"""The score in the alerts reads like the scoreboard (feedback 0.4.0, #560): the local team first, and the header's score when the play-by-play disagrees.

Unicaja - León, 1st quarter: the scoreboard said 24-22 and the end-of-quarter notice said 22-26 (a scoring correction of the table left the log with other points
than the header). And the partial must read in the same direction as the game score, not always with our team first.
"""
import pytest

from src.live_core.advice import AdviceEngine
from src.live_core.score_text import score_text
from tests.builders import OWN, RIVAL
from tests.test_live_core_closing import by_id, end_of, flat, pts


def summary(period, log, header=None, home=None, elapsed_late=0):
    snapshot = end_of(period, [flat(*log)], remaining=0)
    if header:
        snapshot["score"] = dict(header)
    if home:
        snapshot["home_id"] = home
    snapshot["elapsed"] += elapsed_late
    [alert] = by_id(AdviceEngine(own_team_id=OWN, rival_team_id=RIVAL).evaluate(snapshot), "period_summary")
    return alert


# --- the text -----------------------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("home, expected", [
    (OWN, "24-22 (+2)"),                          # we are the local team: our points first, the difference as before
    (None, "24-22 (+2)"),                         # an old snapshot without the local team keeps our team first
    (RIVAL, "22-24 (+2 para nosotros)"),          # the local team is the rival: its points first, and the sign says whose it is
])
def test_the_score_text_goes_in_the_order_of_the_scoreboard(home, expected):
    assert score_text({"home_id": home} if home else {}, OWN, 24, 22) == expected


def test_a_difference_against_us_is_signed_for_us_in_both_orders():
    assert score_text({"home_id": OWN}, OWN, 20, 26) == "20-26 (-6)"
    assert score_text({"home_id": RIVAL}, OWN, 20, 26) == "26-20 (-6 para nosotros)"


# --- the summary ------------------------------------------------------------------------------------------------------------------------------

def test_the_summary_uses_the_score_of_the_header_when_the_log_disagrees_regression():
    """The log has 22-26 (a basket of the table was corrected afterwards) but FEB's header, what the staff sees on the scoreboard, says 24-22."""
    log = [pts(OWN, 100, 3), pts(RIVAL, 200, 3), pts(OWN, 300, 2), pts(RIVAL, 400, 3), pts(OWN, 450, 3)]       # 8-6 by the log; the header says 24-22
    alert = summary(1, log, header={OWN: 24, RIVAL: 22}, home=OWN)
    assert "marcador 24-22 (+2)" in alert.message and "1.er cuarto 24-22 (+2)" in alert.message
    assert alert.evidence["score"] == {"own": 24, "rival": 22}
    assert alert.evidence["log_score"] == {"own": 8, "rival": 6}            # what the log said, kept for the diagnosis


def test_the_summary_reads_like_the_scoreboard_when_the_rival_is_the_local_team():
    log = [pts(OWN, 100, 3), pts(RIVAL, 200, 3)]
    alert = summary(1, log, header={OWN: 22, RIVAL: 24}, home=RIVAL)
    assert "marcador 24-22 (+2 para nosotros)" not in alert.message          # 22 is ours: the local (rival) 24 goes first
    assert "marcador 24-22 (-2 para nosotros)" in alert.message


def test_a_header_that_is_still_zero_or_belongs_to_the_next_period_is_not_used():
    log = [pts(OWN, 100, 3), pts(RIVAL, 200, 2)]
    assert "marcador 3-2 (+1)" in summary(1, log, header={OWN: 0, RIVAL: 0}).message                       # no header yet (an old or minimal snapshot)
    late = summary(1, log, header={OWN: 9, RIVAL: 7}, elapsed_late=30)                                       # polled 30 s into the next period: its points are in the header
    assert "marcador 3-2 (+1)" in late.message


# --- the timeouts --------------------------------------------------------------------------------------------------------------------------

def timeout_alert(home, called_by=OWN):
    from tests.test_live_core_timeout_review import RIVAL_RUN, T, at, by_id as ids, engine
    snapshot = at(T + 10, RIVAL_RUN, own_timeouts=[T] if called_by == OWN else [], rival_timeouts=[T] if called_by == RIVAL else [], score={OWN: 17, RIVAL: 22})
    if home:
        snapshot["home_id"] = home
    [alert] = ids(engine().evaluate(snapshot), "timeout_review")
    return alert


def test_the_timeout_review_writes_the_game_and_the_run_in_the_order_of_the_scoreboard():
    own_home, rival_home = timeout_alert(OWN), timeout_alert(RIVAL)
    assert "(2.º cuarto" in own_home.message and "17-22): para cortar el parcial rival (0-9)" in own_home.message
    assert "22-17): para cortar el parcial rival (9-0)" in rival_home.message           # the local team (the rival) first in both numbers


def test_the_rival_run_also_reads_in_the_order_of_the_scoreboard():
    from tests.test_live_core_timeout_review import RIVAL_RUN, at, by_id as ids, engine
    snapshot = at(780, RIVAL_RUN, players={})
    [own_home] = ids(engine().evaluate(snapshot), "rival_run")
    snapshot["home_id"] = RIVAL
    [rival_home] = ids(engine().evaluate(snapshot), "rival_run")
    assert "Parcial de 0-9 en contra" in own_home.message and "Parcial de 9-0 en contra" in rival_home.message
