"""Rules that read the last actions do not speak while the play-by-play is behind the scoreboard (feedback 0.4.0, #564).

FEB's header (the score the staff sees) arrives before the play-by-play lines: «Triples fríos 0/7» was said when the triple that broke the streak was already on the scoreboard but not yet in the log.
This is the pattern of ``lineup_settle`` for the score: a rule of recent actions waits until the log has caught up with the header, and stops waiting if the difference does not go away (a correction of
the table can leave the log with other points for the rest of the game).
"""
import pytest

from src.live_core.advice import AdviceEngine
from src.live_core.config import RuleConfig
from tests.builders import OWN, RIVAL, snap


def threes(misses=7):
    return [[100 + 10 * i, OWN, "fg3", 0, "p1"] for i in range(misses)]


def at(elapsed, header, log=None):
    s = snap(elapsed=elapsed, log=log if log is not None else threes())
    s["score"] = dict(header)
    return s


def ids(alerts):
    return [a.id for a in alerts]


def engine(**kw):
    return AdviceEngine(own_team_id=OWN, rival_team_id=RIVAL, config=RuleConfig(**kw))


def test_a_cold_streak_waits_while_the_scoreboard_is_ahead_of_the_log_regression():
    eng = engine()
    assert "cold_3p_streak" not in ids(eng.evaluate(at(200, {OWN: 3, RIVAL: 0})))      # a made three is on the scoreboard, not in the log yet
    assert "cold_3p_streak" in ids(engine().evaluate(at(200, {OWN: 0, RIVAL: 0})))     # the same log with a scoreboard that agrees speaks


def test_it_speaks_once_the_log_has_caught_up_if_the_streak_still_holds():
    eng = engine()
    eng.evaluate(at(200, {OWN: 2, RIVAL: 0}))                                          # a two-pointer of the other kind: the scoreboard is ahead
    caught_up = at(215, {OWN: 2, RIVAL: 0}, log=threes() + [[210, OWN, "pts", 2, "p1"]])
    assert "cold_3p_streak" in ids(eng.evaluate(caught_up))


def test_a_difference_that_never_goes_away_is_not_waited_for_forever():
    eng = engine()
    assert "cold_3p_streak" not in ids(eng.evaluate(at(200, {OWN: 2, RIVAL: 0})))
    assert "cold_3p_streak" in ids(eng.evaluate(at(200 + eng._ctx.config.log_lag_max_s + 10, {OWN: 2, RIVAL: 0})))


def test_a_scoreboard_behind_the_log_is_not_a_lag_and_other_rules_never_wait():
    assert "cold_3p_streak" in ids(engine().evaluate(at(200, {OWN: 0, RIVAL: 0}, log=threes() + [[190, RIVAL, "pts", 2, "r1"]])))
    players = {"p1": {"name": "Ana", "team_id": OWN, "on_court": True, "minutes": 600, "stint": 100, "pf": 4, "pts": 0, "pf_by_period": {}}}
    s = at(200, {OWN: 5, RIVAL: 0})
    s["players"] = players
    assert "foul_trouble" in ids(engine().evaluate(s))                                  # a rule that does not read recent actions is not held back
