"""FIBA timeout budget and the "since the last timeout" helpers (issue #239).

FIBA: 2 timeouts in the first half, 3 in the second (at most 2 of them in the last 2:00 of the 4th period) and 1 per
overtime; unused ones are not carried over. The snapshot only keeps the game-seconds of each timeout, so the period of
each is derived from the clock (a timeout at the very second a period opens counts for the new period).
"""
import pytest

from src.live_core.clock import elapsed_seconds, period_start
from src.live_core.timeouts import episode, last_timeout, timeout_within, timeouts_left

OWN, RIVAL = "T1", "T2"


def at(period, remaining):
    return elapsed_seconds(period, remaining)


def mk(period, remaining, own=(), rival=()):
    """A snapshot at ``period`` with ``remaining`` seconds left; timeouts given as (period, remaining) pairs."""
    stamp = lambda pairs: [at(p, r) for p, r in pairs]  # noqa: E731
    team = lambda timeouts: {"name": "x", "fouls_game": 0, "timeouts": timeouts, "fouls_by_period": {}, "stats": {}}  # noqa: E731
    return {"period": period, "remaining": remaining, "elapsed": at(period, remaining), "score": {OWN: 0, RIVAL: 0},
            "teams": {OWN: team(stamp(own)), RIVAL: team(stamp(rival))}, "players": {}, "log": []}


# --- budget -------------------------------------------------------------------------------

def test_first_half_has_two():
    assert timeouts_left(mk(1, 600), OWN) == 2
    assert timeouts_left(mk(2, 100, own=[(1, 300)]), OWN) == 1
    assert timeouts_left(mk(2, 100, own=[(1, 300), (2, 400)]), OWN) == 0


def test_second_half_has_three_whatever_was_used_before():
    assert timeouts_left(mk(3, 600, own=[(1, 300), (2, 400)]), OWN) == 3     # nothing carries over, nothing is lost
    assert timeouts_left(mk(3, 300, own=[(3, 400)]), OWN) == 2
    assert timeouts_left(mk(4, 500, own=[(3, 400), (4, 550)]), OWN) == 1


def test_the_last_two_minutes_of_the_fourth_period_allow_at_most_two():
    assert timeouts_left(mk(4, 130), OWN) == 3                          # still before the last 2:00
    assert timeouts_left(mk(4, 120), OWN) == 2                          # inside it: 3 left, 2 usable
    assert timeouts_left(mk(4, 60, own=[(4, 110)]), OWN) == 1           # one used in the last 2:00 -> one more
    assert timeouts_left(mk(4, 60, own=[(4, 110), (4, 90)]), OWN) == 0  # two used in the last 2:00 -> none, even with one left
    assert timeouts_left(mk(4, 60, own=[(3, 300), (4, 500)]), OWN) == 1


def test_one_per_overtime_and_it_is_not_carried_over():
    assert timeouts_left(mk(5, 300), OWN) == 1
    assert timeouts_left(mk(5, 100, own=[(5, 200)]), OWN) == 0
    assert timeouts_left(mk(6, 300, own=[(5, 200)]), OWN) == 1          # the second overtime starts again
    assert timeouts_left(mk(5, 300, own=[(3, 300), (4, 500)]), OWN) == 1  # regulation timeouts do not count in overtime


def test_each_team_has_its_own_budget_and_data_never_gives_a_negative_number():
    snap = mk(2, 300, own=[(1, 500), (2, 550)], rival=[(1, 400)])
    assert (timeouts_left(snap, OWN), timeouts_left(snap, RIVAL)) == (0, 1)
    assert timeouts_left(mk(2, 300, own=[(1, 500), (1, 400), (2, 550)]), OWN) == 0   # three in a half: FEB data glitch


def test_a_team_the_snapshot_does_not_know_has_a_full_budget_and_nothing_to_report():
    snap = mk(3, 400)
    assert timeouts_left(snap, "nobody") == 3
    assert timeouts_left(snap, None) == 3
    assert last_timeout(snap, "nobody") is None and not timeout_within(snap, "nobody", 60)


# --- last timeout -------------------------------------------------------------------------

def test_last_timeout_is_the_latest_of_the_team_up_to_now():
    snap = mk(3, 300, own=[(1, 300), (3, 500)], rival=[(3, 400)])
    assert last_timeout(snap, OWN) == at(3, 500)
    assert last_timeout(snap, RIVAL) == at(3, 400)
    assert last_timeout(mk(3, 300), OWN) is None


def test_a_timeout_after_the_snapshot_clock_is_ignored():
    snap = mk(3, 300, own=[(3, 500), (3, 200)])      # the second one has not happened yet at this clock
    assert last_timeout(snap, OWN) == at(3, 500)


@pytest.mark.parametrize("remaining,expected", [(480, True), (440, True), (439, False)])
def test_just_called_means_within_the_given_seconds(remaining, expected):
    snap = mk(3, remaining, own=[(3, 500)])          # called at 8:20; 60 s later is 7:20 = 440
    assert timeout_within(snap, OWN, 60) is expected


def test_the_rival_timeout_is_not_ours():
    assert not timeout_within(mk(3, 480, rival=[(3, 500)]), OWN, 60)


# --- episode ------------------------------------------------------------------------------

def test_an_episode_starts_with_the_period_or_with_our_last_timeout_in_it():
    assert episode(mk(3, 400), OWN) == f"3:{period_start(3)}"
    assert episode(mk(3, 400, own=[(3, 500)]), OWN) == f"3:{at(3, 500)}"
    assert episode(mk(4, 400, own=[(3, 500)]), OWN) == f"4:{period_start(4)}"      # a timeout of the previous period does not count
    assert episode(mk(3, 400, rival=[(3, 500)]), OWN) == f"3:{period_start(3)}"    # the rival's timeout does not restart ours


def test_the_episode_changes_when_a_new_timeout_is_called():
    before, after = mk(3, 400, own=[(3, 500)]), mk(3, 300, own=[(3, 500), (3, 350)])
    assert episode(before, OWN) != episode(after, OWN)
