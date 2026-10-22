"""Estimate the strength gap between divisions from real games between them (issue #464): ``python -m src.live_prep.level_gap``.

Each team has a rating (mean net rating per 100 possessions in games of its own division). A game between divisions gives ``actual - (rating A - rating B)``
for the stronger division's team, which the gap per level of difference explains.
"""
import pytest

from src.live_prep.level_gap import estimate_gap, team_ratings

RATINGS = {"A": 4.0, "B": -2.0, "C": 3.0, "D": 0.0}


def cross(a, b, level_a, level_b, margin100):
    return {"a": a, "b": b, "level_a": level_a, "level_b": level_b, "margin100": margin100}


class TestEstimate:
    def test_the_stronger_division_wins_more_than_the_ratings_say(self):
        games = [cross("A", "B", 2, 3, 11.0), cross("C", "D", 2, 3, 8.0)]       # expected 6 and 3: +5 over each, one level apart
        est = estimate_gap(games, RATINGS)
        assert est["gap"] == pytest.approx(5.0) and est["n"] == 2

    def test_the_games_are_seen_from_either_side_and_two_levels_count_double(self):
        games = [cross("B", "A", 3, 2, -11.0), cross("D", "C", 4, 2, -13.0)]     # the second: expected -3, actual -13 over two levels = 5 each
        assert estimate_gap(games, RATINGS)["gap"] == pytest.approx(5.0)

    def test_games_of_a_team_without_rating_or_of_the_same_division_do_not_count(self):
        games = [cross("A", "Z", 2, 3, 20.0), cross("A", "B", 3, 3, 20.0)]
        assert estimate_gap(games, RATINGS) == {"gap": None, "n": 0, "se": None}

    def test_it_says_how_uncertain_it_is(self):
        games = [cross("A", "B", 2, 3, 6.0), cross("C", "D", 2, 3, 12.0), cross("A", "D", 2, 3, 20.0)]
        est = estimate_gap(games, RATINGS)
        assert est["n"] == 3 and est["se"] > 0

    def test_one_game_has_no_standard_error(self):
        assert estimate_gap([cross("A", "B", 2, 3, 11.0)], RATINGS)["se"] is None


class TestRatings:
    def test_a_team_rating_is_the_mean_of_its_games_in_its_own_division(self):
        league = [{"a": "A", "b": "B", "margin100": 6.0}, {"a": "A", "b": "C", "margin100": 2.0}]
        ratings = team_ratings(league)
        assert ratings["A"] == pytest.approx(4.0) and ratings["B"] == pytest.approx(-6.0) and ratings["C"] == pytest.approx(-2.0)


class TestCollect:
    def test_the_games_between_divisions_of_a_cup_give_the_estimate(self, feb_game_doc):
        import json
        from src.live_prep.level_gap import collect

        def remap(mapping):
            text = json.dumps(feb_game_doc)
            for old, new in mapping.items():
                text = text.replace(f'"{old}"', f'"{new}"')
            return json.loads(text)

        a, b = [t["id"] for t in feb_game_doc["HEADER"]["TEAM"]]
        second_division = [remap({a: "11", b: "12"}), remap({a: "12", b: "11"})]     # teams 11 and 12 play in the division of level 3
        first_division = [remap({a: "21", b: "22"}), remap({a: "22", b: "21"})]      # 21 and 22 in level 2
        cup = [remap({a: "21", b: "11"})]                                              # a tie between the divisions
        levels = {"SEGUNDA": 3, "PRIMERA": 2}
        result = collect([("SEGUNDA", second_division), ("PRIMERA", first_division), ("COPA", cup)], levels.get)
        assert result["n"] == 1 and result["teams"] == 4 and result["gap"] is not None

    def test_without_games_between_divisions_it_says_nothing(self, feb_game_doc):
        from src.live_prep.level_gap import collect
        assert collect([("SEGUNDA", [feb_game_doc])], {"SEGUNDA": 3}.get)["gap"] is None
