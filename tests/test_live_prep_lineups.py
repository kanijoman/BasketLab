"""``tables.lineups`` of the package (issue #248): the most played quintets of both teams over the season, and parity of the live
engine's quintets with the calculator of the web (``src/database/lineup_stats_calculator.py``)."""
import pytest

from src.live_core.engine import LiveEngine
from src.live_prep.package_builder import LINEUPS_PER_TEAM, SeasonAccumulator, build_package

A, B = "982047", "981204"
STAMP = "2026-10-08T00:00:00Z"


def package(games, team=A, rival=B):
    acc = SeasonAccumulator()
    for g in games:
        acc.add_game(g)
    return acc.to_package("FEB_TEST", "2025-2026", team, rival, None, STAMP)


def test_the_package_lists_the_most_played_quintets_of_both_teams(feb_game_doc):
    rows = package([feb_game_doc]).tables["lineups"]
    snapshot = LiveEngine().update(feb_game_doc)
    for tid in (A, B):
        mine = [r for r in rows if r["team_id"] == tid]
        live = [l for l in snapshot["lineups"][tid] if l["seconds"] > 0]      # a quintet that lasted no time is not in the package
        assert 0 < len(mine) <= LINEUPS_PER_TEAM and len(mine) == min(len(live), LINEUPS_PER_TEAM)
        assert [r["seconds"] for r in mine] == sorted((r["seconds"] for r in mine), reverse=True)
        top = mine[0]
        assert top["players"] == live[0]["players"] and top["seconds"] == live[0]["seconds"] and top["games"] == 1
        assert top["net40"] == pytest.approx((top["pts_for"] - top["pts_against"]) / top["seconds"] * 2400, abs=0.06)


def test_the_totals_add_up_over_the_games_and_count_in_how_many_they_appeared(feb_game_doc):
    one = package([feb_game_doc]).tables["lineups"]
    two = package([feb_game_doc, feb_game_doc]).tables["lineups"]
    a1 = next(r for r in one if r["team_id"] == A)
    a2 = next(r for r in two if r["team_id"] == A and r["players"] == a1["players"])
    assert a2["seconds"] == 2 * a1["seconds"] and a2["pts_for"] == 2 * a1["pts_for"] and a2["games"] == 2 and a2["stints"] == 2 * a1["stints"]


def test_build_package_gives_the_same_lineups(feb_game_doc):
    built = build_package([feb_game_doc], "FEB_TEST", "2025-2026", A, B, created_at=STAMP)
    assert built.tables["lineups"] == package([feb_game_doc]).tables["lineups"]


def test_a_team_that_was_not_asked_for_has_no_rows(feb_game_doc):
    rows = package([feb_game_doc], team=A, rival="999999").tables["lineups"]
    assert {r["team_id"] for r in rows} == {A}


# --- parity with the web's calculator ---------------------------------------------------------------------------------

def test_the_live_quintets_agree_with_the_lineup_calculator_of_the_web(feb_game_doc):
    """The calculator samples the game every 5 seconds and counts the actions on the edges of a segment twice, so the numbers are
    compared with that tolerance: minutes within 0.3 and points within 3, most of them equal."""
    from src.database.lineup_extractor import LineupExtractor
    from src.database.lineup_stats_calculator import LineupStatsCalculator
    from src.database.playbyplay_analyzer import PlayByPlayAnalyzer

    analyzer = PlayByPlayAnalyzer(feb_game_doc, False)
    extractor, calculator = LineupExtractor(analyzer), LineupStatsCalculator(analyzer)
    snapshot = LiveEngine().update(feb_game_doc)
    compared = equal = 0
    for tid in (A, B):
        for live in snapshot["lineups"][tid][:6]:
            web = calculator.calculate_lineup_stats_single_game(analyzer, extractor, tid, frozenset(live["players"]))
            assert abs(live["seconds"] / 60 - web["minutes"]) <= 0.3
            assert abs(live["pts_for"] - web["points_for"]) <= 3 and abs(live["pts_against"] - web["points_against"]) <= 3
            compared += 2
            equal += (live["pts_for"] == web["points_for"]) + (live["pts_against"] == web["points_against"])
    assert compared == 24 and equal >= 0.7 * compared
