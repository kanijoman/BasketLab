"""The Bayesian (Kalman) rating of the teams behind ``net_rtg_prior`` (issue #567, study of 26/10/2026).

The study found that the prior of the matchup is what the win probability lives on, and that a rating that is updated with every result according to how sure
it is of each team (its variance), discounting the strength of the opponents and the home court, beats the season average of the net rating: with the model
calibrated per family of competitions the log loss goes from 0.4105 to 0.4070 (2,886 games). Pure Python, as the publisher runs it.
"""
import pytest

from src.live_prep.team_rating import HOME_PRIOR, NOISE, P0, TeamRatings


def test_teams_never_seen_are_average_and_their_gap_is_zero():
    ratings = TeamRatings()
    assert ratings.rating("A") == 0.0 and ratings.gap_per_100("A", "B", pace=70.0) == 0.0


def test_one_result_moves_both_teams_by_how_unsure_they_were_and_never_the_whole_margin():
    ratings = TeamRatings()
    ratings.update("A", "B", 20)                                  # A, at home, wins by 20
    gain = P0 / (P0 + P0 + NOISE) * (20 - HOME_PRIOR)              # the part of the surprise that goes to A
    assert ratings.rating("A") == pytest.approx(gain) and ratings.rating("B") == pytest.approx(-gain)
    assert 0 < ratings.rating("A") < 20


def test_the_second_same_result_moves_less_the_rating_gets_surer():
    ratings = TeamRatings()
    ratings.update("A", "B", 20)
    first = ratings.rating("A")
    ratings.update("A", "B", 20)
    assert 0 < ratings.rating("A") - first < first


def test_the_strength_of_the_opponents_counts():
    """A beats B by 10 and B beats C by 10: A is worth more than C although they never met."""
    ratings = TeamRatings()
    for _ in range(3):
        ratings.update("A", "B", 10)
        ratings.update("B", "C", 10)
    assert ratings.rating("A") > ratings.rating("B") > ratings.rating("C")
    assert ratings.gap_per_100("A", "C", pace=70.0) > 0 > ratings.gap_per_100("C", "A", pace=70.0)


def test_the_home_court_is_learnt_and_not_given_to_the_teams():
    """Equal teams that always win at home by 6: the ratings stay near 0 and the home court goes towards 6."""
    ratings = TeamRatings()
    teams = ["A", "B", "C", "D"]
    for _ in range(10):
        for h in teams:
            for a in teams:
                if h != a:
                    ratings.update(h, a, 6)
    assert all(abs(ratings.rating(t)) < 0.5 for t in teams)
    assert ratings.home_advantage() == pytest.approx(6.0, abs=0.6)


def test_the_gap_is_said_per_100_possessions_with_the_pace_of_the_matchup():
    ratings = TeamRatings()
    ratings.update("A", "B", 20)
    per_game = ratings.rating("A") - ratings.rating("B")
    assert ratings.gap_per_100("A", "B", pace=80.0) == pytest.approx(per_game * 100 / 80)
    assert ratings.gap_per_100("A", "B", pace=0.0) == pytest.approx(per_game * 100 / 70)    # no pace known: the default one


def test_the_same_results_in_the_same_order_give_the_same_ratings():
    games = [("A", "B", 7), ("C", "A", -3), ("B", "C", 12), ("A", "C", 1)]
    first, second = TeamRatings(), TeamRatings()
    for g in games:
        first.update(*g)
        second.update(*g)
    assert {t: first.rating(t) for t in "ABC"} == {t: second.rating(t) for t in "ABC"}
