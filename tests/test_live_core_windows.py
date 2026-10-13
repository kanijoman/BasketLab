"""Window statistics over the event log (issue #237): the base of the diagnosis of runs and droughts.

All helpers read the log entries [elapsed, team_id, kind, value, player_id]; old 4-element entries (a log written by
an older engine) must still work, without a player.
"""
import pytest

from src.live_core.config import RuleConfig
from src.live_core.windows import (
    field_goal_gap, last_shots, player_of, player_points, run_causes, scoring_gap, trailing_makes, window_stats,
)

A, B = "T1", "T2"

LOG = [
    [100, A, "fg2", 1, "a1"], [100, A, "pts", 2, "a1"],
    [110, A, "fg3", 0, "a2"],
    [115, B, "orb", 1, "b1"],
    [120, B, "fg3", 1, "b1"], [120, B, "pts", 3, "b1"],
    [130, A, "tov", 1, "a1"], [140, A, "tov", 1, "a1"], [150, A, "tov", 1, None],
    [150, B, "stl", 1, "b2"],
    [160, A, "ft", 1, "a1"], [160, A, "pts", 1, "a1"], [160, A, "ft", 0, "a1"],
    [170, A, "timeout", 1, None],
    [400, A, "fg2", 0, "a1"],
]


def test_window_stats_of_a_team_inside_an_inclusive_window():
    s = window_stats(LOG, A, 100, 170)
    assert s["pts"] == 3
    assert s["fg2"] == [1, 1] and s["fg3"] == [0, 1] and s["ft"] == [1, 2]
    assert s["tov"] == 3 and s["tov_by_player"] == {"a1": 2}
    assert s["orb"] == 0 and s["stl"] == 0 and s["timeouts"] == 1


def test_window_stats_ignore_the_other_team_and_the_outside_of_the_window():
    s = window_stats(LOG, B, 100, 170)
    assert s["pts"] == 3 and s["fg3"] == [1, 1] and s["orb"] == 1 and s["stl"] == 1
    assert s["tov"] == 0 and s["fg2"] == [0, 0]
    assert window_stats(LOG, A, 101, 109)["pts"] == 0


def test_an_empty_log_gives_zeros():
    s = window_stats([], A, 0, 600)
    assert s["pts"] == 0 and s["fg2"] == [0, 0] and s["tov"] == 0 and s["tov_by_player"] == {}


def test_old_four_element_entries_still_count_without_a_player():
    old = [[100, A, "pts", 2], [110, A, "tov", 1], [120, A, "orb", 1]]
    s = window_stats(old, A, 0, 200)
    assert s["pts"] == 2 and s["tov"] == 1 and s["orb"] == 1 and s["tov_by_player"] == {}
    assert player_of(old[0]) is None and player_of(LOG[0]) == "a1"
    assert player_points(old, "a1", 0, 200) == 0


def test_scoring_gap_is_the_time_since_the_last_points():
    assert scoring_gap(LOG, A, now=300) == 140          # last points at 160
    assert scoring_gap(LOG, B, now=300) == 180          # last points at 120
    assert scoring_gap(LOG, "T9", now=300) == 300       # never scored: since tip-off
    assert scoring_gap(LOG, "T9", now=300, since=200) == 100
    assert scoring_gap(LOG, A, now=160) == 0


def test_field_goal_gap_ignores_free_throws():
    assert field_goal_gap(LOG, A, now=300) == 200       # last made field goal at 100, the free throw at 160 does not count
    assert scoring_gap(LOG, A, now=300) == 140


def test_last_shots_are_the_most_recent_attempts_oldest_first():
    assert last_shots(LOG, A, 3) == [1, 0, 0]                       # fg2 made, fg3 missed, fg2 missed
    assert last_shots(LOG, A, 2, kinds=("fg3",)) == [0]
    assert last_shots(LOG, A, 5, kinds=("ft",)) == [1, 0]
    assert last_shots(LOG, A, 5, player_id="a2") == [0]
    assert last_shots(LOG, A, 0) == []


def test_trailing_makes_counts_the_current_hot_streak():
    assert trailing_makes([0, 1, 1, 1]) == 3
    assert trailing_makes([1, 1, 0]) == 0
    assert trailing_makes([]) == 0


def test_player_points_inside_a_window():
    assert player_points(LOG, "a1", 0, 200) == 3
    assert player_points(LOG, "a1", 101, 200) == 1
    assert player_points(LOG, "b1", 0, 200) == 3


# --- causes of a run or a drought --------------------------------------------------------

CFG = RuleConfig()
NAMES = {"a1": "Ana", "a2": "Aida", "b1": "Bea"}


def stats(**kw):
    base = window_stats([], A, 0, 1)
    base.update(kw)
    return base


def test_turnovers_are_the_cause_and_the_player_who_concentrates_them_is_named():
    own = stats(tov=4, tov_by_player={"a1": 3, "a2": 1})
    [cause] = run_causes(own, stats(), NAMES, CFG)
    assert cause["kind"] == "turnovers" and cause["count"] == 4
    assert cause["text"] == "4 pérdidas (3 de Ana)"


def test_causes_are_ranked_by_the_points_they_explain_and_limited():
    own = stats(tov=2, tov_by_player={"a1": 1, "a2": 1}, ft=[0, 3], fg2=[0, 3], fg3=[0, 2])
    rival = stats(orb=3, fg3=[2, 3], ft=[3, 5])
    causes = run_causes(own, rival, NAMES, CFG)
    assert len(causes) == CFG.cause_max
    assert [c["points"] for c in causes] == sorted((c["points"] for c in causes), reverse=True)
    assert all(isinstance(c["text"], str) and c["text"] for c in causes)


@pytest.mark.parametrize("own,rival,kind,text", [
    (dict(), dict(orb=3), "rival_orb", "3 rebotes ofensivos del rival"),
    (dict(ft=[1, 4]), dict(), "own_free_throws", "3 tiros libres fallados"),
    (dict(), dict(fg3=[3, 5]), "rival_threes", "3 triples del rival"),
    (dict(), dict(ft=[6, 8]), "rival_free_throws", "8 tiros libres del rival"),
    (dict(fg2=[1, 4], fg3=[0, 3]), dict(), "own_cold", "tiro propio 1/7"),
])
def test_each_cause_has_its_own_text(own, rival, kind, text):
    causes = run_causes(stats(**own), stats(**rival), NAMES, CFG)
    assert [(c["kind"], c["text"]) for c in causes if c["kind"] == kind] == [(kind, text)]


def test_a_single_event_is_not_a_cause():
    own = stats(tov=1, tov_by_player={"a1": 1}, ft=[0, 1])
    assert run_causes(own, stats(orb=1, fg3=[1, 1]), NAMES, CFG) == []


def test_the_minimum_count_comes_from_the_config():
    own = stats(tov=1, tov_by_player={"a1": 1})
    [cause] = run_causes(own, stats(), NAMES, RuleConfig(cause_min_count=1))
    assert cause["kind"] == "turnovers" and cause["text"] == "1 pérdida"  # singular, and no player when it is only one
