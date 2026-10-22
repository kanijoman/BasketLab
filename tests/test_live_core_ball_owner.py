"""Who has the ball right now, for the scoreboard of the app (feedback of the 0.3.2 tests, issue #497).

An indicator, not an official statistic: it is read from the last events of the play-by-play (the exact possessions of ``possessions.py`` are only known once a possession
is closed). After a made basket the ball is the rival's; after a miss it is nobody's until the rebound; a rebound or a steal gives it to that team; a turnover to the rival;
free throws are the shooter's. Nothing at the start of a period and when the feed does not say.
"""
from src.live_core.events import Event
from src.live_core.state import LiveGame

A, B = "1", "2"


def game():
    return LiveGame([(A, "A"), (B, "B")], {})


def ev(num, kind, team=None, made=None, elapsed=None, **kw):
    elapsed = num * 10 if elapsed is None else elapsed
    points = kw.pop("points", 2)
    return Event(num=num, period=kw.pop("period", 1), remaining=600 - elapsed, elapsed=elapsed, kind=kind, team_id=team, made=made,
                 points=points if made else 0, **kw)


def owner(g):
    return (g.snapshot().get("ball") or {}).get("team_id")


def play(*events):
    g = game()
    for e in events:
        g.apply(e)
    return g


def test_nobody_has_the_ball_before_the_first_action():
    assert owner(game()) is None and game().snapshot()["ball"] is None


def test_after_a_made_basket_the_ball_is_the_rivals():
    assert owner(play(ev(1, "fg2", A, made=True))) == B
    assert owner(play(ev(1, "fg3", B, made=True, points=3))) == A


def test_after_a_miss_the_ball_is_in_the_air_until_the_rebound():
    g = play(ev(1, "fg2", A, made=False))
    assert owner(g) is None and g.snapshot()["ball"] == {"team_id": None, "since": 10, "why": "miss"}
    assert owner(play(ev(1, "fg2", A, made=False), ev(2, "rebound", B))) == B          # defensive rebound
    assert owner(play(ev(1, "fg2", A, made=False), ev(2, "rebound", A))) == A          # offensive rebound


def test_a_turnover_gives_the_ball_to_the_rival_and_a_steal_to_the_stealer():
    assert owner(play(ev(1, "turnover", A))) == B
    assert owner(play(ev(1, "steal", B))) == B


def test_free_throws_are_the_shooters_and_the_next_action_decides_the_rest():
    g = play(ev(1, "foul", B), ev(2, "ft", A, made=True, points=1))
    assert owner(g) == A
    assert owner(play(ev(1, "ft", A, made=True, points=1), ev(2, "ft", A, made=True, points=1), ev(3, "fg2", B, made=True))) == A      # B scored: the ball goes to A
    assert owner(play(ev(1, "ft", A, made=False, points=1), ev(2, "rebound", B))) == B


def test_fouls_substitutions_and_timeouts_do_not_move_the_ball():
    base = play(ev(1, "fg2", A, made=True))
    for kind in ("foul", "sub_in", "sub_out", "timeout"):
        g = play(ev(1, "fg2", A, made=True), ev(2, kind, B))
        assert owner(g) == owner(base) == B


def test_the_start_and_the_end_of_a_period_clear_it():
    assert owner(play(ev(1, "fg2", A, made=True), ev(2, "period_end", elapsed=600))) is None
    assert owner(play(ev(1, "fg2", A, made=True), ev(2, "period_start", period=2, elapsed=600))) is None


def test_it_says_when_it_started_and_survives_the_snapshot_copy():
    g = play(ev(1, "fg2", A, made=True, elapsed=95))
    ball = g.snapshot()["ball"]
    assert ball == {"team_id": B, "since": 95, "why": "made_basket"}
    ball["team_id"] = "x"
    assert owner(g) == B                                                                  # the snapshot is a copy


def test_a_game_with_other_than_two_teams_has_no_ball():
    g = LiveGame([(A, "A")], {})
    g.apply(ev(1, "fg2", A, made=True))
    assert g.snapshot()["ball"] is None
