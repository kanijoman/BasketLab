"""The rows of NCAA that are published keep only the Division I teams (#1061, decision of 23/11/2026 in #888): the game is stored COMPLETE, with the team that is not Division I and its box, and the
rows of that team (and of its players) stay out of what is published, as do the rest of its figures.

Real games: Buffalo (Division I, MAC) hosting RIT, which is not (401823428); and Washington State against Gonzaga, both Division I (401829197). A game of FIBA or ACB has no ``division1`` and keeps
every team.
"""
import copy

from db_helpers import new_mock_db
from ncaa_helpers import fixture

from src.external.ncaa_canonical import to_canonical
from src.external.ncaa_page import parse_summary
from src.local_data.export import export_collection

ENTRY = {"competition": "D1 Men", "season_value": "2025", "season_label": "2025/2026", "gender": "M"}
COLLECTION = "NCAA_D1_Men_2025_MAC"


def doc(name):
    return to_canonical(parse_summary(fixture(name)), ENTRY, {})


def payload(*names, db=None):
    db = db or new_mock_db("BASKETBALL")
    for name in names:
        db[COLLECTION].insert_one({**doc(name), "_reliable": True})
    return export_collection(db[COLLECTION], COLLECTION)


def players(game, team):
    return {f"ncaa:{p['id']}" for p in parse_summary(fixture(game))["players"][team] if p["stats"]}


def test_the_rows_of_a_team_that_is_not_division_i_are_not_published_and_its_host_keeps_its_own():
    out = payload("game_mens_nond1_401823428")
    assert {r["team_id"] for r in out["team_rows"]} == {"ncaa:2084"} and [r["team_name"] for r in out["team_rows"]] == ["Buffalo Bulls"]
    published = {r["player_id"] for r in out["player_rows"]}
    assert published and published <= players("game_mens_nond1_401823428", "2084") and not published & players("game_mens_nond1_401823428", "178")
    assert {r["is_local"] for r in out["player_rows"]} == {True}                  # Buffalo is the home team; RIT, the visitor, is not published


def test_a_game_between_two_division_i_teams_keeps_both():
    out = payload("game_mens_401829197")
    assert {r["team_id"] for r in out["team_rows"]} == {"ncaa:265", "ncaa:2250"} and {r["is_local"] for r in out["player_rows"]} == {True, False}
    assert {r["player_id"] for r in out["player_rows"]} == players("game_mens_401829197", "265") | players("game_mens_401829197", "2250")


def test_the_game_stays_complete_in_the_archive_only_the_published_rows_leave_it_out():
    db = new_mock_db("BASKETBALL")
    out = payload("game_mens_nond1_401823428", db=db)
    stored = db[COLLECTION].find_one({"_id": "ncaa:401823428"})
    assert len(stored["BOXSCORE"]["TEAM"]) == 2 and any(t["division1"] is False for t in stored["HEADER"]["TEAM"]) and out["games"] == 1


def test_a_source_that_says_nothing_of_the_division_keeps_every_team():
    """FIBA and ACB documents have no ``division1``: nothing of theirs is filtered."""
    db = new_mock_db("BASKETBALL")
    game = copy.deepcopy(doc("game_mens_nond1_401823428"))
    for team in game["HEADER"]["TEAM"]:
        team.pop("division1")
    for team in game["BOXSCORE"]["TEAM"]:
        team.pop("division1")
    db["FIBA_Test_2025_"].insert_one({**game, "_id": "fiba:1", "_league": "fiba"})
    out = export_collection(db["FIBA_Test_2025_"], "FIBA_Test_2025_")
    assert {r["team_id"] for r in out["team_rows"]} == {"ncaa:2084", "ncaa:178"}


def test_the_rows_are_the_same_whatever_the_order_the_games_were_stored_in():
    a = payload("game_mens_nond1_401823428", "game_mens_401829197")
    b = payload("game_mens_401829197", "game_mens_nond1_401823428")
    assert a == b and {r["team_id"] for r in a["team_rows"]} == {"ncaa:2084", "ncaa:265", "ncaa:2250"}
