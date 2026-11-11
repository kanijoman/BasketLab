"""Issue #862: before a team has played this season its ``teamCode`` is unknown (the calendar only has ids and names), so a package of round 1 had no carry-over rating.

The team is linked to last season by its EXACT name (normalised: case, accents, spaces). Checked on the archive: every name link agreed with the teamCode link (8 of 8 in Primera FEB 2026-27).
A name that two teams of last season share is ambiguous and links nothing; an unlinked team starts at 0 as always.
"""
import pytest

from src.live_prep.package_builder import SeasonAccumulator
from src.live_prep.round_packages import build_round_packages_from_db
from src.live_prep.season_carry import carry_for, normalize_name
from test_live_prep_game_sources import OLD, SEGUNDA, Handler
from test_live_prep_season_carry_source import CODE_OWN, CODE_RIVAL, played

NEW_OWN, NEW_RIVAL = "7001", "7002"


@pytest.fixture
def last_season(feb_game_doc):
    """Last season: «ACEITES ABRIL ADBA SANFER» (CODE_OWN) beat «MANRESA CBF A» (CODE_RIVAL) twice. Nothing played yet this season."""
    games = [played(feb_game_doc, ("11", CODE_OWN, 90), ("22", CODE_RIVAL, 60), 1, "05-10-2025 - 12:00"),
             played(feb_game_doc, ("22", CODE_RIVAL, 70), ("11", CODE_OWN, 80), 2, "05-11-2025 - 12:00")]
    for g in games:
        for slot in g["HEADER"]["TEAM"]:
            slot["name"] = {CODE_OWN: " Aceites Abril  ADBA Sanfer ", CODE_RIVAL: "MANRESA CBF A"}[slot["teamCode"]]
    return {OLD: games, SEGUNDA: []}


def round_one(names=("ACEITES ABRIL ADBA SANFER", "MANRESA CBF A")):
    return [{"code": "m1", "start": None, "round": 1, "home": {"id": NEW_OWN, "name": names[0]}, "away": {"id": NEW_RIVAL, "name": names[1]}}]


def gap(world, matches):
    built = build_round_packages_from_db(Handler(world), SEGUNDA, matches, season="2026-2027")
    return built[0]["package"].baselines["net_rtg_prior"]


@pytest.mark.parametrize("text,expected", [(" Aceites  Abril ", "ACEITES ABRIL"), ("Peñas Huesca", "PENAS HUESCA"), ("", "")])
def test_names_are_compared_without_case_accents_or_extra_spaces(text, expected):
    assert normalize_name(text) == expected


def test_a_team_that_has_not_played_yet_takes_the_rating_of_its_namesake_of_last_season(last_season):
    assert gap(last_season, round_one()) > 0 == gap({SEGUNDA: []}, round_one())


def test_a_new_name_links_nothing(last_season):
    assert gap(last_season, round_one(("OTHER CLUB", "ANOTHER CLUB"))) == 0


def test_a_name_shared_by_two_teams_of_last_season_is_ambiguous(last_season):
    for slot in last_season[OLD][0]["HEADER"]["TEAM"] + last_season[OLD][1]["HEADER"]["TEAM"]:
        slot["name"] = "MISMO NOMBRE"
    carry = carry_for(Handler(last_season), SEGUNDA)
    assert carry.ratings and "MISMO NOMBRE" not in carry.names


def test_a_team_already_seen_keeps_its_teamcode_link_and_is_not_reseeded_by_name(last_season):
    acc = SeasonAccumulator(carry={CODE_OWN: 5.0}, carry_names={"ACEITES ABRIL ADBA SANFER": CODE_OWN})
    acc.ratings.update(NEW_OWN, NEW_RIVAL, 3)
    before = acc.ratings.rating(NEW_OWN)
    acc.link_names({NEW_OWN: "ACEITES ABRIL ADBA SANFER"})
    assert acc.ratings.rating(NEW_OWN) == before
