"""The recommender with the quintets of the package (issue #132): a swap makes a new quintet and, when the season has data for it,
its net rating per 40 minutes (shrunk to zero by the time it played together) moves the candidate's score and shows in the
proposal. A quintet with little time together, or none in the table, says nothing: the swap is judged by role as before."""
import pytest

from src.live_core.advice import AdviceEngine
from src.live_core.config import RuleConfig
from src.live_core.lineups import lineup_key
from src.live_core.recommender import Recommender

from live_helpers import ON_COURT, OWN, RIVAL, TABLE, snap  # noqa: F401


def after(out_pid, in_pid):
    return lineup_key([in_pid if pid == out_pid else pid for pid in ON_COURT])


def row(key, net40, seconds):
    return {"team_id": OWN, "players": key.split("|"), "seconds": seconds, "pts_for": 0, "pts_against": 0, "stints": 3, "net40": net40}


def rec(lineups=None, **cfg):
    return Recommender(OWN, TABLE, RuleConfig(**cfg), lineups=lineups)


def best_of(r, out_pid="b1"):
    return [c["in_id"] for c in r.suggest_swaps(snap(), out_pid)]


def score_of(r, in_id="b2"):
    return next(c["score"] for c in r.suggest_swaps(snap(), "b1") if c["in_id"] == in_id)


def test_a_quintet_that_did_well_in_the_season_scores_higher_and_one_that_did_badly_lower():
    key = after("b1", "b2")
    base = score_of(rec())
    assert score_of(rec({key: row(key, 14.0, 3600)})) > base > score_of(rec({key: row(key, -14.0, 3600)}))


def test_it_can_change_who_comes_in_first():
    # b3 is the unbalanced option by default (it comes last); with a tolerant balance and a good quintet it goes first
    loose = dict(rec_balance_tolerance=10.0, rec_lineup_weight=0.1)
    assert best_of(rec(**loose))[0] == "b2"
    key = after("b1", "b3")
    assert best_of(rec({key: row(key, 30.0, 7200)}, **loose))[0] == "b3"


def test_a_quintet_with_little_time_together_says_nothing():
    lineups = {after("b1", "b3"): row(after("b1", "b3"), 40.0, 120), after("b1", "b2"): row(after("b1", "b2"), -40.0, 120)}
    assert best_of(rec(lineups)) == best_of(rec())
    candidate = rec(lineups).suggest_swaps(snap(), "b1")[0]
    assert candidate["lineup_net40"] is None and "quinteto resultante" not in candidate["message"].lower()


def test_the_same_net_rating_counts_less_the_less_they_played_together():
    key = after("b1", "b2")
    short = rec({key: row(key, 20.0, 600)}).suggest_swaps(snap(), "b1")
    long = rec({key: row(key, 20.0, 7200)}).suggest_swaps(snap(), "b1")
    score = lambda cs: next(c["score"] for c in cs if c["in_id"] == "b2")
    base = next(c["score"] for c in rec().suggest_swaps(snap(), "b1") if c["in_id"] == "b2")
    assert base < score(short) < score(long)


def test_the_proposal_carries_the_net_rating_and_says_it_in_the_message():
    key = after("b1", "b2")
    candidate = next(c for c in rec({key: row(key, 9.5, 1800)}).suggest_swaps(snap(), "b1") if c["in_id"] == "b2")
    assert candidate["lineup_net40"] == pytest.approx(9.5) and candidate["lineup_seconds"] == 1800
    assert "quinteto resultante" in candidate["message"].lower() and "+9.5" in candidate["message"] and "30 min" in candidate["message"]


def test_without_lineups_nothing_changes():
    candidate = rec().suggest_swaps(snap(), "b1")[0]
    assert candidate["lineup_net40"] is None and candidate["lineup_seconds"] == 0


def test_the_rest_mode_is_not_judged_by_quintets():
    key = after("b1", "b2")
    a = rec().suggest_rest(snap(overrides={"b1": {"minutes": 1500}}), "b1")
    b = rec({key: row(key, 30.0, 3600)}).suggest_rest(snap(overrides={"b1": {"minutes": 1500}}), "b1")
    assert [c["in_id"] for c in a] == [c["in_id"] for c in b]


def test_the_engine_gives_the_recommender_the_quintets_of_the_package():
    key = after("b1", "b2")
    engine = AdviceEngine(own_team_id=OWN, rival_team_id=RIVAL, baselines=TABLE, config=RuleConfig(), lineups=[row(key, 14.0, 3600)])
    swaps = engine._recommender.suggest_swaps(snap(), "b1")
    assert swaps[0]["in_id"] == "b2" and swaps[0]["lineup_net40"] == pytest.approx(14.0)
