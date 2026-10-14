"""Lineups and plus/minus in the live state (issue #248): ``LiveGame`` keeps, with the five players on court of each team, the
seconds and points for and against of every quintet, the current quintet's stint, and the +/- of every player (the points of
his team minus the rival's while he is on court). The official box score of the sample game carries each player's +/- (``pllss``):
the numbers must agree with it.
"""
import pytest

from src.live_core.clock import elapsed_seconds
from src.live_core.engine import LiveEngine
from src.live_core.events import Event
from src.live_core.state import LiveGame

A, B = "A", "B"
TEAM_A, TEAM_B = [f"a{i}" for i in range(1, 7)], [f"b{i}" for i in range(1, 7)]


def ev(num, period, remaining, kind, pid, made=None, points=0):
    team = B if pid.startswith("b") else A
    return Event(num=num, period=period, remaining=remaining, elapsed=elapsed_seconds(period, remaining), kind=kind,
                 team_id=team, player_id=pid, name=pid, made=made, points=points)


def game():
    g = LiveGame([(A, "A"), (B, "B")], roster={pid: (pid, A if pid.startswith("a") else B) for pid in TEAM_A + TEAM_B})
    for n, pid in enumerate(TEAM_A[:5] + TEAM_B[:5]):
        g.apply(ev(n, 1, 600, "sub_in", pid))
    return g


def basket(g, num, remaining, pid, points=2):
    g.apply(ev(num, 1, remaining, "fg3" if points == 3 else "fg2", pid, made=True, points=points))


def lineup(snapshot, team, players):
    return next(l for l in snapshot["lineups"][team] if l["players"] == sorted(players))


def test_the_points_of_a_basket_go_for_the_scorers_quintet_against_the_rival_one_and_to_every_plus_minus():
    g = game()
    basket(g, 20, 500, "a1")
    basket(g, 21, 480, "b2", 3)
    s = g.snapshot()
    la, lb = lineup(s, A, TEAM_A[:5]), lineup(s, B, TEAM_B[:5])
    assert (la["pts_for"], la["pts_against"]) == (2, 3) and (lb["pts_for"], lb["pts_against"]) == (3, 2)
    assert s["players"]["a1"]["pm"] == -1 and s["players"]["b1"]["pm"] == 1 and s["players"]["a6"]["pm"] == 0


def test_free_throws_count_too():
    g = game()
    g.apply(ev(20, 1, 500, "ft", "a1", made=True, points=1))
    g.apply(ev(21, 1, 500, "ft", "a1", made=False))
    assert g.snapshot()["players"]["a2"]["pm"] == 1


def test_seconds_are_credited_to_the_quintet_only_while_there_are_five_on_court():
    g = game()
    g.apply(ev(20, 1, 500, "sub_out", "a5"))            # 100 s with the starting five
    g.apply(ev(21, 1, 460, "sub_in", "a6"))             # 40 s with four players: nobody's quintet
    g.apply(ev(22, 1, 400, "rebound", "a1"))            # 60 s with the new five
    s = g.snapshot()
    assert lineup(s, A, TEAM_A[:5])["seconds"] == 100
    assert lineup(s, A, TEAM_A[:4] + ["a6"])["seconds"] == 60


def test_a_quintet_that_comes_back_adds_to_its_own_totals_and_counts_its_stints():
    g = game()
    g.apply(ev(20, 1, 500, "sub_out", "a5")); g.apply(ev(21, 1, 500, "sub_in", "a6"))
    g.apply(ev(22, 1, 400, "sub_out", "a6")); g.apply(ev(23, 1, 400, "sub_in", "a5"))
    g.apply(ev(24, 1, 300, "rebound", "a1"))
    first = lineup(g.snapshot(), A, TEAM_A[:5])
    assert first["seconds"] == 100 + 100 and first["stints"] == 2


def test_the_current_quintet_has_its_own_stint_that_restarts_with_every_change():
    g = game()
    basket(g, 20, 500, "b1")
    g.apply(ev(21, 1, 450, "sub_out", "a5")); g.apply(ev(22, 1, 450, "sub_in", "a6"))
    basket(g, 23, 400, "a1")
    now = g.snapshot()["lineup_now"][A]
    assert now["players"] == sorted(TEAM_A[:4] + ["a6"]) and now["since"] == 150
    assert now["seconds"] == 50 and (now["pts_for"], now["pts_against"]) == (2, 0)      # nothing of the first five's stint is in it


def test_a_player_has_his_plus_minus_in_the_game_and_in_the_current_stint():
    g = game()
    basket(g, 20, 500, "b1")                                # a5 is -2 on court
    g.apply(ev(21, 1, 450, "sub_out", "a5"))
    basket(g, 22, 400, "b1")                                # a5 is on the bench: no change
    g.apply(ev(23, 1, 350, "sub_in", "a5"))                 # comes back: a new stint
    basket(g, 24, 300, "a1", 3)
    p = g.snapshot()["players"]["a5"]
    assert p["pm"] == -2 + 3 and p["stint_pm"] == 3


def test_the_snapshot_without_events_has_empty_lineups_and_no_current_one():
    g = LiveGame([(A, "A"), (B, "B")])
    s = g.snapshot()
    assert s["lineups"] == {A: [], B: []} and s["lineup_now"] == {A: None, B: None}


def test_the_quintets_come_by_seconds_most_played_first():
    g = game()
    g.apply(ev(20, 1, 500, "sub_out", "a5")); g.apply(ev(21, 1, 500, "sub_in", "a6"))
    g.apply(ev(22, 1, 100, "rebound", "a1"))
    assert [l["seconds"] for l in g.snapshot()["lineups"][A]] == [400, 100]


# --- against the official box score of the real sample game ---------------------------------------------------------

def test_the_plus_minus_of_every_player_is_the_official_one(feb_game_doc):
    snapshot = LiveEngine().update(feb_game_doc)
    wrong = {}
    for team in feb_game_doc["BOXSCORE"]["TEAM"]:
        for p in team["PLAYER"]:
            got = snapshot["players"].get(p["id"], {}).get("pm", 0)
            if got != int(p["pllss"]):
                wrong[p["name"]] = (got, int(p["pllss"]))
    assert wrong == {}


def test_every_point_of_the_game_belongs_to_a_quintet_of_each_side_and_the_time_adds_up(feb_game_doc):
    snapshot = LiveEngine().update(feb_game_doc)
    for tid, other in (("982047", "981204"), ("981204", "982047")):
        lineups = snapshot["lineups"][tid]
        assert sum(l["pts_for"] for l in lineups) == snapshot["score"][tid]
        assert sum(l["pts_against"] for l in lineups) == snapshot["score"][other]
        assert all(len(l["players"]) == 5 for l in lineups)
        assert 0.95 * 2400 <= sum(l["seconds"] for l in lineups) <= 2400 + 5
