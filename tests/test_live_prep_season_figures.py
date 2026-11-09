"""The package carries each player's season for the columns of the live box score that had no reference (feedback of the 0.5.2, after #699).

The box score of the app colours a column against what the player usually does; for T2, TC, FR, +/-, Val, Usg%, ORtg, DRtg, NetRtg, 3Pr and PIE% the package had nothing. Each
row of ``tables.players`` / ``tables.rival_players`` now has the per 40 minutes of fouls drawn, plus/minus and valuation (and what adds and subtracts in it, its noise), the
two and field-goal percentages shrunk to the league like the free throws, the share of the team's minutes and the season figures of the web (``live_core.boxscore.figures``,
the same code as the box score of the game, over the season totals with 200 team minutes per game). Checked with a real FEB game: a season of one game says what the live
box score said at the end of it.
"""
import pytest

from src.live_core.boxscore import build
from src.live_core.config import RuleConfig
from src.live_core.engine import LiveEngine
from src.live_prep.package_builder import SeasonAccumulator

A, B = "982047", "981204"
SEASON_ADV = ("usage", "orating", "drating", "net_rtg", "three_pr", "pie")


def package_of(games):
    acc = SeasonAccumulator()
    for g in games:
        acc.add_game(g)
    return acc.to_package(collection="FEB_TEST", season="2025-2026", team_id=A, rival_id=B, competition_meta=None, created_at="2026-11-09T00:00:00Z")


def rows(package):
    return {**package.tables["players"], **package.tables["rival_players"]}


@pytest.fixture(scope="module")
def one_game(feb_game_doc):
    final = LiveEngine().update(feb_game_doc)
    return final, build(final, {}, RuleConfig()), rows(package_of([feb_game_doc]))


def test_a_season_of_one_game_says_what_the_box_score_said_at_its_end(one_game):
    final, box, table = one_game
    assert table
    for pid, row in table.items():
        p, scale = final["players"][pid], 2400 / final["players"][pid]["minutes"]
        assert row["fd_per40"] == pytest.approx(p["fd"] * scale, abs=0.01) and row["pm_per40"] == pytest.approx(p["pm"] * scale, abs=0.01)
        assert row["val_per40"] == pytest.approx(box[pid]["val"] * scale, abs=0.01)
        for key in SEASON_ADV:
            game = box[pid]["adv"][key]                  # None under the box score's minimum minutes (a rule of the live table, not of the season)
            if game is not None:
                assert row["adv"][key] == pytest.approx(game, rel=0.02, abs=0.1), (pid, key)
    assert sum(1 for pid in table if box[pid]["adv"]["usage"] is not None) >= 10


def test_the_shooting_percentages_are_shrunk_to_the_league_like_the_free_throws(one_game):
    final, _, table = one_game
    for pid, row in table.items():
        st = final["players"][pid]["stats"]
        for pct, made, attempted in (("fg2_pct", st["fg2m"], st["fg2a"]), ("fg_pct", st["fg2m"] + st["fg3m"], st["fg2a"] + st["fg3a"])):
            assert 0 < row[pct] < 1
            if attempted >= 4 and made / attempted not in (0.0, 1.0):
                assert row[pct] != pytest.approx(made / attempted, abs=1e-9)          # pulled towards the league, not his raw percentage


def test_the_share_of_minutes_is_of_the_minutes_of_his_team(one_game):
    final, _, table = one_game
    for pid, row in table.items():
        assert row["min_share"] == pytest.approx(final["players"][pid]["minutes"] / 2400, abs=0.001)


def test_a_season_of_two_games_counts_the_totals_not_the_mean_of_each_game(feb_game_doc):
    final = LiveEngine().update(feb_game_doc)
    one, two = rows(package_of([feb_game_doc])), rows(package_of([feb_game_doc, feb_game_doc]))
    for pid in one:
        assert two[pid]["fd_per40"] == pytest.approx(one[pid]["fd_per40"]) and two[pid]["min_share"] == pytest.approx(one[pid]["min_share"])
        assert two[pid]["adv"]["usage"] == pytest.approx(one[pid]["adv"]["usage"], rel=1e-6)
    assert final["players"]


def test_with_a_real_package_every_column_of_the_box_score_has_its_colour(one_game, feb_game_doc):
    """The whole way: the package of the season, and the box score of a game with it, for a player with minutes and shots of both kinds."""
    final, _, table = one_game
    box = build(final, table, RuleConfig())
    shooters = [pid for pid, p in final["players"].items() if p["minutes"] >= 600 and p["stats"]["fg2a"] and p["stats"]["fg3a"]]
    assert shooters
    for pid in shooters:
        assert {"fg2", "fg", "fd", "pm", "val", "usage", "orating", "drating", "net_rtg", "three_pr", "pie"} <= set(box[pid]["dev"]), pid
