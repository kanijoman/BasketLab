"""Issue #825: a team starts the season with the final rating of the previous one, linked by ``teamCode`` (the ids change every season).

Measured on 1,106 games of 4 season transitions (log loss 0.5486 -> 0.5366; 61.7 % -> 72.2 % accuracy in the first 3 games of a team).
Teams without a link (new, promoted, relegated) keep starting at 0 with the variance of a team never seen.
"""
import pytest

from src.live_prep.package_builder import SeasonAccumulator
from src.live_prep.team_rating import CARRY_VARIANCE, P0, TeamRatings

A, B = "982047", "981204"
CODE_A, CODE_B = "33002601", "08160700"


def margin_of(doc):
    from src.live_core.engine import LiveEngine

    snap = LiveEngine().update(doc)
    return snap["score"][A] - snap["score"][B]


def test_a_linked_team_starts_from_the_final_rating_of_the_last_season(feb_game_doc):
    acc = SeasonAccumulator(carry={CODE_A: 6.0})
    acc.add_game(feb_game_doc)
    reference = TeamRatings()
    reference.seed(A, 6.0, CARRY_VARIANCE)
    reference.update(A, B, margin_of(feb_game_doc))
    assert acc.ratings.rating(A) == pytest.approx(reference.rating(A))
    assert acc.ratings.rating(B) == pytest.approx(reference.rating(B))


def test_a_team_without_link_starts_at_zero_as_always(feb_game_doc):
    plain, carried = SeasonAccumulator(), SeasonAccumulator(carry={"99999999": 6.0})
    for acc in (plain, carried):
        acc.add_game(feb_game_doc)
    assert carried.ratings.rating(A) == plain.ratings.rating(A)
    assert carried.ratings.variance(B) == plain.ratings.variance(B)


def test_the_carried_team_is_surer_than_a_new_one():
    ratings = TeamRatings()
    ratings.seed("A", 4.0, CARRY_VARIANCE)
    assert ratings.rating("A") == 4.0 and ratings.variance("A") == CARRY_VARIANCE < P0 and ratings.variance("B") == P0


def test_the_seed_does_not_override_what_the_season_already_taught():
    """Idempotence: seeding a team that has played is ignored (late data must not rewrite its rating)."""
    ratings = TeamRatings()
    ratings.update("A", "B", 10)
    before = ratings.rating("A")
    ratings.seed("A", 9.0, CARRY_VARIANCE)
    assert ratings.rating("A") == before


def test_the_final_ratings_of_a_season_are_exported_by_team_code(feb_game_doc):
    acc = SeasonAccumulator()
    acc.add_game(feb_game_doc)
    final = acc.final_by_code()
    assert set(final) == {CODE_A, CODE_B} and final[CODE_A] == acc.ratings.rating(A)
