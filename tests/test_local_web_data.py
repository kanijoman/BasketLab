"""The web-data branch (#328, #640): what the refresh publishes for the web, sealed by scope, with a manifest and files that never change in place.

The artifacts are served by a CDN with a cache of minutes and read by clients that may hold an older manifest: a file name that stays while its
bytes change would mix versions, so a name carries the hash of its content and an unchanged file is kept byte for byte (sealing is random).
Nothing readable is published: rows and reports are sealed, and access is the wraps of the index.
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
from src.local_data.export import export_collection  # noqa: E402
from src.local_data.web_data import SCHEMA, SECTIONS, publish_web_data  # noqa: E402

FEB = "L_F_-2_2025_2026_Liga_Regular_B"
FBCYL = "FBCYL_1ª_FASE-GRUPO_A-1_2026_"
MASTER = "a-master-secret-for-the-tests"


def _fast_lineups(handler, name):
    """What the lineups of a competition cost (four sizes of every team over every game) is not what these tests are about: a payload as small as the real one is shaped."""
    from src.local_data.export import FORMAT
    from src.local_data.lineups_export import COLUMNS

    return {"format": FORMAT, "collection": name, "league": "fbcyl" if "FBCYL" in name else "feb", "columns": list(COLUMNS),
            "teams": [{"team_id": "1", "team_name": "A", "games": [], "players": {}, "sizes": {}}]}


@pytest.fixture(autouse=True)
def cheap_lineups(monkeypatch):
    monkeypatch.setattr("src.local_data.web_data.export_lineups", _fast_lineups)


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


def _tree(out: Path) -> dict:
    return {str(p.relative_to(out)).replace("\\", "/"): p.read_bytes() for p in sorted(out.rglob("*")) if p.is_file()}


def _manifest(out: Path) -> dict:
    return json.loads((out / "index.json").read_text(encoding="utf-8"))


def _open(out: Path, entry: dict, scope: str) -> dict:
    envelope = json.loads((out / entry["file"]).read_text(encoding="utf-8"))
    return json.loads(open_sealed(envelope, entry["wraps"], {scope: scope_key(MASTER, scope)}))


def test_the_manifest_lists_the_rows_and_the_reports_of_every_competition(handler, tmp_path):
    publish_web_data(handler, tmp_path, ScopedSealer(MASTER), [FEB, FBCYL])
    manifest = _manifest(tmp_path)
    assert manifest["schema"] == SCHEMA and manifest["v"] == 2 and manifest["open_key"]
    assert sorted(r["collection"] for r in manifest["rows"]) == sorted([FEB, FBCYL])
    assert sorted(r["collection"] for r in manifest["reports"]) == sorted([FEB, FBCYL])
    assert {r["league"] for r in manifest["rows"]} == {"feb", "fbcyl"}
    assert all(set(e) >= {"file", "bytes", "sha256"} for e in manifest["rows"] + manifest["reports"])


def test_the_rows_are_the_export_of_the_competition_sealed_for_its_scope(handler, tmp_path):
    publish_web_data(handler, tmp_path, ScopedSealer(MASTER, open_access=False), [FEB])
    entry = _manifest(tmp_path)["rows"][0]
    db = handler.connection.client["BASKETBALL"]
    assert _open(tmp_path, entry, f"competicion:{FEB}") == json.loads(json.dumps(export_collection(db[FEB], FEB), default=str))
    with pytest.raises(Exception):
        _open(tmp_path, entry, "club:101")                                # a club key does not open the rows of the whole competition


def test_while_the_beta_is_open_the_open_key_opens_the_rows_and_closing_it_removes_it(handler, tmp_path):
    publish_web_data(handler, tmp_path / "open", ScopedSealer(MASTER, open_access=True), [FEB])
    assert _open(tmp_path / "open", _manifest(tmp_path / "open")["rows"][0], "abierto")["collection"] == FEB
    publish_web_data(handler, tmp_path / "closed", ScopedSealer(MASTER, open_access=False), [FEB])
    manifest = _manifest(tmp_path / "closed")
    assert "open_key" not in manifest
    assert all(w["scope"] != "abierto" for e in manifest["rows"] for w in e["wraps"])


def test_the_reports_of_a_competition_have_their_own_index_so_a_page_loads_only_its_own(handler, tmp_path):
    publish_web_data(handler, tmp_path, ScopedSealer(MASTER, open_access=False), [FEB])
    entry = _manifest(tmp_path)["reports"][0]
    index = json.loads((tmp_path / entry["file"]).read_text(encoding="utf-8"))
    assert len(index["reports"]) == 8 and {e["mode"] for e in index["reports"]} == {"own", "rival"}
    own = next(e for e in index["reports"] if e["mode"] == "own" and e["team_id"] == "101")
    assert _open(tmp_path, own, "club:101")["team"] == "ALPHA"


def test_every_file_name_carries_the_hash_of_its_content(handler, tmp_path):
    publish_web_data(handler, tmp_path, ScopedSealer(MASTER), [FEB])
    manifest = _manifest(tmp_path)
    for entry in manifest["rows"] + manifest["reports"]:
        assert entry["sha256"][:12] in entry["file"] and entry["file"].isascii() and entry["file"].startswith(("rows/", "reports/"))
        assert (tmp_path / entry["file"]).stat().st_size == entry["bytes"]


def test_a_refresh_without_news_changes_no_byte_regression(handler, tmp_path):
    """Sealing is random: without the previous publication every file would be new (and every cache invalid) on each of the 3 refreshes a day."""
    sealer = ScopedSealer(MASTER)
    publish_web_data(handler, tmp_path, sealer, [FEB, FBCYL])
    before = _tree(tmp_path)
    publish_web_data(handler, tmp_path, sealer, [FEB, FBCYL])
    assert _tree(tmp_path) == before


def test_a_new_game_never_changes_a_file_in_place_and_leaves_no_orphans(handler, tmp_path):
    sealer = ScopedSealer(MASTER)
    publish_web_data(handler, tmp_path, sealer, [FEB, FBCYL])
    before = _tree(tmp_path)
    handler.connection.client["BASKETBALL"][FEB].insert_one({**games.build_games()[0], "_id": 9999})
    publish_web_data(handler, tmp_path, sealer, [FEB, FBCYL])
    after = _tree(tmp_path)
    assert all(after[name] == data for name, data in before.items() if name in after and name != "index.json")   # same name, same bytes
    assert before.keys() - after.keys() and after.keys() - before.keys()                                         # what changed got a new name
    manifest = _manifest(tmp_path)
    reports = [e["file"] for r in manifest["reports"] for e in json.loads(after[r["file"]])["reports"]]
    referenced = {e["file"] for e in manifest["rows"] + [x for section in SECTIONS for x in manifest.get(section, [])] + manifest["reports"]} | set(reports) | {"index.json", "frontend/vercel.json"}
    assert set(after) == referenced
    untouched = [n for n in after if "FBCYL" in n and n in before]
    assert untouched                                                                                             # the other competition kept its files


def test_a_subset_republishes_only_those_competitions_and_keeps_the_rest(handler, tmp_path):
    sealer = ScopedSealer(MASTER)
    publish_web_data(handler, tmp_path, sealer, [FEB, FBCYL])
    publish_web_data(handler, tmp_path, sealer, [FEB], keep_others=True)
    assert sorted(r["collection"] for r in _manifest(tmp_path)["rows"]) == sorted([FEB, FBCYL])


def test_the_branch_carries_the_vercel_guard(handler, tmp_path):
    publish_web_data(handler, tmp_path, ScopedSealer(MASTER), [FEB])
    guard = json.loads((tmp_path / "frontend" / "vercel.json").read_text(encoding="utf-8"))
    assert guard == {"git": {"deploymentEnabled": False}}


def test_no_competition_publishes_an_empty_but_valid_manifest(handler, tmp_path):
    publish_web_data(handler, tmp_path, ScopedSealer(MASTER), [])
    manifest = _manifest(tmp_path)
    assert manifest["rows"] == [] and manifest["reports"] == []


def test_the_entry_point_publishes_with_the_secret_of_the_environment_and_refuses_without_it(handler, tmp_path, monkeypatch):
    import run_web_data

    monkeypatch.delenv("PACKAGE_MASTER_KEY", raising=False)
    monkeypatch.delenv("PACKAGE_PASSWORD", raising=False)
    assert run_web_data.main(["--out", str(tmp_path / "none")]) == 2
    monkeypatch.setenv("PACKAGE_MASTER_KEY", MASTER)
    assert run_web_data.main(["--out", str(tmp_path / "all"), "--collection", FEB]) == 0
    assert [r["collection"] for r in _manifest(tmp_path / "all")["rows"]] == [FEB]


# Issue #676 (P4, block B): the ``DERIVED`` of each game, sealed by competition like the rows, in a file of its own (the team tables do not pay for it).
def test_the_manifest_lists_the_derived_of_every_competition_that_has_it(handler, tmp_path):
    publish_web_data(handler, tmp_path, ScopedSealer(MASTER), [FEB, FBCYL])
    manifest = _manifest(tmp_path)
    assert sorted(d["collection"] for d in manifest["derived"]) == sorted([FEB, FBCYL])
    assert all(set(e) >= {"file", "bytes", "sha256", "wraps", "games", "league"} and e["file"].startswith("derived/") for e in manifest["derived"])
    assert all(e["sha256"][:12] in e["file"] for e in manifest["derived"])


def test_the_derived_are_the_export_of_the_competition_sealed_for_its_scope(handler, tmp_path):
    from src.local_data.export import export_derived

    publish_web_data(handler, tmp_path, ScopedSealer(MASTER, open_access=False), [FEB])
    entry = _manifest(tmp_path)["derived"][0]
    db = handler.connection.client["BASKETBALL"]
    assert _open(tmp_path, entry, f"competicion:{FEB}") == json.loads(json.dumps(export_derived(db[FEB], FEB), default=str))
    with pytest.raises(Exception):
        _open(tmp_path, entry, "club:101")


def test_a_competition_with_no_derived_has_no_entry_and_a_refresh_changes_no_byte(handler, tmp_path):
    db = handler.connection.client["BASKETBALL"]
    db["L_F_-2_2025_2026_Sin_Derived"].insert_many([{k: v for k, v in g.items() if k != "DERIVED"} for g in games.build_games()])
    sealer = ScopedSealer(MASTER)
    publish_web_data(handler, tmp_path, sealer, [FEB, "L_F_-2_2025_2026_Sin_Derived"])
    assert [d["collection"] for d in _manifest(tmp_path)["derived"]] == [FEB]
    before = _tree(tmp_path)
    publish_web_data(handler, tmp_path, sealer, [FEB, "L_F_-2_2025_2026_Sin_Derived"])
    assert _tree(tmp_path) == before


def test_the_derived_of_a_competition_that_left_the_publication_are_removed(handler, tmp_path):
    sealer = ScopedSealer(MASTER)
    publish_web_data(handler, tmp_path, sealer, [FEB, FBCYL])
    gone = next(d for d in _manifest(tmp_path)["derived"] if d["collection"] == FBCYL)["file"]
    publish_web_data(handler, tmp_path, sealer, [FEB])
    assert not (tmp_path / gone).exists()


# Issues #684 and #685: the shots and the rotations of each competition, sealed by competition like the rows, in files of their own.
def test_the_manifest_lists_the_shots_of_every_competition_that_has_them(handler, tmp_path):
    from src.local_data.export import FORMAT
    from src.local_data.shots_export import export_shots

    publish_web_data(handler, tmp_path, ScopedSealer(MASTER, open_access=False), [FEB, FBCYL])
    manifest = _manifest(tmp_path)
    assert sorted(s["collection"] for s in manifest["shots"]) == sorted([FEB, FBCYL])
    assert all(e["file"].startswith("shots/") and e["sha256"][:12] in e["file"] and set(e) >= {"file", "bytes", "sha256", "wraps", "games", "league"} for e in manifest["shots"])
    entry = next(s for s in manifest["shots"] if s["collection"] == FEB)
    db = handler.connection.client["BASKETBALL"]
    assert _open(tmp_path, entry, f"competicion:{FEB}") == json.loads(json.dumps(export_shots(db[FEB], FEB), default=str))
    assert _open(tmp_path, entry, f"competicion:{FEB}")["format"] == FORMAT
    with pytest.raises(Exception):
        _open(tmp_path, entry, "club:101")


def test_the_rotations_are_published_for_a_competition_with_play_by_play_and_not_for_one_without(handler, tmp_path):
    from src.local_data.rotations_export import export_rotations

    publish_web_data(handler, tmp_path, ScopedSealer(MASTER, open_access=False), [FEB])
    entry = _manifest(tmp_path)["rotations"][0]
    assert entry["collection"] == FEB and entry["file"].startswith("rotations/") and entry["games"] == 4               # for rotations, ``games`` counts the teams
    assert _open(tmp_path, entry, f"competicion:{FEB}") == json.loads(json.dumps(export_rotations(handler, FEB), default=str))
    with pytest.raises(Exception):
        _open(tmp_path, entry, "club:101")
    db = handler.connection.client["BASKETBALL"]
    without = "L_F_-2_2025_2026_Sin_Pbp"
    db[without].insert_many([{k: v for k, v in g.items() if k != "PLAYBYPLAY"} for g in games.build_games()])
    publish_web_data(handler, tmp_path / "other", ScopedSealer(MASTER), [without])
    assert _manifest(tmp_path / "other").get("rotations", []) == []                 # nothing to analyse: no entry


def test_the_lineups_are_published_for_a_competition_with_play_by_play_and_not_for_one_without(handler, tmp_path, monkeypatch):
    """#686: the real exporter (the others of this file run a cheap one) over the games of the fixture, sealed for the competition; ``games`` counts the teams."""
    from src.local_data import lineups_export

    monkeypatch.setattr("src.local_data.web_data.export_lineups", lineups_export.export_lineups)
    publish_web_data(handler, tmp_path, ScopedSealer(MASTER, open_access=False), [FEB])
    entry = _manifest(tmp_path)["lineups"][0]
    payload = _open(tmp_path, entry, f"competicion:{FEB}")
    assert entry["collection"] == FEB and entry["file"].startswith("lineups/") and entry["games"] == len(payload["teams"]) > 0
    assert payload == json.loads(json.dumps(lineups_export.export_lineups(handler, FEB), default=str))
    with pytest.raises(Exception):
        _open(tmp_path, entry, "club:101")
    db = handler.connection.client["BASKETBALL"]
    without = "L_F_-2_2025_2026_Sin_Pbp"
    db[without].insert_many([{k: v for k, v in g.items() if k != "PLAYBYPLAY"} for g in games.build_games()])
    publish_web_data(handler, tmp_path / "other", ScopedSealer(MASTER), [without])
    assert _manifest(tmp_path / "other").get("lineups", []) == []


def test_the_files_of_a_competition_that_left_the_publication_are_removed_for_every_section(handler, tmp_path):
    sealer = ScopedSealer(MASTER)
    publish_web_data(handler, tmp_path, sealer, [FEB, FBCYL])
    gone = [s["file"] for s in _manifest(tmp_path)["shots"] if s["collection"] == FBCYL]
    publish_web_data(handler, tmp_path, sealer, [FEB])
    assert gone and not any((tmp_path / f).exists() for f in gone)


# Issue #677: the match list and the analysis of every match, sealed by competition in a file of their own.
def test_the_matches_of_every_competition_are_published_sealed_for_it(handler, tmp_path):
    from src.local_data.matches_export import export_matches

    publish_web_data(handler, tmp_path, ScopedSealer(MASTER, open_access=False), [FEB, FBCYL])
    manifest = _manifest(tmp_path)
    assert sorted(m["collection"] for m in manifest["matches"]) == sorted([FEB, FBCYL])
    entry = next(m for m in manifest["matches"] if m["collection"] == FEB)
    assert entry["file"].startswith("matches/") and entry["sha256"][:12] in entry["file"] and entry["games"] == 12
    assert _open(tmp_path, entry, f"competicion:{FEB}") == json.loads(json.dumps(export_matches(handler, FEB), default=str))
    with pytest.raises(Exception):
        _open(tmp_path, entry, "club:101")


# Issue #679: the possessions page of each competition (table, consistency and quality CSV) and, apart, its per-possession CSV: sealed by competition like the rest.
def test_the_possessions_of_every_competition_are_published_sealed_for_it(handler, tmp_path):
    publish_web_data(handler, tmp_path, ScopedSealer(MASTER, open_access=False), [FEB, FBCYL])
    manifest = _manifest(tmp_path)
    assert sorted(p["collection"] for p in manifest["possessions"]) == sorted([FEB, FBCYL])
    entry = next(p for p in manifest["possessions"] if p["collection"] == FEB)
    assert entry["file"].startswith("possessions/") and entry["sha256"][:12] in entry["file"]
    payload = _open(tmp_path, entry, f"competicion:{FEB}")
    assert set(payload) >= {"table", "consistency", "quality_csv"} and payload["table"]
    with pytest.raises(Exception):
        _open(tmp_path, entry, "club:101")


def test_the_per_possession_csv_is_a_section_of_its_own_and_only_where_there_are_possessions(handler, tmp_path, monkeypatch):
    from src.local_data import web_data

    publish_web_data(handler, tmp_path, ScopedSealer(MASTER), [FEB])
    assert _manifest(tmp_path).get("possession_csv", []) == []                    # the fixture games have no possessions to list: nothing to publish

    monkeypatch.setattr(web_data, "export_possession_csv", lambda _handler, name: {"format": 1, "collection": name, "league": "feb", "games": 2, "csv": "ID_Partido\n1\n"})
    publish_web_data(handler, tmp_path / "with", ScopedSealer(MASTER, open_access=False), [FEB])
    entry = _manifest(tmp_path / "with")["possession_csv"][0]
    assert entry["file"].startswith("possession_csv/") and entry["games"] == 2
    assert _open(tmp_path / "with", entry, f"competicion:{FEB}")["csv"].startswith("ID_Partido")
