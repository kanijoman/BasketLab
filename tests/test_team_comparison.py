"""Comparative reports of the weekly report, on the web (issue #607): home vs away, won vs lost, a stretch vs the rest of the season.

``GET /teams/{collection}/compare?by=venue|result|period`` asks the season figures twice (``TeamStatsService.load_season_data``) with the two sides of the comparison and says, per
team, both groups and the REAL difference (group 1 minus group 2, in the unit of the figure: points for a percentage), for the team and for what its rivals did against it. The
weekly report showed the first group with an arrow; the arrow is gone (issue #608).
"""
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.api.app import app
from src.api.deps import get_db
from src.services.team_comparison_service import COMPARED_FIELDS, TeamComparisonService

V1 = "/api/v1"


def stat(name, ppg=80.0, **kw):
    base = {"team_name": name, "_id": f"id-{name}", "team_id": f"id-{name}", "total_games": 5, "games_home": 3, "games_away": 2, "points_per_game": ppg,
            "fg3_percentage": 33.0, "offensive_rating": 100.0, "defensive_rating": 98.0, "turnovers_per_game": 12.0, "internal_noise": "x"}
    base.update(kw)
    return base


def season(groups):
    """A ``load_season_data`` that answers by the filters it is given: ``groups`` maps a key of the filters to what it returns."""
    calls = []

    def load(collection, date_filter=None, venue_filter=None, result_filter=None):
        calls.append({"date_filter": date_filter, "venue_filter": venue_filter, "result_filter": result_filter})
        key = ("venue", venue_filter) if venue_filter is not None else ("result", result_filter) if result_filter else ("date", "range" if date_filter and "$not" not in date_filter else "rest")
        return groups[key]
    load.calls = calls
    return load


def service(groups):
    handler = MagicMock()
    svc = TeamComparisonService(handler)
    svc._stats.load_season_data = season(groups)
    return svc


HOME = {"team_stats": [stat("Alfa", 85.0), stat("Bravo", 70.0, fg3_percentage=30.0)], "opponent_stats": [stat("Alfa", 75.0), stat("Bravo", 80.0)]}
AWAY = {"team_stats": [stat("Alfa", 78.0), stat("Bravo", 72.5, fg3_percentage=33.5)], "opponent_stats": [stat("Alfa", 77.0), stat("Bravo", 76.0)]}
GROUPS = {("venue", True): HOME, ("venue", False): AWAY, ("result", "won"): HOME, ("result", "lost"): AWAY, ("date", "range"): HOME, ("date", "rest"): AWAY}


class TestTheDifference:
    def test_it_is_the_first_group_minus_the_second_in_the_unit_of_the_figure(self):
        row = {r["team_name"]: r for r in service(GROUPS).compare("C", "venue")["team"]}
        assert row["Alfa"]["diff"]["points_per_game"] == pytest.approx(7.0)
        assert row["Bravo"]["diff"]["points_per_game"] == pytest.approx(-2.5)
        assert row["Bravo"]["diff"]["fg3_percentage"] == pytest.approx(-3.5)              # percentage points, not a percentage of a percentage

    def test_both_groups_are_in_the_row_with_their_games(self):
        alfa = {r["team_name"]: r for r in service(GROUPS).compare("C", "venue")["team"]}["Alfa"]
        assert alfa["a"]["points_per_game"] == 85.0 and alfa["b"]["points_per_game"] == 78.0
        assert (alfa["games_a"], alfa["games_b"]) == (5, 5)

    def test_only_the_figures_of_the_tables_travel(self):
        alfa = service(GROUPS).compare("C", "venue")["team"][0]
        assert "internal_noise" not in alfa["a"] and "_id" not in alfa["a"]
        assert set(alfa["a"]) <= set(COMPARED_FIELDS) and "points_per_game" in alfa["a"]

    def test_what_the_rivals_did_against_each_team_is_compared_too(self):
        rival = {r["team_name"]: r for r in service(GROUPS).compare("C", "venue")["opponent"]}
        assert rival["Alfa"]["diff"]["points_per_game"] == pytest.approx(-2.0)

    def test_a_figure_missing_in_one_group_has_no_difference_and_zero_is_not_missing(self):
        groups = {**GROUPS, ("venue", False): {"team_stats": [stat("Alfa", 78.0, fg3_percentage=None, turnovers_per_game=0.0), stat("Bravo")], "opponent_stats": []}}
        alfa = {r["team_name"]: r for r in service(groups).compare("C", "venue")["team"]}["Alfa"]
        assert "fg3_percentage" not in alfa["diff"]
        assert alfa["diff"]["turnovers_per_game"] == pytest.approx(12.0)                  # 12 - 0

    def test_rows_are_sorted_by_team_name(self):
        assert [r["team_name"] for r in service(GROUPS).compare("C", "venue")["team"]] == ["Alfa", "Bravo"]


class TestWhoIsInTheTable:
    def test_a_team_with_games_in_only_one_group_is_there_with_the_other_empty(self):
        groups = {**GROUPS, ("venue", False): {"team_stats": [stat("Alfa", 78.0)], "opponent_stats": []}}
        rows = {r["team_name"]: r for r in service(groups).compare("C", "venue")["team"]}
        assert rows["Bravo"]["b"] is None and rows["Bravo"]["diff"] == {} and rows["Bravo"]["games_b"] == 0
        assert rows["Alfa"]["diff"]

    def test_teams_are_matched_by_name_so_a_fbcyl_id_that_is_a_dict_works(self):
        a = {"team_stats": [stat("Alfa", 90.0, _id={"id": 1}, team_id={"id": 1})], "opponent_stats": []}
        b = {"team_stats": [stat("Alfa", 80.0, _id={"id": 1}, team_id={"id": 1})], "opponent_stats": []}
        out = service({**GROUPS, ("venue", True): a, ("venue", False): b}).compare("C", "venue")["team"]
        assert len(out) == 1 and out[0]["diff"]["points_per_game"] == pytest.approx(10.0)

    def test_empty_collection_gives_empty_lists(self):
        empty = {"team_stats": [], "opponent_stats": []}
        out = service({**GROUPS, ("venue", True): empty, ("venue", False): empty}).compare("C", "venue")
        assert out["team"] == [] and out["opponent"] == []


class TestTheTwoSides:
    def test_venue_asks_for_home_and_away(self):
        svc = service(GROUPS)
        out = svc.compare("C", "venue")
        assert [(c["venue_filter"]) for c in svc._stats.load_season_data.calls] == [True, False]
        assert (out["label_a"], out["label_b"]) == ("Local", "Visitante")

    def test_result_asks_for_won_and_lost(self):
        svc = service(GROUPS)
        out = svc.compare("C", "result")
        assert [c["result_filter"] for c in svc._stats.load_season_data.calls] == ["won", "lost"]
        assert (out["label_a"], out["label_b"]) == ("Ganados", "Perdidos")

    def test_a_stretch_is_the_range_and_the_rest_is_everything_outside_it(self):
        svc = service(GROUPS)
        out = svc.compare("C", "period", date_from=datetime(2026, 10, 1), date_to=datetime(2026, 10, 15))
        first, second = svc._stats.load_season_data.calls
        assert first["date_filter"] == {"$gte": datetime(2026, 10, 1), "$lte": datetime(2026, 10, 15)}
        assert second["date_filter"] == {"$not": first["date_filter"]}                    # before it AND after it
        assert (out["label_a"], out["label_b"]) == ("Tramo", "Resto de la temporada")

    @pytest.mark.parametrize("kw,expected", [({"date_from": datetime(2026, 10, 1)}, {"$gte": datetime(2026, 10, 1)}),
                                             ({"date_to": datetime(2026, 10, 15)}, {"$lte": datetime(2026, 10, 15)})])
    def test_an_open_ended_stretch_is_a_stretch_too(self, kw, expected):
        svc = service(GROUPS)
        svc.compare("C", "period", **kw)
        assert svc._stats.load_season_data.calls[0]["date_filter"] == expected

    def test_a_stretch_needs_at_least_one_date(self):
        with pytest.raises(ValueError, match="fecha"):
            service(GROUPS).compare("C", "period")

    def test_an_unknown_comparison_is_refused(self):
        with pytest.raises(ValueError):
            service(GROUPS).compare("C", "month")


class TestTheEndpoint:
    @pytest.fixture
    def client(self):
        app.dependency_overrides[get_db] = lambda: MagicMock()
        yield TestClient(app)
        app.dependency_overrides.clear()

    def get(self, client, query):
        with patch("src.services.team_comparison_service.TeamStatsService.load_season_data", side_effect=season(GROUPS)):
            return client.get(f"{V1}/teams/LF/compare?{query}")

    def test_it_answers_each_comparison(self, client):
        for by in ("venue", "result"):
            r = self.get(client, f"by={by}")
            assert r.status_code == 200 and r.json()["team"][0]["diff"]["points_per_game"] == pytest.approx(7.0)

    def test_the_stretch_reads_from_date_and_to_date(self, client):
        r = self.get(client, "by=period&from_date=2026-10-01&to_date=2026-10-15")
        assert r.status_code == 200 and r.json()["label_a"] == "Tramo"

    def test_a_stretch_without_dates_is_a_bad_request_and_an_unknown_comparison_is_refused(self, client):
        assert self.get(client, "by=period").status_code == 400
        assert self.get(client, "by=month").status_code == 422
        assert self.get(client, "by=period&from_date=not-a-date").status_code in (400, 422)

    def test_it_is_a_public_read(self, client):
        assert self.get(client, "by=venue").status_code == 200


class TestFbcylDateFilter:
    def test_the_dates_inside_a_not_are_normalised_to_the_start_of_the_day_like_the_others(self):
        from src.database.aggregation.fbcyl_pipeline import FBCYLPipelineBuilder
        flt = {"$not": {"$gte": datetime(2026, 10, 1, 17, 30), "$lte": datetime(2026, 10, 15, 21, 0)}}
        pipeline = FBCYLPipelineBuilder.build_team_stats_pipeline(flt)
        match = next(stage["$match"]["parsedDate"] for stage in pipeline if "$match" in stage and "parsedDate" in stage["$match"])
        assert match == {"$not": {"$gte": datetime(2026, 10, 1), "$lte": datetime(2026, 10, 15)}}
