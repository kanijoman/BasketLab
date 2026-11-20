"""The validation of the age curve says where it helps (#892): the error by age group, so that a curve that only helps the young is said to."""
from tests.test_market_age_curve import births_of, leave_one_season_out, pairs, world  # noqa: F401


def test_the_error_is_broken_down_by_age_group_and_the_curve_helps_where_the_world_has_one():
    obs, births = world(persons=1500)
    groups = leave_one_season_out(pairs(obs, births, 1))["per_age_group"]
    assert set(groups) == {"<=21", "22-29", "30+"} and all(g["n"] > 0 for g in groups.values())
    assert groups["<=21"]["mae_model"] < groups["<=21"]["mae_rho_only"] * 0.95            # the young improve in the world
    assert groups["22-29"]["mae_model"] <= groups["22-29"]["mae_rho_only"] * 1.02          # where nothing happens it does no harm
