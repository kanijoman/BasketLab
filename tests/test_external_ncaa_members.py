"""The teams of a conference are the ones that are LISTED in it (#1103): a conference competition of NCAA holds every game whose home team belongs to it, so the teams of other conferences that came to
play there appear with one or two games (visitors, none at home). The publication says which teams are the conference's (``members`` of the rows entry of the manifest) so that the web lists only those;
the rows of the others stay, and their games still count for the teams that played them.

Real games (Washington State and Gonzaga, 401829197; Buffalo and RIT, 401823428) with the conference of a team changed to make it an outsider: the document keeps the shape ESPN's game has.
"""
import copy

from db_helpers import new_mock_db
from ncaa_helpers import fixture

from src.external.ncaa_canonical import to_canonical
from src.external.ncaa_page import parse_summary
from src.external.publish import conference_members

ENTRY = {"competition": "D1 Men", "season_value": "2025", "season_label": "2025/2026", "gender": "M"}


def doc(name, **conferences):
    game = to_canonical(parse_summary(fixture(name)), ENTRY, {})
    out = copy.deepcopy(game)
    for team in out["HEADER"]["TEAM"] + out["BOXSCORE"]["TEAM"]:
        if team["id"] in conferences:
            team["conference_id"] = conferences[team["id"]]
    return {**out, "_reliable": True}


def collection(*docs):
    db = new_mock_db("BASKETBALL")
    for d in docs:
        db["NCAA_D1_Men_2025_WCC"].insert_one(d)
    return db["NCAA_D1_Men_2025_WCC"]


def test_the_members_are_the_teams_that_played_in_the_conference_not_the_ones_that_visited():
    games = collection(doc("game_mens_401829197", **{"ncaa:2250": "3"}))              # Gonzaga shown as a team of another conference
    assert conference_members(games, "29") == ["ncaa:265"]


def test_every_team_of_the_conference_counts_whether_it_hosted_or_visited():
    assert conference_members(collection(doc("game_mens_401829197")), "29") == ["ncaa:2250", "ncaa:265"]


def test_a_team_that_is_not_division_i_has_no_conference_and_is_never_a_member():
    games = collection(doc("game_mens_nond1_401823428"))
    assert conference_members(games, "14") == ["ncaa:2084"]


def test_the_members_come_from_all_the_games_of_the_competition():
    games = collection(doc("game_mens_401829197", **{"ncaa:2250": "3"}), doc("game_mens_nond1_401823428", **{"ncaa:2084": "29"}))
    assert conference_members(games, "29") == ["ncaa:2084", "ncaa:265"]
