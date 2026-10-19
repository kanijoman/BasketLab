"""The consumers that still estimated possessions with 0.45 use the common estimate (0.44) and, when the game has them, its exact
possessions and validated rebounds / turnovers (#379): the weekly report's last match, the player sheet and the IN/OUT blocks."""
import pytest

from src.api.routers.players import _enrich_stat_block
from src.services.weekly_report_service import WeeklyReportService
from src.stats.match_derived import with_derived
from src.stats.stats_calculator import StatsCalculator


def _box(**kw):
    base = {"pts": 80, "p2m": 20, "p2a": 38, "p3m": 8, "p3a": 22, "p1m": 14, "p1a": 20, "ro": 10, "rd": 25, "assist": 15, "st": 7, "to": 12, "bs": 3}
    base.update({k: str(v) for k, v in kw.items()})
    return {k: str(v) if not isinstance(v, str) else v for k, v in base.items()}


def test_the_single_match_possessions_use_the_common_estimate_of_a_free_throw():
    team = _box()                    # FGA 60, FTA 20, TOV 12, ORB 10
    stats = StatsCalculator().calculate_single_match_stats(team, _box())

    assert stats["possessions_per_game"] == pytest.approx(60 + 0.44 * 20 + 12 - 10)       # 70.8, not 71


def test_given_possessions_replace_the_estimate_and_feed_the_ratings():
    stats = StatsCalculator().calculate_single_match_stats(_box(pts=80), _box(pts=70), possessions=75.0, opp_possessions=72.0)

    assert stats["possessions_per_game"] == 75.0
    assert stats["offensive_rating"] == pytest.approx(80 / 75 * 100)
    assert stats["defensive_rating"] == pytest.approx(70 / 72 * 100)


def _game(derived=True):
    doc = {"HEADER": {"starttime": "05-10-2025 - 12:30", "TEAM": [{"id": "A", "name": "Local"}, {"id": "B", "name": "Visitante"}]},
           "BOXSCORE": {"TEAM": [{"id": "A", "TOTAL": {**_box(), "name": "Local"}}, {"id": "B", "TOTAL": {**_box(pts=70, ro=8, rd=20, to=14), "name": "Visitante"}}]}}
    if derived:
        doc["DERIVED"] = {"v": 5, "TEAM": [{"id": "A", "possessions": 75.0, "orb": 13, "drb": 26, "tov": 13},
                                           {"id": "B", "possessions": 72.0, "orb": 9, "drb": 22, "tov": 15}]}
    return doc


def test_with_derived_overrides_rebounds_turnovers_and_gives_the_exact_possessions():
    game = _game()
    own, rival, poss, opp_poss = with_derived(game["BOXSCORE"]["TEAM"][0]["TOTAL"], game["BOXSCORE"]["TEAM"][1]["TOTAL"], game, 0)

    assert (own["ro"], own["rd"], own["to"]) == (13, 26, 13) and (rival["ro"], rival["rd"], rival["to"]) == (9, 22, 15)
    assert (poss, opp_poss) == (75.0, 72.0)
    assert game["BOXSCORE"]["TEAM"][0]["TOTAL"]["ro"] == "10"          # the stored box score is not touched


def test_with_derived_looks_at_the_team_by_index_so_it_works_from_either_side():
    game = _game()
    own, rival, poss, opp_poss = with_derived(game["BOXSCORE"]["TEAM"][1]["TOTAL"], game["BOXSCORE"]["TEAM"][0]["TOTAL"], game, 1)

    assert (own["ro"], rival["ro"], poss, opp_poss) == (9, 13, 72.0, 75.0)


def test_without_derived_fields_nothing_changes():
    game = _game(derived=False)
    own, rival, poss, opp_poss = with_derived(game["BOXSCORE"]["TEAM"][0]["TOTAL"], game["BOXSCORE"]["TEAM"][1]["TOTAL"], game, 0)

    assert own == game["BOXSCORE"]["TEAM"][0]["TOTAL"] and (poss, opp_poss) == (None, None)


def test_the_weekly_last_match_uses_the_exact_figures_of_the_game_when_they_exist():
    stats = WeeklyReportService._feb_last_match_stats(StatsCalculator(), _game(), 0, "Local")

    sel, opp, opp_name, _ = stats
    assert sel["possessions_per_game"] == 75.0 and opp["possessions_per_game"] == 72.0 and opp_name == "Visitante"
    assert sel["offensive_rebounds_per_game"] == 13 and sel["turnovers_per_game"] == 13


def test_the_weekly_last_match_falls_back_to_the_estimate_without_derived_fields():
    sel, opp, _, _ = WeeklyReportService._feb_last_match_stats(StatsCalculator(), _game(derived=False), 0, "Local")

    assert sel["possessions_per_game"] == pytest.approx(60 + 0.44 * 20 + 12 - 10)
    assert opp["possessions_per_game"] > 0


def test_the_player_sheet_blocks_use_the_common_free_throw_cost():
    block = _enrich_stat_block({"fga_2": 40, "fga_3": 20, "fta": 10, "tov": 8, "orb": 6, "points_for": 66, "minutes": 40,
                                "opp_fga_2": 35, "opp_fga_3": 20, "opp_fta": 10, "opp_tov": 9, "opp_orb": 5, "points_against": 60})

    assert block["possessions"] == pytest.approx(60 + 0.44 * 10 + 8 - 6, abs=0.05)             # 66.4, not 66.5
    assert block["offensive_rating"] == pytest.approx(66 / 66.4 * 100, abs=0.05)
