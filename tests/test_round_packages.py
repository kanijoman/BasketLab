"""Packages for every match of the next round of a competition (issues #286, #172).

One pass over the games of a competition gives the packages of ALL the matches of its next round (the accumulator tracks every
team of the round); each match has the club's perspective when the club plays it and the home team's otherwise. The matches of a
competition travel in ONE bundle: a single envelope (one key derivation) around the compressed JSON of its packages. The index
lists the bundles of every competition with a summary of their matches, so the app lists them without downloading anything.
"""
import json
from unittest.mock import MagicMock

import pytest

from src.live_core.package import PreparationPackage
from src.live_prep.package_builder import build_package
from src.live_prep.package_crypto import decrypt_package
from src.live_prep.round_packages import (
    ROUND_BUNDLE_VERSION, build_round_packages, bundle_plaintext, publish_rounds, round_file_name,
)

PASSWORD = "clave-larga-de-prueba"
STAMP = "2026-10-14T00:00:00Z"


def _teams(game):
    return [(str(t["id"]), t["name"]) for t in game["HEADER"]["TEAM"]]


def _match(code, home, away, start="2026-10-17T17:00", rnd=4):
    return {"code": code, "start": start, "round": rnd, "home": {"id": home[0], "name": home[1]}, "away": {"id": away[0], "name": away[1]}}


@pytest.fixture
def teams(feb_game_doc):
    (a, an), (b, bn) = _teams(feb_game_doc)
    return {"a": (a, an), "b": (b, bn), "c": ("9001", "TERCERO"), "d": ("9002", "CUARTO")}


def _build(games, matches, club=None, **kw):
    return build_round_packages(games, "FEB_TEST", "2025-2026", matches, club_team_id=club, created_at=STAMP, **kw)


def test_every_match_has_a_package_from_each_of_its_two_teams(feb_game_doc, teams):
    """Any club can follow the match, not only the home team or the club of the staff (issue #286)."""
    matches = [_match("1", teams["a"], teams["b"]), _match("2", teams["c"], teams["d"])]
    built = _build([feb_game_doc], matches)
    assert [(b["match"]["code"], b["own_id"], b["rival_id"]) for b in built] == [
        ("1", teams["a"][0], teams["b"][0]), ("1", teams["b"][0], teams["a"][0]),
        ("2", teams["c"][0], teams["d"][0]), ("2", teams["d"][0], teams["c"][0])]
    assert all(isinstance(b["package"], PreparationPackage) for b in built)
    assert all(b["package"].team["id"] == b["own_id"] and b["package"].rival["id"] == b["rival_id"] for b in built)


def test_the_default_perspective_comes_first_the_clubs_when_it_plays_and_the_home_teams_otherwise(feb_game_doc, teams):
    matches = [_match("1", teams["a"], teams["b"]), _match("2", teams["c"], teams["d"])]
    club_away = _build([feb_game_doc], matches, club=teams["b"][0])
    assert [(b["own_id"], b["default"]) for b in club_away] == [
        (teams["b"][0], True), (teams["a"][0], False), (teams["c"][0], True), (teams["d"][0], False)]
    assert [b["is_club"] for b in club_away] == [True, True, False, False]      # the match is the club's, whichever side is followed


def test_both_packages_are_what_the_one_off_builder_gives_for_that_side(feb_game_doc, teams):
    """One shared pass must not change the numbers of a package."""
    matches = [_match("1", teams["a"], teams["b"]), _match("2", teams["c"], teams["d"])]
    built = _build([feb_game_doc], matches)
    for entry, (own, rival) in zip(built[:2], ((teams["a"][0], teams["b"][0]), (teams["b"][0], teams["a"][0]))):
        single = build_package([feb_game_doc], "FEB_TEST", "2025-2026", own, rival, entry["package"].competition_meta, STAMP)
        assert entry["package"].dumps() == single.dumps()
    assert built[0]["package"].competition_meta["match"]["code"] == "1"


def test_the_rosters_are_asked_once_per_team_and_a_failure_leaves_the_package_without_roster(feb_game_doc, teams):
    asked = []

    def source(ids):
        asked.append(tuple(ids))
        if teams["c"][0] in ids:
            raise ConnectionError("FEB down")
        return {"p1": {"team_id": teams["a"][0], "name": "X", "formacion": True}} if teams["a"][0] in ids else None

    matches = [_match("1", teams["a"], teams["b"]), _match("2", teams["a"], teams["c"]), _match("3", teams["c"], teams["d"])]
    built = _build([feb_game_doc], matches, roster_source=source)
    flat = [t for ids in asked for t in ids]
    assert flat.count(teams["a"][0]) == 1, "each team is asked once, however many matches it has"
    assert "roster" in built[0]["package"].tables and "roster" in built[1]["package"].tables
    assert "roster" not in built[4]["package"].tables                            # c against d: c fails and d has none


# --- the bundle ------------------------------------------------------------------------------

def test_the_bundle_holds_every_package_in_one_compressed_envelope(feb_game_doc, teams, tmp_path):
    matches = [_match("1", teams["a"], teams["b"]), _match("2", teams["c"], teams["d"])]
    built = _build([feb_game_doc], matches, club=teams["a"][0])
    entry = publish_rounds(tmp_path, PASSWORD, "FEB_TEST", 4, built, club_team_id=teams["a"][0])
    raw = (tmp_path / entry["file"]).read_text(encoding="utf-8")
    envelope = json.loads(raw)
    assert envelope["z"] == "gzip"
    bundle = json.loads(decrypt_package(envelope, PASSWORD))
    assert bundle["v"] == ROUND_BUNDLE_VERSION and bundle["collection"] == "FEB_TEST" and bundle["round"] == 4
    assert [(m["match"]["code"], m["own_id"]) for m in bundle["matches"]] == [
        ("1", teams["a"][0]), ("1", teams["b"][0]), ("2", teams["c"][0]), ("2", teams["d"][0])]
    assert PreparationPackage.loads(bundle["matches"][2]["package"]).team["id"] == teams["c"][0]
    assert len(raw.encode("utf-8")) < sum(len(m["package"]) for m in bundle["matches"]), "compressed before encrypting"


def test_the_index_entry_summarises_the_matches_without_the_packages(feb_game_doc, teams, tmp_path):
    matches = [_match("1", teams["a"], teams["b"]), _match("2", teams["c"], teams["d"])]
    built = _build([feb_game_doc], matches, club=teams["a"][0])
    entry = publish_rounds(tmp_path, PASSWORD, "FEB_TEST", 4, built, club_team_id=teams["a"][0])
    assert entry["collection"] == "FEB_TEST" and entry["round"] == 4 and entry["club"] is True
    assert entry["file"] == round_file_name("FEB_TEST", 4) and len(entry["sha256"]) == 64 and entry["bytes"] > 0
    assert [(m["code"], m["own_id"], m["is_club"]) for m in entry["matches"]] == [
        ("1", teams["a"][0], True), ("2", teams["c"][0], False)]              # one line per match: its default side
    assert [m["own_ids"] for m in entry["matches"]] == [[teams["a"][0], teams["b"][0]], [teams["c"][0], teams["d"][0]]]
    assert entry["matches"][0]["home"]["name"] == teams["a"][1] and "package" not in entry["matches"][0]


def test_a_round_without_the_club_is_not_marked_as_the_clubs(feb_game_doc, teams, tmp_path):
    built = _build([feb_game_doc], [_match("2", teams["c"], teams["d"])], club="1008631")
    assert publish_rounds(tmp_path, PASSWORD, "FEB_TEST", 4, built, club_team_id="1008631")["club"] is False


def test_the_file_name_is_safe_for_any_collection():
    assert round_file_name("LF2 / A B", 3) == "rounds/LF2_A_B__r3.bpkgz"


def test_the_bundle_plaintext_is_deterministic(feb_game_doc, teams):
    built = _build([feb_game_doc], [_match("1", teams["a"], teams["b"])])
    assert bundle_plaintext("FEB_TEST", 4, built) == bundle_plaintext("FEB_TEST", 4, built)
