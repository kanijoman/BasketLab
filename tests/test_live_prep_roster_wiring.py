"""The FEB roster travels in the package (issue #271): builder, database source, publisher and the live engine.

``tables.roster`` = ``{player id: {team_id, name, formacion, birth, nationality, position, dorsal, height}}`` for the own
team and the rival. It is separate from ``tables.players`` (baselines of players with minutes) so that a signing with no
previous game still has its mark. Without a roster the package is exactly what it was before.
"""
from unittest.mock import MagicMock

import pytest

from src.live_core.advice import AdviceEngine
from src.live_core.package import PreparationPackage
from src.live_prep.package_builder import SeasonAccumulator, build_package

OWN, RIVAL = "982047", "981204"
STAMP = "2026-10-14T00:00:00Z"
ROSTER = {
    "2817524": {"team_id": OWN, "name": "E. PRUEBA", "formacion": True, "birth": "2004-02-01", "nationality": "ESPAÑA",
                "position": "Base", "dorsal": 2, "height": 175},
    "2073736": {"team_id": RIVAL, "name": "A. PRUEBA", "formacion": False, "birth": None, "nationality": None,
                "position": None, "dorsal": None, "height": None},
}


def _build(games, **kw):
    return build_package(games, collection="FEB_TEST", season="2025-2026", team_id=OWN, rival_id=RIVAL,
                         created_at=STAMP, **kw)


# --- builder ------------------------------------------------------------------------------

def test_the_roster_goes_into_the_tables_and_survives_the_envelope(feb_game_doc):
    package = _build([feb_game_doc], roster=ROSTER)
    assert package.tables["roster"] == ROSTER
    assert PreparationPackage.loads(package.dumps()).tables["roster"] == ROSTER


def test_without_a_roster_the_package_is_exactly_what_it_was(feb_game_doc):
    plain, with_none = _build([feb_game_doc]), _build([feb_game_doc], roster=None)
    assert "roster" not in plain.tables and plain.dumps() == with_none.dumps()
    assert _build([feb_game_doc], roster={}).dumps() == plain.dumps(), "an empty roster says nothing: same as none"
    assert _build([feb_game_doc], roster=ROSTER).checksum() != plain.checksum()


def test_the_accumulator_takes_the_roster_when_the_package_is_asked_for(feb_game_doc):
    acc = SeasonAccumulator()
    acc.add_game(feb_game_doc)
    package = acc.to_package("FEB_TEST", "2025-2026", OWN, RIVAL, None, STAMP, roster=ROSTER)
    assert package.tables["roster"] == ROSTER
    assert "roster" not in acc.to_package("FEB_TEST", "2025-2026", OWN, RIVAL, None, STAMP).tables


def test_the_roster_is_a_copy_so_later_changes_do_not_reach_the_package(feb_game_doc):
    roster = {k: dict(v) for k, v in ROSTER.items()}
    package = _build([feb_game_doc], roster=roster)
    roster["2817524"]["formacion"] = False
    assert package.tables["roster"]["2817524"]["formacion"] is True


# --- database source ----------------------------------------------------------------------

def _handler(feb_game_doc):
    handler = MagicMock()
    handler.repository.connection.get_collection.return_value.find.return_value = iter([feb_game_doc])
    return handler


def test_db_source_asks_for_the_rosters_of_both_teams_and_puts_them_in_the_package(feb_game_doc):
    from src.live_prep.db_source import build_package_from_db

    asked = []
    package = build_package_from_db(_handler(feb_game_doc), "FEB_TEST", OWN, RIVAL, "2025-2026",
                                    roster_source=lambda ids: asked.append(list(ids)) or ROSTER)
    assert asked == [[OWN, RIVAL]] and package.tables["roster"] == ROSTER


@pytest.mark.parametrize("source", [lambda ids: None, lambda ids: {}, MagicMock(side_effect=RuntimeError("FEB down"))])
def test_a_roster_that_is_missing_or_fails_does_not_stop_the_package(feb_game_doc, source):
    from src.live_prep.db_source import build_package_from_db

    package = build_package_from_db(_handler(feb_game_doc), "FEB_TEST", OWN, RIVAL, "2025-2026", roster_source=source)
    assert "roster" not in package.tables and package.tables["players"]


def test_db_source_makes_no_request_unless_it_is_given_a_roster_source(feb_game_doc, monkeypatch):
    from src.live_prep import db_source, roster_fetcher

    monkeypatch.setattr(roster_fetcher, "fetch_rosters", MagicMock(side_effect=AssertionError("network used")))
    assert "roster" not in db_source.build_package_from_db(_handler(feb_game_doc), "FEB_TEST", OWN, RIVAL, "2025").tables


# --- publisher ---------------------------------------------------------------------------

def test_the_scheduled_publication_builds_its_packages_with_the_roster_source(tmp_path, monkeypatch):
    from src.live_prep import db_source, publisher, roster_fetcher

    seen = {}

    def fake_build(db, collection, team_id, rival_id, **kw):
        seen.update(kw)
        package = MagicMock()
        package.dumps.return_value = "{}"
        return package

    monkeypatch.setattr(db_source, "build_package_from_db", fake_build)
    own, rival = {"id": "1", "name": "A"}, {"id": "2", "name": "B"}
    service = MagicMock()
    service.upcoming.return_value = {"matches": [{"code": "9", "start": "2026-10-17T20:30", "round": 3, "home": own,
                                                  "away": rival, "opponent": rival, "status": "scheduled", "is_home": True}]}
    publisher.publish_all(object(), tmp_path, "clave-larga-de-prueba", ["COL"], "1", service=service)
    assert seen["roster_source"] is roster_fetcher.fetch_rosters


# --- the live engine ---------------------------------------------------------------------

def _package(roster):
    tables = {"players": {}}
    if roster is not None:
        tables["roster"] = roster
    return PreparationPackage(collection="c", season="s", team={"id": OWN, "name": "A"}, rival={"id": RIVAL, "name": "B"},
                              tables=tables, created_at=STAMP)


def test_the_engine_knows_the_roster_of_the_package():
    engine = AdviceEngine.from_package(PreparationPackage.loads(_package(ROSTER).dumps()))
    assert engine._ctx.roster == ROSTER


def test_a_package_without_roster_gives_the_engine_an_empty_one():
    assert AdviceEngine.from_package(_package(None))._ctx.roster == {}
    assert AdviceEngine(own_team_id=OWN)._ctx.roster == {}
