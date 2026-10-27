"""Weekly report tables say the REAL difference of the comparison instead of a trend arrow (issue #608).

A comparative cell reads ``78.4 (+2.1)``: the figure of the stretch and its absolute difference with the rest of the season (points for a percentage).
The cell colour keeps meaning good/bad; the arrows ⇈ ↑ ≈ ↓ ⇊ are gone.
"""
import pytest

from src.services._weekly_report_helpers import (
    ADV_FIELDS,
    BASIC_FIELDS,
    build_comparative_advanced_rows,
    build_comparative_basic_rows,
    build_last_match_rows,
)

ARROWS = "⇈↑≈↓⇊"


def col_basic(field):
    return 4 + [f for f, _ in BASIC_FIELDS].index(field)      # name + three game counts


def col_adv(field):
    return 2 + [f for f, _ in ADV_FIELDS].index(field)        # name + games


class TestComparativeTables:
    def test_basic_cell_is_the_value_and_the_signed_difference_with_the_rest(self):
        comp = [{"monthly": {"team_name": "A", "points_per_game": 80.0}, "rest": {"team_name": "A", "points_per_game": 77.9}, "deltas": {"points_per_game": 2.7}}]
        texts, _ = build_comparative_basic_rows(comp)
        assert texts[0][col_basic("points_per_game")] == "80.0 (+2.1)"

    def test_a_negative_difference_keeps_its_sign_and_zero_is_unsigned(self):
        comp = [{"monthly": {"team_name": "A", "points_per_game": 70.0, "fg3_percentage": 33.0}, "rest": {"points_per_game": 75.5, "fg3_percentage": 33.0}}]
        row = build_comparative_basic_rows(comp)[0][0]
        assert row[col_basic("points_per_game")] == "70.0 (-5.5)"
        assert row[col_basic("fg3_percentage")] == "33.0 (0.0)"

    def test_advanced_cell_says_the_difference_too(self):
        comp = [{"monthly": {"team_name": "A", "offensive_rating": 105.0, "total_games": 4}, "rest": {"offensive_rating": 100.0, "total_games": 6}}]
        texts, _ = build_comparative_advanced_rows(comp)
        assert texts[0][col_adv("offensive_rating")] == "105.0 (+5.0)"

    def test_no_arrow_is_left_in_any_cell(self):
        monthly = {"team_name": "A", **{f: 50.0 for f, _ in BASIC_FIELDS + ADV_FIELDS}}
        rest = {f: 40.0 for f, _ in BASIC_FIELDS + ADV_FIELDS}
        for build in (build_comparative_basic_rows, build_comparative_advanced_rows):
            texts, _ = build([{"monthly": monthly, "rest": rest, "deltas": {f: 25.0 for f, _ in BASIC_FIELDS + ADV_FIELDS}}])
            assert not any(ch in cell for cell in texts[0] for ch in ARROWS)

    def test_a_figure_the_rest_does_not_have_shows_only_the_value(self):
        comp = [{"monthly": {"team_name": "A", "points_per_game": 80.0}, "rest": {"team_name": "A"}}]
        texts, _ = build_comparative_basic_rows(comp)
        assert texts[0][col_basic("points_per_game")] == "80.0"

    @pytest.mark.parametrize("builder,field,col", [(build_comparative_basic_rows, "points_per_game", col_basic), (build_comparative_advanced_rows, "offensive_rating", col_adv)])
    def test_the_difference_is_the_same_in_both_directions_of_better(self, builder, field, col):
        """A figure where less is better still says value minus rest; the colour is what tells good from bad."""
        comp = [{"monthly": {"team_name": "A", field: 10.0}, "rest": {field: 12.0}}]
        assert builder(comp)[0][0][col(field)].endswith("(-2.0)")


class TestLastMatchTable:
    def test_each_cell_is_the_value_and_the_difference_with_the_season_of_the_team(self):
        field = ADV_FIELDS[1][0]
        texts, _ = build_last_match_rows({field: 110.0}, {field: 90.0}, {field: 100.0}, {field: 95.0}, "Casa", "Fuera")
        assert texts[0][col_adv(field)] == "110.0 (+10.0)"
        assert texts[1][col_adv(field)] == "90.0 (-5.0)"

    def test_without_a_season_figure_there_is_only_the_value_and_no_arrow(self):
        field = ADV_FIELDS[1][0]
        texts, _ = build_last_match_rows({field: 110.0}, {field: 90.0}, {}, {}, "Casa", "Fuera")
        assert texts[0][col_adv(field)] == "110.0" and not any(ch in texts[0][col_adv(field)] for ch in ARROWS)
