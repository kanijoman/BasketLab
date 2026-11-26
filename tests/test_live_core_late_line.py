"""A play-by-play line logged late, with a clock earlier than the lines before it (#1119, epic #1108).

FEB writes a correction or a forgotten action with a higher line number than the ones already applied but an earlier clock. The engine applies lines by number, so the game clock
went BACK to that line and the next one credited the seconds in between a second time: a lineup got 400 s in 300 s of game.
"""
from src.live_core.clock import period_and_remaining
from src.live_core.events import Event
from src.live_core.state import LiveGame

TEAMS = [("A", "A"), ("B", "B")]


def _event(num, at, kind, team=None, player=None):
    period, remaining = period_and_remaining(at)
    return Event(num=num, period=period, remaining=remaining, elapsed=at, kind=kind, team_id=team, player_id=player, name=player)


def _game(late):
    game = LiveGame(TEAMS, {})
    n = 0
    for team, five in (("A", "abcde"), ("B", "vwxyz")):
        for pid in five:
            n += 1
            game.apply(_event(n, 0, "sub_in", team, pid))
    game.apply(_event(11, 400, "turnover", "A", "a"))
    if late:
        game.apply(_event(12, 300, "turnover", "B", "v"))          # logged after the one at 400 s, but it happened at 300 s
    game.apply(_event(13, 600, "turnover", "A", "a"))
    return game


def test_a_line_logged_late_does_not_make_the_clock_go_back_and_credit_seconds_twice_regression():
    on_time, late = _game(late=False).snapshot(), _game(late=True).snapshot()
    assert late["elapsed"] == on_time["elapsed"] == 600
    assert late["lineup_now"]["A"]["seconds"] == on_time["lineup_now"]["A"]["seconds"] == 600, "700 s of quintet in 600 s of game"
    assert late["players"]["a"]["minutes"] == on_time["players"]["a"]["minutes"]


def test_the_late_line_itself_is_still_applied():
    snap = _game(late=True).snapshot()
    assert snap["last_num"] == 13 and any(row[1] == "B" and row[2] == "tov" for row in snap["log"])
