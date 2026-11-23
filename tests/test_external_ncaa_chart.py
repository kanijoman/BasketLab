"""The shot chart of a NCAA game in the canonical document (#1062, D4 of epic #872): the coordinates of ESPN as FEB writes them.

Measured on the real games of ``tests/fixtures/ncaa`` (23/11/2026): ESPN gives every field goal ``coordinate`` in FEET over ONE half court that is already folded (both teams shoot at the same basket),
``x`` across the court from 0 to 50 and ``y`` along it from the hoop (the basket is at ``x = 25, y = 0``: the distance the text says, «25-foot three point jumper», fits it with 0.36 feet of error over 283
shots). They become FEB's percentages of the WHOLE court like ACB's: the home team at the left basket and the visitor at the right one, the distances to the hoop kept (the three-point line of both
sexes is the international 6.75 m since 2021/22, the same the zones of the engine use). As in ACB and in FEB, the chart has EXACTLY the field goals of the play by play: a chart with some missing would make
every zone look different, so a game with any field goal without coordinates (or without play by play) publishes none.
"""
import copy

import pytest

from ncaa_helpers import fixture

from src.external.ncaa_canonical import chart_shots, ncaa_coordinates, to_canonical
from src.external.ncaa_page import parse_summary
from src.live_core.zones import classify_shot

ENTRY_M = {"competition": "D1 Men", "season_value": "2025", "season_label": "2025/2026", "gender": "M"}
ENTRY_F = {"competition": "D1 Women", "season_value": "2025", "season_label": "2025/2026", "gender": "F"}
REAL = [("game_mens_401829197", ENTRY_M), ("game_mens_ot_401812120", ENTRY_M), ("game_mens_nond1_401823428", ENTRY_M), ("game_womens_401825641", ENTRY_F),
        ("game_womens_ot_401827769", ENTRY_F), ("game_womens_nond1_401817303", ENTRY_F)]


def doc(name, entry):
    return to_canonical(parse_summary(fixture(name)), entry, {})


def field_goals(game):
    return [p for p in game["plays"] if p["shooting"] and p["points_attempted"] in (2, 3)]


class TestTheCoordinates:
    def test_the_hoop_is_where_feb_has_it_at_the_basket_of_each_team(self):
        home = ncaa_coordinates(25, 0, 0)
        away = ncaa_coordinates(25, 0, 1)
        assert home == (5.62, 50.0) and away == (94.38, 50.0)                 # 1.575 m of 28 m from the baseline, in the middle of the width

    def test_a_shot_to_the_left_and_a_shot_to_the_right_are_on_opposite_sides_of_the_width(self):
        assert ncaa_coordinates(10, 10, 0)[1] < 50 < ncaa_coordinates(40, 10, 0)[1]

    def test_the_distance_to_the_hoop_is_kept_in_metres(self):
        """23 feet straight out from the hoop is 7.01 m: 1.575 + 7.01 = 8.59 m of the 28 of the court."""
        assert ncaa_coordinates(25, 23, 0)[0] == pytest.approx((1.575 + 23 * 0.3048) / 28 * 100, abs=0.01)

    def test_a_point_outside_the_court_is_kept_inside_it(self):
        x, y = ncaa_coordinates(-3, -9, 0)
        assert 0 <= x <= 100 and 0 <= y <= 100


class TestTheChartOfARealGame:
    @pytest.mark.parametrize("name,entry", REAL)
    def test_every_field_goal_of_the_play_by_play_has_its_shot_and_the_free_throws_do_not(self, name, entry):
        game = parse_summary(fixture(name))
        d = doc(name, entry)
        assert len(d["SHOTCHART"]["SHOTS"]) == len(field_goals(game)) > 0
        assert all(p["shooting"] for p in field_goals(game)) and len(d["SHOTCHART"]["SHOTS"]) < sum(1 for p in game["plays"] if p["shooting"])

    @pytest.mark.parametrize("name,entry", REAL)
    def test_the_zone_of_each_shot_is_one_of_two_points_or_three_as_ESPN_says_in_all_of_them(self, name, entry):
        """718 of 718 field goals of the six real games: the zone the engine gives the shot says 3 points exactly when ESPN says it was a three."""
        game = parse_summary(fixture(name))
        shots = doc(name, entry)["SHOTCHART"]["SHOTS"]
        assert [classify_shot(s)["points"] for s in shots] == [p["points_attempted"] for p in field_goals(game)]

    def test_a_shot_has_what_a_feb_shot_has_in_the_order_of_the_game(self):
        game = parse_summary(fixture("game_mens_401829197"))
        shots = doc("game_mens_401829197", ENTRY_M)["SHOTCHART"]["SHOTS"]
        assert len(shots) == 120 and shots[0] == {"m": "0", "t": "19:44", "x": "24.13", "y": "13.42", "team": "0", "player": "21", "quarter": "1"}
        assert shots[1]["team"] == "1" and shots[1]["player"] == "15"                       # Graham Ike, the visitor
        assert [s["quarter"] for s in shots] == sorted((s["quarter"] for s in shots), key=int) and [s["m"] for s in shots].count("1") == sum(1 for p in field_goals(game) if p["scoring"])

    def test_the_shooter_is_told_by_the_number_of_his_shirt_and_the_team_by_its_slot(self):
        d = doc("game_mens_401829197", ENTRY_M)
        miss = next(s for s in d["SHOTCHART"]["SHOTS"] if s["t"] == "19:44" and s["quarter"] == "1")
        assert miss["team"] == "0" and miss["player"] == "21" and miss["m"] == "0"                 # Ace Glass, Washington State (home, slot 0)

    def test_the_chart_lists_the_teams_with_their_players_as_feb_does(self):
        chart = doc("game_mens_401829197", ENTRY_M)["SHOTCHART"]
        assert [t["id"] for t in chart["TEAM"]] == ["ncaa:265", "ncaa:2250"] and {"id", "no", "name"} == set(chart["TEAM"][0]["PLAYER"][0])
        assert chart["quarters"] is None and chart["duration"] is None


class TestWhenTheChartIsNotComplete:
    def test_a_field_goal_without_coordinates_leaves_the_chart_empty_not_half_of_it(self):
        game = parse_summary(fixture("game_mens_401829197"))
        next(p for p in game["plays"] if p["shooting"] and p["points_attempted"] == 3).update(x=None, y=None)
        shots, covered, total = chart_shots(game)
        assert covered == total - 1 and len(shots) == covered
        chart = to_canonical(game, ENTRY_M, {})["SHOTCHART"]
        assert chart["SHOTS"] == [] and chart["TEAM"] == []

    def test_a_game_whose_play_by_play_came_empty_has_no_chart(self):
        chart = doc("game_womens_noplays_401830444", ENTRY_F)["SHOTCHART"]
        assert chart["SHOTS"] == [] and chart["TEAM"] == []

    def test_the_conversion_changes_nothing_of_what_was_read(self):
        game = parse_summary(fixture("game_womens_401825641"))
        before = copy.deepcopy(game)
        to_canonical(game, ENTRY_F, {})
        assert game == before


class TestWhatIsPublished:
    """The shots section of ``web-data-ext`` reads this chart: like the rows (#1061), only the Division I teams are published; the chart of the game keeps both."""

    def rows(self, name, entry):
        from db_helpers import new_mock_db

        from src.local_data.shots_export import export_shots

        db = new_mock_db("BASKETBALL")
        db["NCAA_D1_Men_2025_MAC"].insert_one({**doc(name, entry), "_reliable": True})
        return export_shots(db["NCAA_D1_Men_2025_MAC"], "NCAA_D1_Men_2025_MAC")["shots"]

    def test_the_shots_of_a_team_that_is_not_division_i_are_not_published(self):
        rows = self.rows("game_mens_nond1_401823428", ENTRY_M)
        game = parse_summary(fixture("game_mens_nond1_401823428"))
        buffalo = sum(1 for p in field_goals(game) if p["team_id"] == "2084")
        assert {r[0] for r in rows} == {"ncaa:2084"} and len(rows) == buffalo > 0
        assert len(doc("game_mens_nond1_401823428", ENTRY_M)["SHOTCHART"]["SHOTS"]) == len(field_goals(game)) > buffalo          # the chart of the game keeps both

    def test_both_teams_of_a_game_between_two_division_i_teams_are_published(self):
        rows = self.rows("game_mens_401829197", ENTRY_M)
        assert {r[0] for r in rows} == {"ncaa:265", "ncaa:2250"} and len(rows) == 120

    def test_the_shooter_is_the_player_of_that_shirt_in_the_team_that_took_the_shot(self):
        rows = self.rows("game_mens_401829197", ENTRY_M)
        assert any(r[0] == "ncaa:265" and r[1] == "ncaa:5313054" for r in rows)                  # Ace Glass, number 21
