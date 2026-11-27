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


# -- the possessions of a match with a late line: live = after the match (#1119, second part) ----------------------------------------------------------------------

def _with_a_late_line():
    from tests.builders import OWN, RIVAL, Match
    m = Match().lineup(OWN, list("abcde"), at=0).lineup(RIVAL, list("vwxyz"), at=0)
    m.score(OWN, 2, at=100, player="a").miss(OWN, at=140, player="b").rebound(RIVAL, at=141, player="v").score(RIVAL, 2, at=200, player="w")
    m.late("score", RIVAL, 2, at=110, player="x")                # FEB logged it after the one at 200 s: by the clock the rival answered at 110 s and the miss at 140 s was the own team's next possession
    return m


def test_the_live_possessions_of_a_match_with_a_late_line_are_the_ones_of_the_whole_game_regression():
    """#1119: the engine applied by line number and ``track()`` (what DERIVED stores) sorts by clock, so a late line broke the alternation live and not afterwards."""
    from src.live_core.engine import LiveEngine
    from src.live_core.possessions import track
    m = _with_a_late_line()
    _, quality = track(m.events, [m.own, m.rival])
    live = LiveEngine().update(m.document())["possessions"]
    assert live["quality"]["breaks"] == quality.breaks
    assert live["quality"]["inferred"] == quality.inferred and live["quality"]["breaks_raw"] == quality.breaks_raw


def test_a_late_line_that_arrives_in_a_later_poll_gives_the_same_as_the_whole_document_at_once():
    """Applied in clock order, a late line that shows up in a later poll rebuilds the game: the result is the one of a fresh engine."""
    from src.live_core.engine import LiveEngine
    m = _with_a_late_line()
    doc = m.document()
    before = dict(doc, PLAYBYPLAY={"LINES": [ln for ln in doc["PLAYBYPLAY"]["LINES"] if int(ln["num"]) != max(int(x["num"]) for x in doc["PLAYBYPLAY"]["LINES"])]})
    engine = LiveEngine()
    engine.update(before)
    after = engine.update(doc)
    fresh = LiveEngine().update(doc)
    assert (after["score"], after["possessions"], after["lineup_now"]) == (fresh["score"], fresh["possessions"], fresh["lineup_now"])
