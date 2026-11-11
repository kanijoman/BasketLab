"""Issue #854: the games of a package are replayed in the order they were played, not in the order of their ``_id``.

The Kalman rating (``TeamRatings``) depends on the order of its updates, so a competition whose ``_id`` order differs from the calendar gave the app another rating than the web
(which orders by date). Ties on the date keep a deterministic order (the ``_id``); a game whose date cannot be read goes last.
"""
import copy

import pytest

from src.live_prep.game_sources import games_of_sources, source_collections
from src.live_prep.package_builder import SeasonAccumulator
from test_live_prep_game_sources import OWN, RIVAL, SEGUNDA, Handler, game

STARTS = {1: "20-12-2025 - 12:00", 2: "05-10-2025 - 12:30", 3: "01-11-2025 - 18:00", 4: "05-10-2025 - 12:30"}


@pytest.fixture
def played_out_of_order(feb_game_doc):
    docs = []
    for code, start in STARTS.items():
        doc = game(feb_game_doc, OWN, RIVAL, code)
        doc["HEADER"]["starttime"] = start
        docs.append(doc)
    docs.append({**game(feb_game_doc, OWN, RIVAL, 5), "HEADER": {**feb_game_doc["HEADER"], "starttime": None, "TEAM": feb_game_doc["HEADER"]["TEAM"]}})
    return {SEGUNDA: docs}


def order_of(world):
    handler = Handler(world)
    sources = source_collections(handler, SEGUNDA, [OWN, RIVAL])
    return [g["_id"] for g in games_of_sources(handler, sources, [OWN, RIVAL])]


def test_games_come_in_the_order_they_were_played_with_the_id_as_tiebreak_and_unreadable_dates_last(played_out_of_order):
    assert order_of(played_out_of_order) == [2, 4, 3, 1, 5]


def test_the_order_does_not_depend_on_how_the_documents_are_stored(played_out_of_order):
    reversed_world = {SEGUNDA: list(reversed(played_out_of_order[SEGUNDA]))}
    assert order_of(reversed_world) == order_of(played_out_of_order)


def test_the_rating_of_the_package_is_the_one_of_the_calendar_order(feb_game_doc):
    """A beats B by the sample margin early and loses the rematch later: the order changes the final rating."""
    first, second = copy.deepcopy(feb_game_doc), copy.deepcopy(feb_game_doc)
    second["HEADER"]["TEAM"] = list(reversed(second["HEADER"]["TEAM"]))     # the rematch at the other court: the same teams, home swapped
    first["HEADER"]["starttime"], second["HEADER"]["starttime"] = "05-10-2025 - 12:30", "05-01-2026 - 12:30"
    first["_id"], second["_id"] = 9, 1                                       # the later game has the smaller id
    handler = Handler({SEGUNDA: [second, first]})
    sources = source_collections(handler, SEGUNDA, [OWN, RIVAL])
    acc = SeasonAccumulator()
    for g in games_of_sources(handler, sources, [OWN, RIVAL]):
        acc.add_game(g)
    expected = SeasonAccumulator()
    for g in (first, second):
        expected.add_game(g)
    assert acc.ratings.rating(OWN) == pytest.approx(expected.ratings.rating(OWN))
