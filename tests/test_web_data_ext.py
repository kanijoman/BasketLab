"""The publication of the external sources, ``web-data-ext`` (#884, D0, PR B): what the web reads of ACB, FIBA and NCAA, apart from ``web-data`` so that a failure of one never stops the other.

It restores the archive of each source into a database that lives as long as the run, leaves out the games that do not reconcile with their official box (they stay in the archive, flagged, but never enter rates,
percentiles or the published rows) and publishes the REAL pipeline of ``web-data`` over what is left: the sealed rows, the manifest with the ``league`` of each competition and the freshness of each source.
The tests run the whole chain on real FEB games badged as FIBA: refresh -> archive -> publication.
"""
import json
from datetime import datetime, timedelta, timezone

import mongomock
import pytest

from market_helpers import FixtureSource  # noqa: E402  (it also puts tests/local_vectors on the path)

from mongomock_handler import mongomock_handler  # noqa: E402

from src.external import registry  # noqa: E402
from src.external.publish import publish_external  # noqa: E402
from src.external.refresh import refresh_source  # noqa: E402
from src.live_prep.package_scopes import open_sealed, scope_key  # noqa: E402
from src.live_prep.package_sealing import ScopedSealer  # noqa: E402
from src.local_data.contract import validate_manifest  # noqa: E402
from src.services.competition_catalogue import load_catalogue  # noqa: E402

NOW = datetime(2026, 11, 17, 7, 0, tzinfo=timezone.utc)
SECRET = "ext-test-master-secret"
NAME = "FIBA_FIBA_test_2026_"


def _catalogue(tmp_path, *sources):
    entries = [{"competition": f"{s.upper()} test", "season_label": "2026/2027", "season_value": "2026", "league": s, "division": "Top", "gender": "F" if s == "fiba" else "M",
                **({"conference": "SEC"} if s == "ncaa" else {})} for s in sources]
    path = tmp_path / "competitions.json"
    path.write_text(json.dumps({"competitions": entries}), encoding="utf-8")
    return load_catalogue(path)


@pytest.fixture(autouse=True)
def clean_registry():
    saved = dict(registry.SOURCES)
    registry.SOURCES.clear()
    yield
    registry.SOURCES.clear()
    registry.SOURCES.update(saved)


@pytest.fixture()
def handler():
    return mongomock_handler()


def _publish(tmp_path, handler, catalogue):
    return publish_external(tmp_path / "archive-ext", tmp_path / "web-ext", catalogue, handler, ScopedSealer(SECRET, open_access=True))


def _open(tmp_path, entry):
    envelope = json.loads((tmp_path / "web-ext" / entry["file"]).read_text(encoding="utf-8"))
    return json.loads(open_sealed(envelope, entry["wraps"], {"abierto": scope_key(SECRET, "abierto")}))


def _refresh(tmp_path, catalogue, source="fiba", now=NOW):
    return refresh_source(source, catalogue, mongomock.MongoClient()["BASKETBALL"], tmp_path / "archive-ext", now)


def test_the_whole_chain_publishes_the_reliable_games_of_a_source_under_its_own_league(tmp_path, handler):
    registry.register(FixtureSource("fiba"))
    cat = _catalogue(tmp_path, "fiba")
    _refresh(tmp_path, cat)
    manifest = _publish(tmp_path, handler, cat)
    validate_manifest(manifest)
    [entry] = manifest["rows"]
    assert (entry["collection"], entry["league"], entry["gender"], entry["category"]) == (NAME, "fiba", "F", "senior")
    assert json.loads((tmp_path / "web-ext" / "index.json").read_text(encoding="utf-8")) == manifest and manifest["open_key"]
    rows = _open(tmp_path, entry)
    assert rows["league"] == "fiba" and {r["team_id"] for r in rows["team_rows"]} == {"fiba:982047", "fiba:981204"}


def test_the_games_that_do_not_reconcile_stay_in_the_archive_but_not_in_what_is_published(tmp_path, handler):
    registry.register(FixtureSource("fiba"))
    cat = _catalogue(tmp_path, "fiba")
    _refresh(tmp_path, cat)
    manifest = _publish(tmp_path, handler, cat)
    assert manifest["rows"][0]["games"] == 1                                  # the real sample game, whose play-by-play and box reconcile; the 12 of the fixture league have no play-by-play
    [freshness] = manifest["sources"]
    assert (freshness["games"], freshness["unreliable"], freshness["published"]) == (13, 12, 1)
    archive = json.loads((tmp_path / "archive-ext" / "fiba" / "archive.json").read_text(encoding="utf-8"))
    assert archive["collections"][0]["games"] == 13                           # nothing was discarded from the archive


def test_the_manifest_says_how_fresh_each_source_is(tmp_path, handler):
    registry.register(FixtureSource("fiba"))
    registry.register(FixtureSource("acb"))
    cat = _catalogue(tmp_path, "fiba", "acb")
    _refresh(tmp_path, cat, "fiba")
    _refresh(tmp_path, cat, "acb", NOW + timedelta(hours=1))
    manifest = _publish(tmp_path, handler, cat)
    assert {s["source"]: (s["state"], s["last_ok"]) for s in manifest["sources"]} == {"fiba": ("ok", "2026-11-17T07:00:00Z"), "acb": ("ok", "2026-11-17T08:00:00Z")}
    assert [e["league"] for e in manifest["rows"]] == ["acb", "fiba"]


def test_a_source_whose_last_run_failed_still_publishes_what_it_had_and_says_it_failed(tmp_path, handler):
    source = FixtureSource("fiba")
    registry.register(source)
    cat = _catalogue(tmp_path, "fiba")
    _refresh(tmp_path, cat)
    source.boom = "the site is down"
    _refresh(tmp_path, cat, now=NOW + timedelta(days=1))
    manifest = _publish(tmp_path, handler, cat)
    [freshness] = manifest["sources"]
    assert freshness["state"] == "failed" and freshness["ok"] is False and freshness["last_ok"] == "2026-11-17T07:00:00Z"      # the web can say «data from 17/11»
    assert manifest["rows"][0]["games"] == 1                                  # and the rows of the last good run are still there


def test_with_no_archive_it_publishes_an_empty_valid_manifest(tmp_path, handler):
    manifest = _publish(tmp_path, handler, _catalogue(tmp_path, "ncaa"))
    validate_manifest(manifest)
    assert manifest["rows"] == [] and manifest["sources"] == []
    assert (tmp_path / "web-ext" / "index.json").is_file()


def test_a_source_that_is_pending_has_no_folder_and_is_not_listed(tmp_path, handler):
    registry.register(FixtureSource("fiba"))
    cat = _catalogue(tmp_path, "fiba", "ncaa")
    _refresh(tmp_path, cat)
    _refresh(tmp_path, cat, "ncaa")                                           # no scraper registered for NCAA yet: pending, nothing written
    assert [s["source"] for s in _publish(tmp_path, handler, cat)["sources"]] == ["fiba"]


def test_feb_collections_never_get_into_it(tmp_path, handler):
    """Even with a FEB game in the very database of the publication, only the external competitions of the catalogue are published."""
    registry.register(FixtureSource("fiba"))
    cat = _catalogue(tmp_path, "fiba")
    _refresh(tmp_path, cat)
    handler.connection.client["BASKETBALL"]["PRIMERA_FEB_2025_2026_Liga_Regular_Único"].insert_one({"_id": 1, "HEADER": {"TEAM": []}})
    assert [e["collection"] for e in _publish(tmp_path, handler, cat)["rows"]] == [NAME]


def test_publishing_twice_changes_nothing_in_the_rows(tmp_path, handler):
    registry.register(FixtureSource("fiba"))
    cat = _catalogue(tmp_path, "fiba")
    _refresh(tmp_path, cat)
    first = _publish(tmp_path, handler, cat)
    second = _publish(tmp_path, handler, cat)
    assert second["rows"] == first["rows"]                                     # the sealed file keeps its bytes: it never changes in place


class TestEntryPoint:
    """``run_web_data_ext.py``: what the workflow runs."""

    @pytest.fixture()
    def cli(self):
        import sys
        from pathlib import Path

        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        import run_web_data_ext
        return run_web_data_ext

    def _argv(self, tmp_path, cat_path):
        return ["--archive", str(tmp_path / "archive-ext"), "--out", str(tmp_path / "web-ext"), "--catalogue", str(cat_path)]

    def test_it_publishes_and_says_what_it_did(self, cli, tmp_path, handler, monkeypatch, capsys):
        monkeypatch.setenv("PACKAGE_MASTER_KEY", SECRET)
        registry.register(FixtureSource("fiba"))
        cat = _catalogue(tmp_path, "fiba")
        _refresh(tmp_path, cat)
        assert cli.main(self._argv(tmp_path, tmp_path / "competitions.json"), handler=handler) == 0
        out = capsys.readouterr().out
        assert "fiba: ok" in out and "1 of 13 games published (12 do not reconcile)" in out and "1 competitions, 1 sources" in out
        assert json.loads((tmp_path / "web-ext" / "index.json").read_text(encoding="utf-8"))["rows"][0]["league"] == "fiba"

    def test_without_the_master_key_it_refuses_and_writes_nothing(self, cli, tmp_path, handler, monkeypatch):
        monkeypatch.delenv("PACKAGE_MASTER_KEY", raising=False)
        monkeypatch.delenv("PACKAGE_PASSWORD", raising=False)
        _catalogue(tmp_path, "fiba")
        assert cli.main(self._argv(tmp_path, tmp_path / "competitions.json"), handler=handler) == 2
        assert not (tmp_path / "web-ext").exists()
