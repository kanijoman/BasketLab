"""The reconciliation report of the FIBA source (#887, D3a; the common acceptance criterion of #884): ``python scripts/fiba_reconciliation_report.py`` over the real pages of ``tests/fixtures/fiba``.

It says, per statistic, how many team-games of the official box the play-by-play reproduces and, for the minutes (which ``reconcile_game`` does not count yet, #963), how close the ones worked out from the substitutions and
the starting five of the page come to the official ones. The numbers of ``docs/evaluaciones/2026-11-18_fiba-cuadre.md`` are the ones this prints.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import fiba_reconciliation_report as report  # noqa: E402

from src.market.box_reconciliation import CORE_STATS, INFO_STATS  # noqa: E402


def test_every_real_game_reconciles_on_every_statistic():
    summary = report.build_summary()
    assert (summary["games"], summary["team_games"], summary["reliable"]) == (6, 12, 6)
    assert set(summary["stats"]) == set(CORE_STATS) | set(INFO_STATS)
    assert all(entry["checked"] == 12 and entry["match"] == 12 and not entry["mismatches"] for entry in summary["stats"].values())
    assert summary["unreliable"] == []


def test_the_games_are_the_ones_of_three_competitions_with_an_overtime_among_them():
    games = report.build_summary()["detail"]
    assert {g["competition"] for g in games} == {"FIBA U18 EuroBasket", "FIBA U16 Women's EuroBasket", "FIBA EuroBasket", "FIBA Women's EuroBasket"}
    assert any(g["periods"] == 5 for g in games) and all(g["events"] > 400 for g in games)


def test_the_minutes_worked_out_from_the_substitutions_are_within_a_second_or_two_of_the_official_ones():
    minutes = report.build_summary()["minutes"]
    assert minutes["player_games"] == 133 and minutes["within_2_s"] == 133
    assert minutes["exact"] >= 100 and minutes["worst_s"] <= 1


def test_the_minutes_of_a_team_add_up_to_five_players_for_the_whole_game():
    """The five on court at every moment: the minutes of the players of a team add up to 5 x the length of the game."""
    for name, played in report.team_minutes().items():
        assert played["got"] == 5 * played["length"] and abs(played["official"] - 5 * played["length"]) <= 1, name        # the official one may be a second off: it rounds each player


def test_the_flag_of_having_played_is_not_reliable_minutes_are():
    """Game 125803: Clemens Sokolov is on court 1:14 (his substitutions say it and so does the official box) and the page marks him ``HasPlayed: False``, with no statistic at all."""
    game = report.load("125803")
    sokolov = next(p for t in game["teams"] for p in t["players"] if p["name"] == "Clemens Sokolov")
    assert sokolov["stats"]["HasPlayed"] is False and sokolov["stats"]["TP"] == "1:14"
    assert report.played(sokolov) is True
    worked = next(report.minutes_from_substitutions(game, t) for t in game["teams"] if t["org_id"] == next(x["org_id"] for x in game["teams"] if sokolov in x["players"]))
    assert worked[sokolov["person_id"]] == 74


def test_it_renders_the_same_report_twice_and_says_what_it_did_not_check():
    first, second = report.render(report.build_summary()), report.render(report.build_summary())
    assert first == second
    assert "6 partidos" in first and "12 equipo-partido" in first and "mapa de tiro" in first
