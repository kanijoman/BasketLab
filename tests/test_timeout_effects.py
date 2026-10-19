"""What happens around the timeouts of a game, per team (#355): the possessions before and after each one.

For every timeout both teams get an entry (``caller`` = ``own`` for the team that called it, ``rival`` for the other) with the
points, possessions and turnovers of both teams in the ``window`` possessions of each team before and after it, inside the
same period. Left out: timeouts in the last minute of a period (preparation of a play, not a change of momentum; they still
count as after-timeout possessions, #354) and the ones without a complete window on either side.
"""
import pytest

from src.live_core.possessions import track
from src.pbp.game_derived import derive_game_fields
from src.pbp.timeout_effects import TM_LAST_MINUTE_S, TM_WINDOW_POSSESSIONS, timeout_effects
from tests.test_live_core_possessions import _Feed, _events
from tests.test_points_by_origin import _game


def _clock(seconds):
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


def _feed(tm_team="B", tm_at=300, before=4, after=4, step=10):
    """Alternating baskets A, B, A, B...: before the timeout A scores 3 and B 2; after it A scores 2 and B 3."""
    feed = _Feed()
    for k in range(before):
        feed.made("AB"[k % 2], _clock(tm_at + step * (before - k)), 3 if k % 2 == 0 else 2, "p1" if k % 2 == 0 else "s")
    feed.timeout(tm_team, _clock(tm_at))
    for k in range(after):
        feed.made("AB"[k % 2], _clock(tm_at - step * (k + 1)), 2 if k % 2 == 0 else 3, "p1" if k % 2 == 0 else "s")
    return feed


def _effects(feed, window=2):
    possessions, _ = track(_events(feed.lines), ["A", "B"])
    return timeout_effects(possessions, ["A", "B"], window=window)


def test_both_teams_get_an_entry_with_the_window_before_and_after():
    out = _effects(_feed("B"))
    b, a = out["B"][0], out["A"][0]

    assert (b["caller"], a["caller"]) == ("own", "rival")
    assert (b["pre"]["pts"], b["pre"]["opp_pts"], b["post"]["pts"], b["post"]["opp_pts"]) == (4, 6, 6, 4)
    assert (a["pre"]["pts"], a["pre"]["opp_pts"], a["post"]["pts"], a["post"]["opp_pts"]) == (6, 4, 4, 6)
    assert (b["pre"]["poss"], b["pre"]["opp_poss"], b["post"]["poss"]) == (2, 2, 2)
    assert (b["p"], b["t"]) == (1, 600 - 300)


def test_turnovers_of_each_side_are_counted():
    feed = _Feed()
    feed.made("A", "05:50", 2, "p1").tov("B", "05:40", "s").made("A", "05:30", 2, "p1").made("B", "05:20", 2, "s")
    feed.timeout("A", "05:00")
    feed.made("A", "04:50", 2, "p1").tov("B", "04:40", "s").made("A", "04:30", 2, "p1").made("B", "04:20", 2, "s")
    entry = _effects(feed, window=2)["B"][0]

    assert entry["pre"]["tov"] == 1 and entry["post"]["tov"] == 1 and entry["caller"] == "rival"


def test_a_timeout_in_the_last_minute_is_left_out_and_one_just_before_it_is_kept():
    assert TM_LAST_MINUTE_S == 60
    assert _effects(_feed("B", tm_at=59, after=4), window=1) == {"A": [], "B": []}
    assert len(_effects(_feed("B", tm_at=61, after=4), window=1)["B"]) == 1


def test_a_timeout_without_a_complete_window_is_left_out():
    assert _effects(_feed("B", before=2, after=4), window=2)["B"] == []          # one possession per team before: not enough
    assert _effects(_feed("B", before=4, after=2), window=2)["B"] == []          # one possession per team after: not enough


def test_a_timeout_at_the_start_of_a_period_has_no_window_before():
    feed = _Feed()
    feed.timeout("A", "10:00")
    for k in range(4):
        feed.made("AB"[k % 2], _clock(590 - 10 * k), 2, "p1" if k % 2 == 0 else "s")

    assert _effects(feed, window=1) == {"A": [], "B": []}


def test_windows_do_not_cross_periods():
    feed = _feed("B", tm_at=300, before=4, after=4)
    feed.q = "2"
    feed.made("A", "09:50", 2, "p1").made("B", "09:40", 2, "s")
    entry = _effects(feed, window=2)["B"][0]

    assert entry["post"]["pts"] == 6          # the baskets of the next period do not enter the window


def test_the_derived_fields_of_a_game_carry_the_entries_with_the_default_window():
    assert TM_WINDOW_POSSESSIONS == 5
    feed = _feed("B", before=10, after=10, step=8)
    teams = {t["id"]: t for t in derive_game_fields(_game(feed))["TEAM"]}

    assert len(teams["B"]["timeouts"]) == 1 and teams["B"]["timeouts"][0]["caller"] == "own"
    assert teams["A"]["timeouts"][0]["caller"] == "rival"


@pytest.mark.parametrize("key", ["pts", "opp_pts", "poss", "opp_poss", "tov", "opp_tov"])
def test_every_window_has_the_counters_of_both_teams(key):
    entry = _effects(_feed("B"))["B"][0]

    assert key in entry["pre"] and key in entry["post"]
