"""The PBP quality audit does not blame the PBP for a box that the source delivered incomplete (#815).

FBCYL gives the rebounds of the audit from the PLAYERS of the box (the PBP does not count team rebounds, and neither does that sum), so a game whose
player list is truncated — the real one of 17/10/2026, Unileón 102–31 Artchivo: 2 players and none, ``fbcyl_game_incomplete_box`` — made the
rebounds «wrong» (8/2 and 0/0 against 25/27 and 5/18) and the score 70 %, when shots and turnovers agree with the team totals. The box is incomplete when the points of
its players do not add up to the points of its team (true in 136 of the other 138 team-games of the first group, and in none of the complete ones).
"""
import gzip
import json
from pathlib import Path

import pytest

from src.services.pbp_quality_service import PBPQualityService

FIXTURES = Path(__file__).parent / "fixtures"


def load(name):
    with gzip.open(FIXTURES / name, "rt", encoding="utf-8") as fh:
        return json.load(fh)


def row_of(game):
    return PBPQualityService(game, True, "FBCYL_1_A-1", "g").compute()[0]


def score(row):
    return float(row["Quality_Score"].rstrip("%"))


def test_a_box_with_a_truncated_player_list_does_not_lower_the_score_with_rebounds():
    row = row_of(load("fbcyl_game_incomplete_box.json.gz"))
    assert score(row) > 90                                              # it was 70.38 % because of rebounds compared with 2 + 0 players
    assert row["Local_BS_RebO"] == 8 and row["Local_PBP_RebO"] == 25    # the columns still show both, so the reader sees what was compared


def test_the_row_says_which_team_has_the_incomplete_box_and_why():
    row = row_of(load("fbcyl_game_incomplete_box.json.gz"))
    assert "UNILEON" in row["Aviso"].upper() and "ART-CHIVO" in row["Aviso"].upper()
    assert "24 de 102" in row["Aviso"] and "0 de 31" in row["Aviso"]    # what its players add up to, against what the team scored


def test_a_complete_box_has_no_warning_and_keeps_its_score():
    row = row_of(load("fbcyl_game_ok.json.gz"))
    assert row["Aviso"] == ""
    assert row["Quality_Score"] == "99.49%"                              # the value before the change: complete boxes are scored as ever


def test_only_the_team_with_the_incomplete_box_loses_its_rebounds_from_the_score():
    game = load("fbcyl_game_ok.json.gz")
    first = game["stats"]["teams"][0]
    first["players"] = first["players"][:2]                              # the same truncation, in a game that was fine
    row = row_of(game)
    assert row["Aviso"] != ""
    assert row["Rival_PBP_RebD"] == row["Rival_BS_RebD"]                 # the rival's box is untouched (and its rebounds are still scored)
    assert score(row) >= 98                                              # nothing is blamed on the PBP: the rebounds of the incomplete team are not scored


def test_a_team_without_score_in_its_data_cannot_be_judged_and_is_not_flagged():
    game = load("fbcyl_game_ok.json.gz")
    for team in game["stats"]["teams"]:
        team["data"].pop("score", None)
    assert row_of(game)["Aviso"] == ""


def test_a_feb_game_is_never_flagged_its_box_comes_from_the_team_total():
    from tests.test_pbp_quality_service import _feb_game
    row = PBPQualityService(_feb_game(), False, "FEB_X", "g").compute()[0]
    assert row["Aviso"] == ""


def test_the_warning_is_the_last_column_so_the_old_positions_do_not_move():
    assert PBPQualityService.CSV_COLUMNS[-1] == "Aviso"
    assert PBPQualityService.CSV_COLUMNS[:5] == ["ID_Partido", "Coleccion", "Equipo_Local", "Equipo_Rival", "Quality_Score"]
