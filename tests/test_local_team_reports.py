"""Team reports precomputed and sealed by scope (#638, class B of the local-first spike #327): the first user's pages without a server.

One file per team and mode (own analysis, rival scouting), computed with the report service of the API, sealed once with a random key and
wrapped for the scopes that may read it (``package_scopes``): the own report of a team for its club, the rival report for the clubs of the
competition, everything for ``competicion:<collection>``, and ``abierto`` while the beta is open. Access is the wraps, never a re-encryption.
"""
import json
import sys
from pathlib import Path

import mongomock
import pymongo
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent / "local_vectors"))

import fbcyl_games  # noqa: E402
import games  # noqa: E402
from src.live_prep.package_scopes import open_sealed, scope_key  # noqa: E402
from src.live_prep.package_sealing import ScopedSealer  # noqa: E402
from src.local_data.team_reports import _dump, build_reports, publish_reports, report_scopes  # noqa: E402

FEB = "L_F_-2_2025_2026_Liga_Regular_B"
FBCYL = "FBCYL_1ª_FASE-GRUPO_A-1_2026_"
MASTER = "a-master-secret-for-the-tests"


@pytest.fixture()
def handler(monkeypatch):
    from src.api import deps

    monkeypatch.setattr(pymongo, "MongoClient", mongomock.MongoClient)
    deps._create_handler.cache_clear()
    handler = deps._create_handler()
    db = handler.connection.client["BASKETBALL"]
    db[FEB].insert_many(games.build_games())
    db[FBCYL].insert_many(fbcyl_games.build_games())
    yield handler
    deps._create_handler.cache_clear()


def _keys(*scopes):
    return {s: scope_key(MASTER, s) for s in scopes}


def _open(out: Path, entry: dict, *scopes) -> dict:
    envelope = json.loads((out / entry["file"]).read_text(encoding="utf-8"))
    return json.loads(open_sealed(envelope, entry["wraps"], _keys(*scopes)))


def test_every_team_gets_its_own_and_its_rival_report_and_the_season_is_read_once(handler, monkeypatch):
    from src.services.team_stats_service import TeamStatsService

    loads = []
    original = TeamStatsService.load_season_data
    monkeypatch.setattr(TeamStatsService, "load_season_data", lambda self, *a, **k: (loads.append(a), original(self, *a, **k))[1])
    built = list(build_reports(handler, FEB))
    assert sorted((tid, mode) for tid, _name, mode, _r in built) == sorted((t, m) for t in ("101", "102", "103", "104") for m in ("own", "rival"))
    assert all(r["mode"] == mode and r["team"] == name for _tid, name, mode, r in built)
    assert len(loads) == 1                                                 # 8 reports, one pass over the season


def test_who_may_read_what():
    ids = ["101", "102", "103"]
    assert report_scopes("own", "101", ids, FEB) == ["club:101", f"competicion:{FEB}"]
    rival = report_scopes("rival", "102", ids, FEB)
    assert rival[0] == f"competicion:{FEB}" and {f"club:{t}" for t in ids} <= set(rival)


def test_a_club_key_opens_its_own_report_and_every_rival_report_but_not_another_clubs_own(handler, tmp_path):
    index = publish_reports(handler, [FEB], tmp_path, ScopedSealer(MASTER, open_access=False))
    by = {(e["team_id"], e["mode"]): e for e in index["reports"]}
    assert _open(tmp_path, by[("101", "own")], "club:101")["team"] == "ALPHA"
    assert _open(tmp_path, by[("102", "rival")], "club:101")["mode"] == "rival"
    with pytest.raises(Exception):
        _open(tmp_path, by[("102", "own")], "club:101")                    # the analysis of BRAVO is for BRAVO's staff
    assert _open(tmp_path, by[("102", "own")], f"competicion:{FEB}")["team"] == "BRAVO"
    assert "open_key" not in index


def test_while_the_beta_is_open_everybody_can_read_and_the_index_publishes_the_open_key(handler, tmp_path):
    index = publish_reports(handler, [FEB], tmp_path, ScopedSealer(MASTER, open_access=True))
    assert index["open_key"]
    assert _open(tmp_path, index["reports"][0], "abierto")["team"]


def test_the_index_describes_every_file_safely(handler, tmp_path):
    index = publish_reports(handler, [FEB], tmp_path, ScopedSealer(MASTER))
    assert index["v"] == 2 and len(index["reports"]) == 8
    for entry in index["reports"]:
        assert entry["file"].isascii() and (tmp_path / entry["file"]).stat().st_size == entry["bytes"]
        assert {"collection", "team_id", "team", "mode", "sha256", "wraps"} <= set(entry)
    assert json.loads((tmp_path / "index.json").read_text(encoding="utf-8")) == index


def test_a_report_that_did_not_change_is_not_rewritten_regression(handler, tmp_path):
    """Sealing is random (a new key and iv each time): rewriting every file on every refresh would invalidate every cache for nothing."""
    sealer = ScopedSealer(MASTER)
    first = publish_reports(handler, [FEB], tmp_path, sealer)
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    second = publish_reports(handler, [FEB], tmp_path, sealer, previous=first)
    assert {p.name: p.read_bytes() for p in tmp_path.iterdir() if p.name != "index.json"} == {k: v for k, v in before.items() if k != "index.json"}
    assert [e["wraps"] for e in second["reports"]] == [e["wraps"] for e in first["reports"]]


def test_a_new_game_rewrites_the_reports_it_changes(handler, tmp_path):
    sealer = ScopedSealer(MASTER)
    first = publish_reports(handler, [FEB], tmp_path, sealer)
    handler.connection.client["BASKETBALL"][FEB].insert_one({**games.build_games()[0], "_id": 9999})
    second = publish_reports(handler, [FEB], tmp_path, sealer, previous=first)
    changed = [a["team_id"] for a, b in zip(first["reports"], second["reports"]) if a["sha256"] != b["sha256"]]
    assert "101" in changed


def test_fbcyl_competitions_get_their_reports_too(handler, tmp_path):
    index = publish_reports(handler, [FBCYL], tmp_path, ScopedSealer(MASTER, open_access=False))
    assert {(e["mode"]) for e in index["reports"]} == {"own", "rival"} and len(index["reports"]) == 8
    entry = next(e for e in index["reports"] if e["mode"] == "rival")
    assert _open(tmp_path, entry, f"competicion:{FBCYL}")["mode"] == "rival"


@pytest.mark.parametrize("name, build", [(FEB, games.build_games), (FBCYL, fbcyl_games.build_games)])
def test_reports_do_not_depend_on_the_order_the_games_were_stored_in_regression(handler, name, build):
    """The archive restores the games sorted by ``_id``: summing the same floats in another order differs in the 14th decimal, and a report that
    changed with it would be republished (and its cache invalidated) by every refresh."""
    db = handler.connection.client["BASKETBALL"]
    forward = {(t, m): _dump(r) for t, _n, m, r in build_reports(handler, name)}
    db[name].drop()
    db[name].insert_many(list(reversed(build())))
    backward = {(t, m): _dump(r) for t, _n, m, r in build_reports(handler, name)}
    assert forward == backward and forward
