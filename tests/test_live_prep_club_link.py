"""Issue #862: before a team has played this season its teamCode is unknown, but its team page of the FEB shows the name of the CLUB (``div.box-club``), not the sponsored name.

Checked on the archive and the live pages: the club name of the 13 teams of Primera FEB that kept their teamCode from 2025-26 to 2026-27 was the same in all 13 (the sponsored name
changes: «PARTIZAN DE FUENLABRADA» / «FLEXICAR FUENLABRADA» are both «FUENLABRADA S.A.D.»). The team ids change every season, so the link is: club name of the new id == club name of the old
id of a team with a known teamCode. A club that two old teams share is ambiguous and links nothing; an unlinked team starts at 0 as always.
"""
import gzip
from pathlib import Path

import pytest

from src.live_prep.club_fetcher import fetch_club_name, normalize_club, parse_club_name
from src.live_prep.package_builder import SeasonAccumulator
from src.live_prep.round_packages import build_round_packages_from_db
from src.live_prep.season_carry import ClubLinker, carry_for
from test_live_prep_game_sources import OLD, SEGUNDA, Handler
from test_live_prep_season_carry_source import CODE_OWN, CODE_RIVAL, played

PAGE = Path(__file__).parent / "fixtures" / "feb_team_page_1008631.html.gz"
NEW_OWN, NEW_RIVAL = "7001", "7002"
CLUBS = {"11": "CLUB DEPORTIVO UNO", "22": "CLUB DEPORTIVO DOS", NEW_OWN: "Club  Deportivo UNO", NEW_RIVAL: "CLUB DEPORTIVO DOS"}


def test_the_club_name_is_read_from_a_real_team_page():
    """B.F. León: the title of the page is the sponsored name, the club is another block."""
    html = gzip.open(PAGE).read()
    assert parse_club_name(html) == "CLUB BALONCESTO FEMENINO LEON"


@pytest.mark.parametrize("html", [b"", b"<html><div class='nombre'>A PERSON</div></html>"])
def test_a_page_without_club_gives_none(html):
    assert parse_club_name(html) is None


def test_a_failing_request_gives_none():
    def broken(*args, **kwargs):
        raise RuntimeError("FEB down")

    assert fetch_club_name("1", get=broken) is None


@pytest.mark.parametrize("text,expected", [(" Peñas  Huesca ", "PENAS HUESCA"), ("OVIEDO C.B.", "OVIEDO C.B."), (None, "")])
def test_clubs_are_compared_without_case_accents_or_extra_spaces(text, expected):
    assert normalize_club(text) == expected


@pytest.fixture
def last_season(feb_game_doc):
    games = [played(feb_game_doc, ("11", CODE_OWN, 90), ("22", CODE_RIVAL, 60), 1, "05-10-2025 - 12:00"),
             played(feb_game_doc, ("22", CODE_RIVAL, 70), ("11", CODE_OWN, 80), 2, "05-11-2025 - 12:00")]
    return {OLD: games, SEGUNDA: []}


def club_source(table=CLUBS, asked=None):
    def source(team_id):
        if asked is not None:
            asked.append(str(team_id))
        return table.get(str(team_id))
    return source


def round_one():
    return [{"code": "m1", "start": None, "round": 1, "home": {"id": NEW_OWN, "name": "SPONSOR NEW"}, "away": {"id": NEW_RIVAL, "name": "OTHER SPONSOR"}}]


def gap(world, source):
    built = build_round_packages_from_db(Handler(world), SEGUNDA, round_one(), season="2026-2027", club_source=source)
    return built[0]["package"].baselines["net_rtg_prior"]


def test_a_team_that_has_not_played_yet_takes_the_rating_of_its_club_of_last_season(last_season):
    """The sponsor changed (the names of the header are others), the club is the same."""
    assert gap(last_season, club_source()) > 0 == gap(last_season, None)


def test_a_new_club_links_nothing(last_season):
    assert gap(last_season, club_source({NEW_OWN: "A NEW CLUB", NEW_RIVAL: "ANOTHER NEW CLUB", "11": "X", "22": "Y"})) == 0


def test_a_club_that_two_teams_of_last_season_share_is_ambiguous(last_season):
    linker = ClubLinker(carry_for(Handler(last_season), SEGUNDA), club_source({"11": "SAME CLUB", "22": "SAME CLUB", NEW_OWN: "SAME CLUB"}))
    assert linker.code_of(NEW_OWN) is None


def test_the_old_teams_pages_are_only_asked_when_a_team_has_not_played(last_season):
    asked = []
    linker = ClubLinker(carry_for(Handler(last_season), SEGUNDA), club_source(asked=asked))
    assert asked == []
    assert linker.code_of(NEW_OWN) == CODE_OWN
    assert sorted(set(asked)) == ["11", "22", NEW_OWN]
    linker.code_of(NEW_RIVAL)
    assert asked.count("11") == 1      # the previous season is read once


def test_a_team_already_known_is_not_reseeded_by_its_club(last_season):
    acc = SeasonAccumulator(carry={CODE_OWN: 5.0})
    acc.ratings.update(NEW_OWN, NEW_RIVAL, 3)
    before = acc.ratings.rating(NEW_OWN)
    acc.link_clubs([NEW_OWN, NEW_RIVAL], ClubLinker(carry_for(Handler(last_season), SEGUNDA), club_source()))
    assert acc.ratings.rating(NEW_OWN) == before
