"""Zone shooting rated against how the COMPETITION shoots in that zone (issues #139, #760).

Before #760 a zone was ``above``/``below`` the league average only if it differed by 2 percentage points AND z >= 1: both fixed numbers, the same in the rim and in the corner three.
Now the reference is the distribution of the teams (or the players) of the competition in that zone: ``above`` over its upper quartile, ``below`` under its lower quartile. There is no
minimum of shots: each entity weighs what it shot, so a player with one shot does not move the quartiles, and the zone is still painted (with the low-sample flag as a hint only).
"""
import pytest

from src.shotcharts.zone_rating import rate_zone, rate_zones, weighted_quantile


class TestWeightedQuantile:
    def test_equal_weights_are_the_plain_quantiles_of_the_inverse_cdf(self):
        pairs = [(1.0, 1), (2.0, 1), (3.0, 1), (4.0, 1)]
        assert [weighted_quantile(pairs, q) for q in (0.25, 0.5, 0.75, 1.0)] == [1.0, 2.0, 3.0, 4.0]

    def test_the_order_of_the_entries_does_not_matter(self):
        assert weighted_quantile([(3.0, 1), (1.0, 1), (4.0, 1), (2.0, 1)], 0.75) == 3.0

    def test_what_an_entity_shot_is_what_it_weighs(self):
        # one shot at 100 % and one at 0 % next to 98 shots at 50 %: the middle is where the shots are
        pairs = [(1.0, 1), (0.0, 1), (0.5, 98)]
        assert weighted_quantile(pairs, 0.25) == 0.5 and weighted_quantile(pairs, 0.75) == 0.5

    def test_a_heavy_entity_moves_the_quartile_a_light_one_does_not(self):
        light = [(0.40, 100), (0.45, 100), (0.50, 100), (0.55, 100), (1.0, 1)]
        assert weighted_quantile(light, 0.75) == 0.55
        heavy = [(0.40, 100), (0.45, 100), (0.50, 100), (0.55, 100), (1.0, 600)]
        assert weighted_quantile(heavy, 0.75) == 1.0

    def test_nothing_to_say_without_data(self):
        assert weighted_quantile([], 0.25) is None
        assert weighted_quantile([(0.5, 0)], 0.25) is None            # an entity that did not shoot has no weight


def _team(fgm, fga):
    return (fgm, fga)


# eight teams shooting 100 times each in the zone: 40, 42, 44, 46, 48, 50, 52, 54 % → quartiles at 42 % and 50 % of the weight (the lower inverse cdf)
TEAMS = [_team(m, 100) for m in (40, 42, 44, 46, 48, 50, 52, 54)]


class TestRateZone:
    def test_above_the_upper_quartile(self):
        r = rate_zone(54, 100, TEAMS)
        assert r["rating"] == "above" and r["delta_pp"] == pytest.approx(54 - 47.0)
        assert r["league_pct"] == pytest.approx(47.0)                     # the average of the competition, for the tooltip

    def test_below_the_lower_quartile(self):
        assert rate_zone(40, 100, TEAMS)["rating"] == "below"

    def test_between_the_quartiles_is_average(self):
        assert rate_zone(46, 100, TEAMS)["rating"] == "average"

    def test_the_quartile_itself_is_average_not_above(self):
        # the upper quartile of these eight is 50 %: being exactly there is not above it
        assert rate_zone(50, 100, TEAMS)["rating"] == "average"
        assert rate_zone(42, 100, TEAMS)["rating"] == "average"
        assert rate_zone(51, 100, TEAMS)["rating"] == "above"
        assert rate_zone(41, 100, TEAMS)["rating"] == "below"

    def test_no_fixed_margin_it_depends_on_how_the_competition_spreads(self):
        tight = [_team(m, 1000) for m in (450, 452, 454, 456, 458, 460, 462, 464)]            # 45-46.4 %: everybody shoots alike
        assert rate_zone(463, 1000, tight)["rating"] == "above"              # +0.6 pp over the average is above here (the fixed rule needed +2 pp)
        wide = [_team(m, 1000) for m in (200, 300, 400, 450, 500, 550, 650, 750)]
        assert rate_zone(550, 1000, wide)["rating"] == "average"             # +7.5 pp over the average of this competition is not even above it

    def test_no_minimum_of_shots_a_few_shots_are_still_rated(self):
        assert rate_zone(3, 3, TEAMS)["rating"] == "above"                   # 100 % on 3 shots: above, with the low-sample flag as the only hint
        assert rate_zone(3, 3, TEAMS)["low_sample"] is True

    def test_low_sample_flag_is_a_hint_only(self):
        assert rate_zone(4, 9, TEAMS)["low_sample"] is True
        assert rate_zone(5, 10, TEAMS)["low_sample"] is False

    def test_a_player_with_one_shot_does_not_move_the_players_quartiles(self):
        players = [_team(m, 50) for m in (15, 17, 19, 21, 23, 25)] + [_team(1, 1), _team(0, 1)]       # two players with a single shot
        assert rate_zone(25, 50, players)["rating"] == "above"
        assert rate_zone(15, 50, players)["rating"] == "below"

    def test_no_shots_is_none(self):
        r = rate_zone(0, 0, TEAMS)
        assert r["rating"] == "none" and r["delta_pp"] is None and r["league_pct"] == pytest.approx(47.0) and r["percentile"] is None

    def test_a_competition_without_shots_in_the_zone_is_unknown(self):
        assert rate_zone(5, 10, [])["rating"] == "unknown"
        assert rate_zone(5, 10, [_team(0, 0)])["rating"] == "unknown"

    def test_a_single_entity_is_its_own_reference_and_so_average(self):
        assert rate_zone(30, 100, [_team(30, 100)])["rating"] == "average"

    def test_percentile_is_the_weighted_position_with_half_of_the_ties(self):
        # the team at 46 % has two teams under it (40, 42, 44) → three; ties count half: (3 + 0.5) / 8
        assert rate_zone(46, 100, TEAMS)["percentile"] == pytest.approx(100 * 3.5 / 8)
        assert rate_zone(54, 100, TEAMS)["percentile"] == pytest.approx(100 * 7.5 / 8)


def _entity(**zones):
    return {z: {"fga": fga, "fgm": fgm} for z, (fgm, fga) in zones.items()}


class TestRateZones:
    ZONES = [
        {"zone": "paint", "fga": 100, "fgm": 54, "fg_pct": 54.0},
        {"zone": "top_three", "fga": 0, "fgm": 0, "fg_pct": 0.0},
        {"zone": "corner_left", "fga": 20, "fgm": 5, "fg_pct": 25.0},
    ]

    ENTITIES = [_entity(paint=(m, 100), top_three=(30, 100)) for m in (40, 42, 44, 46, 48, 50, 52, 54)]

    def test_adds_rating_fields_per_zone_keeping_the_originals(self):
        out = rate_zones(self.ZONES, self.ENTITIES)
        assert out[0]["zone"] == "paint" and out[0]["fg_pct"] == 54.0 and out[0]["rating"] == "above"
        assert out[1]["rating"] == "none"
        assert out[2]["rating"] == "unknown"                                  # no entity shot there

    def test_without_entities_every_zone_is_unknown(self):
        assert [z["rating"] for z in rate_zones(self.ZONES, [])] == ["unknown", "none", "unknown"]

    def test_inputs_are_not_mutated(self):
        rate_zones(self.ZONES, self.ENTITIES)
        assert "rating" not in self.ZONES[0]
