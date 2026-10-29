"""Where the scouting gets the games of a team besides its league, and the category of every team (#638).

The cups of the season are found by the name of the collection and the season in it; the games of the team in them by the team id; the category of a
team is the ``level`` of its league in the catalog of the publisher. A scouting of a cup collection has no other cup to add.
"""
from types import SimpleNamespace

import pytest
from db_helpers import new_mock_db

from src.live_prep.scouting_scopes import cup_collections, cup_games, is_cup, season_of, team_levels

LEAGUE = "PRIMERA_FEB_2026_2027_Liga_Regular_\u00danico"
SEGUNDA = "SEGUNDA_FEB_2026_2027_Liga_Regular_A"
CUP_GROUP = "COPA_ESPA\u00d1A_2026_2027_FASE_DE_GRUPOS_A"
CUP_PLAYOFF = "COPA_ESPA\u00d1A_2026_2027_Play-offs_1_16_Final"
CUP_LAST_YEAR = "COPA_ESPA\u00d1A_2025_2026_Play-offs_1_8_Final"
FBCYL_CUP = "FBCYL_COPA_2026_2027_A"


@pytest.mark.parametrize("name, cup, season", [
    (LEAGUE, False, "2026_2027"), (CUP_GROUP, True, "2026_2027"), ("COPA_DE_LA_REINA_2025_2026_Final", True, "2025_2026"),
    ("SUPERCOPA_2026_2027", True, "2026_2027"), ("NO_SEASON_HERE", False, None),
])
def test_cups_and_seasons_are_read_from_the_name(name, cup, season):
    assert (is_cup(name), season_of(name)) == (cup, season)


def test_the_cups_of_the_season_are_found_and_nothing_else():
    names = [LEAGUE, SEGUNDA, CUP_GROUP, CUP_PLAYOFF, CUP_LAST_YEAR]
    assert cup_collections(names, LEAGUE) == [CUP_GROUP, CUP_PLAYOFF]
    assert cup_collections(names, CUP_LAST_YEAR) == []                         # a cup collection is not asked for other cups by this function's caller
    assert cup_collections(names, "NO_SEASON_HERE") == []


def _handler(collections, meta=None):
    db = new_mock_db("scopes")
    for name, docs in collections.items():
        if docs:
            db[name].insert_many(docs)
        else:
            db.create_collection(name)
    for name, label in (meta or {}).items():
        db["COLLECTION_META"].insert_one({"_id": name, "competition_label": label, "group_label": ""})
    return SimpleNamespace(connection=SimpleNamespace(client={"BASKETBALL": db}), repository=SimpleNamespace(connection=SimpleNamespace(get_collection=lambda n: db[n])))


def _game(code, *teams):
    return {"_id": code, "HEADER": {"TEAM": [{"id": t} for t in teams]}}


def _reader(handler, collection, team_id=None):
    return [g for g in handler.connection.client["BASKETBALL"][collection].find({}) if team_id is None or any(t["id"] == team_id for t in g["HEADER"]["TEAM"])]


def test_the_cup_games_of_the_team_come_from_every_cup_of_the_season_by_team_id():
    handler = _handler({LEAGUE: [_game(1, "10", "11")], CUP_GROUP: [_game(2, "10", "90"), _game(3, "91", "92")], CUP_PLAYOFF: [_game(4, "93", "10")],
                        CUP_LAST_YEAR: [_game(5, "10", "94")], FBCYL_CUP: [_game(6, "10", "95")]})
    games = cup_games(handler, LEAGUE, "10", reader=_reader)
    assert sorted(g["_id"] for g in games["copa"]) == [2, 4]                   # not the league, not another team's, not last year's, not FBCYL's


def test_a_team_without_cup_games_has_no_cup_scope():
    handler = _handler({LEAGUE: [_game(1, "10", "11")], CUP_GROUP: [_game(2, "90", "91")]})
    assert cup_games(handler, LEAGUE, "10", reader=_reader) == {}


def test_scouting_a_cup_collection_adds_no_other_cup():
    handler = _handler({CUP_GROUP: [_game(2, "10", "90")], CUP_PLAYOFF: [_game(4, "10", "93")]})
    assert cup_games(handler, CUP_GROUP, "10", reader=_reader) == {}


CATALOG = [{"competition": "PRIMERA FEB", "level": 2, "gender": "M"}, {"competition": "SEGUNDA FEB", "level": 3, "gender": "M"}]


def test_the_category_of_a_team_is_the_level_of_its_league():
    handler = _handler({LEAGUE: [_game(1, "10", "11")], SEGUNDA: [_game(2, "20", "21")], CUP_GROUP: [_game(3, "10", "20")]},
                       meta={LEAGUE: "PRIMERA FEB", SEGUNDA: "SEGUNDA FEB", CUP_GROUP: "COPA ESPAÑA"})
    assert team_levels(handler, LEAGUE, CATALOG) == {"10": 2, "11": 2, "20": 3, "21": 3}      # the cup gives nobody a category


def test_a_team_in_two_leagues_keeps_the_highest_category():
    handler = _handler({LEAGUE: [_game(1, "10", "11")], SEGUNDA: [_game(2, "10", "21")]}, meta={LEAGUE: "PRIMERA FEB", SEGUNDA: "SEGUNDA FEB"})
    assert team_levels(handler, LEAGUE, CATALOG)["10"] == 2


def test_competitions_outside_the_catalog_and_unreadable_seasons_give_no_levels():
    handler = _handler({LEAGUE: [_game(1, "10", "11")]}, meta={LEAGUE: "LIGA QUE NO ESTA"})
    assert team_levels(handler, LEAGUE, CATALOG) == {}
    assert team_levels(handler, "NO_SEASON_HERE", CATALOG) == {}
