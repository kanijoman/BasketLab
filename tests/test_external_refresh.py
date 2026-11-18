"""The refresh of an external source (#884, D0, PR B): one job per source, isolated from the others and from FEB, that keeps its own archive and says how fresh it is.

A source is an object registered by name that hands over the games of a competition in the canonical format. The runner validates each one (``validate_game``), marks it with its reconciliation (``reconcile_game``: an
unreliable game is KEPT and flagged, nothing is discarded), merges it by ``_id`` into the archive of the source (the format of the private archive: one ``.jsonl.gz`` per competition with its sha256) and writes
``status.json``: when it ran, when it last worked and how many games it has. A failing source never stops another one and never touches its own archive. The tests use a source built on REAL FEB games badged as the source.
"""
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from db_helpers import new_mock_db

from market_helpers import FixtureSource  # noqa: E402  (it also puts tests/local_vectors on the path)

import games  # noqa: E402

from src.external import registry  # noqa: E402
from src.external.refresh import refresh_source, run_sources  # noqa: E402
from src.services.competition_catalogue import external_collections, load_catalogue  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 11, 17, 7, 0, tzinfo=timezone.utc)


def _catalogue(tmp_path, *sources):
    entries = [{"competition": f"{s.upper()} test", "season_label": "2026/2027", "season_value": "2026", "league": s, "division": "Top", "gender": "M", **({"fiba": {"event": "fiba-test-event-2026"}} if s == "fiba" else {}), **({"conference": "SEC"} if s == "ncaa" else {})} for s in sources]
    path = tmp_path / "competitions.json"
    path.write_text(json.dumps({"competitions": entries}), encoding="utf-8")
    return load_catalogue(path)


@pytest.fixture()
def db():
    return new_mock_db("BASKETBALL")


@pytest.fixture(autouse=True)
def clean_registry():
    saved = dict(registry.SOURCES)
    registry.SOURCES.clear()
    yield
    registry.SOURCES.clear()
    registry.SOURCES.update(saved)


def _status(out, source):
    return json.loads((out / source / "status.json").read_text(encoding="utf-8"))


def _bytes(out, source):
    return {p.name: p.read_bytes() for p in sorted((out / source).glob("*")) if p.name != "status.json"}


class TestRefreshOfOneSource:
    def test_the_first_run_stores_every_game_in_the_archive_of_its_source_and_says_so(self, tmp_path, db):
        registry.register(FixtureSource("fiba"))
        status = refresh_source("fiba", _catalogue(tmp_path, "fiba"), db, tmp_path / "out", NOW)
        assert status["ok"] is True and status["games"] == 13 and status["new"] == 13 and status["rejected"] == []
        archive = json.loads((tmp_path / "out" / "fiba" / "archive.json").read_text(encoding="utf-8"))
        assert [c["name"] for c in archive["collections"]] == ["FIBA_FIBA_test_2026_"]
        assert _status(tmp_path / "out", "fiba")["finished"] == "2026-11-17T07:00:00Z"

    def test_a_game_that_does_not_reconcile_is_kept_and_flagged_never_discarded(self, tmp_path, db):
        registry.register(FixtureSource("fiba"))
        refresh_source("fiba", _catalogue(tmp_path, "fiba"), db, tmp_path / "out", NOW)
        stored = {d["_id"]: d for d in db["FIBA_FIBA_test_2026_"].find()}
        assert len(stored) == 13
        assert stored["fiba:9001"]["_reliable"] is False                      # the games of the fixture league have a box and no play-by-play: they do not reconcile
        reliable = [d for d in stored.values() if d["_reliable"]]
        assert len(reliable) == 1 and reliable[0]["_id"].startswith("fiba:")  # the real sample game, whose play-by-play and box reconcile
        assert refresh_source("fiba", _catalogue(tmp_path, "fiba"), db, tmp_path / "out", NOW)["unreliable"] == 12

    def test_a_game_that_is_not_canonical_is_rejected_with_its_reason_and_the_others_still_go_in(self, tmp_path, db):
        source = FixtureSource("fiba")
        source.docs.append(games.build_games()[0])                              # a raw FEB game: no _league, ids without prefix
        registry.register(source)
        status = refresh_source("fiba", _catalogue(tmp_path, "fiba"), db, tmp_path / "out", NOW)
        assert status["ok"] is True and status["games"] == 13
        assert len(status["rejected"]) == 1 and "_league" in status["rejected"][0]["reason"] and status["rejected"][0]["id"] == "9001"

    def test_running_it_again_changes_nothing_in_the_archive(self, tmp_path, db):
        registry.register(FixtureSource("ncaa"))
        cat = _catalogue(tmp_path, "ncaa")
        refresh_source("ncaa", cat, db, tmp_path / "out", NOW)
        first = _bytes(tmp_path / "out", "ncaa")
        status = refresh_source("ncaa", cat, db, tmp_path / "out", NOW + timedelta(hours=24))
        assert _bytes(tmp_path / "out", "ncaa") == first and status["new"] == 0 and status["games"] == 13
        assert _status(tmp_path / "out", "ncaa")["last_ok"] == "2026-11-18T07:00:00Z"        # it did run: only its freshness moved

    def test_a_game_corrected_later_replaces_the_stored_one_by_its_id(self, tmp_path, db):
        source = FixtureSource("acb")
        registry.register(source)
        cat = _catalogue(tmp_path, "acb")
        refresh_source("acb", cat, db, tmp_path / "out", NOW)
        source.docs[0]["HEADER"]["TEAM"][0]["pts"] = "75"                        # the source corrects a score
        status = refresh_source("acb", cat, db, tmp_path / "out", NOW + timedelta(days=1))
        stored = db[next(iter(external_collections(cat)))].find_one({"_id": source.docs[0]["_id"]})
        assert stored["HEADER"]["TEAM"][0]["pts"] == "75" and status["games"] == 13 and status["new"] == 0 and status["updated"] == 1

    def test_the_rewrite_window_is_asked_for_only_after_a_good_run(self, tmp_path, db):
        source = FixtureSource("fiba")
        registry.register(source)
        cat = _catalogue(tmp_path, "fiba")
        refresh_source("fiba", cat, db, tmp_path / "out", NOW, window_days=3)
        refresh_source("fiba", cat, db, tmp_path / "out", NOW + timedelta(days=1), window_days=3)
        assert source.asked == [("FIBA test", None), ("FIBA test", "2026-11-14")]     # the whole history the first time, then the last 3 days before the previous good run

    def test_a_source_that_is_not_registered_yet_is_pending_not_a_failure_and_writes_nothing(self, tmp_path, db):
        status = refresh_source("ncaa", _catalogue(tmp_path, "ncaa"), db, tmp_path / "out", NOW)
        assert status["state"] == "pending" and status["ok"] is None
        assert not (tmp_path / "out").exists()

    def test_a_source_with_no_active_competition_has_nothing_to_do(self, tmp_path, db):
        registry.register(FixtureSource("acb"))
        assert refresh_source("acb", _catalogue(tmp_path, "fiba"), db, tmp_path / "out", NOW)["state"] == "pending"


class TestWhatTheSourceIsToldAndWhatItSays:
    def test_the_source_is_given_the_ids_it_already_has_so_that_it_does_not_ask_for_them_again(self, tmp_path, db):
        source = FixtureSource("fiba")
        registry.register(source)
        cat = _catalogue(tmp_path, "fiba")
        refresh_source("fiba", cat, db, tmp_path / "out", NOW)
        refresh_source("fiba", cat, db, tmp_path / "out", NOW + timedelta(days=1))
        assert source.known[0] == frozenset() and len(source.known[1]) == 13 and "fiba:9001" in source.known[1]

    def test_what_the_source_has_to_say_of_its_run_goes_to_the_status_and_is_capped(self, tmp_path, db):
        source = FixtureSource("fiba")
        source.notes = [f"game {i}: not found" for i in range(30)]
        registry.register(source)
        status = refresh_source("fiba", _catalogue(tmp_path, "fiba"), db, tmp_path / "out", NOW)
        assert status["notes"] == source.notes[:20] and status["notes_total"] == 30
        assert _status(tmp_path / "out", "fiba")["notes"] == source.notes[:20]

    def test_a_source_with_nothing_to_say_has_no_notes_in_its_status(self, tmp_path, db):
        registry.register(FixtureSource("fiba"))
        assert "notes" not in refresh_source("fiba", _catalogue(tmp_path, "fiba"), db, tmp_path / "out", NOW)


class TestIsolation:
    def test_a_failing_source_reports_it_keeps_its_last_good_date_and_leaves_its_archive_alone(self, tmp_path, db):
        good = FixtureSource("ncaa")
        registry.register(good)
        cat = _catalogue(tmp_path, "ncaa")
        refresh_source("ncaa", cat, db, tmp_path / "out", NOW)
        before = _bytes(tmp_path / "out", "ncaa")
        good.boom = "the site changed its hashes"
        status = refresh_source("ncaa", cat, db, tmp_path / "out", NOW + timedelta(days=1))
        assert status["ok"] is False and "hashes" in status["error"]
        assert _bytes(tmp_path / "out", "ncaa") == before
        saved = _status(tmp_path / "out", "ncaa")
        assert saved["ok"] is False and saved["last_ok"] == "2026-11-17T07:00:00Z" and saved["finished"] == "2026-11-18T07:00:00Z"
        assert (saved["games"], saved["unreliable"]) == (13, 12)                  # what the archive holds does not change because a run failed: the status keeps the counts of the last good one

    def test_a_failure_of_one_source_does_not_stop_the_others(self, tmp_path, db):
        registry.register(FixtureSource("ncaa", boom="NCAA is down"))
        registry.register(FixtureSource("fiba"))
        registry.register(FixtureSource("acb"))
        cat = _catalogue(tmp_path, "ncaa", "fiba", "acb")
        results = run_sources(["ncaa", "fiba", "acb"], cat, db, tmp_path / "out", NOW)
        assert {s: r["ok"] for s, r in results.items()} == {"ncaa": False, "fiba": True, "acb": True}
        assert (tmp_path / "out" / "fiba" / "archive.json").is_file() and (tmp_path / "out" / "acb" / "archive.json").is_file()

    def test_nothing_is_written_outside_the_folder_of_the_source(self, tmp_path, db):
        registry.register(FixtureSource("fiba"))
        refresh_source("fiba", _catalogue(tmp_path, "fiba"), db, tmp_path / "out", NOW)
        assert [p.name for p in (tmp_path / "out").iterdir()] == ["fiba"]


class TestEntryPoint:
    """``run_external_refresh.py``: what the workflow runs (one job per source) and what it asks to build its matrix."""

    @pytest.fixture()
    def cli(self):
        sys.path.insert(0, str(ROOT))
        import run_external_refresh
        return run_external_refresh

    def _argv(self, tmp_path, *sources, extra=()):
        cat = tmp_path / "competitions.json"
        cat.write_text(json.dumps({"competitions": [{"competition": f"{s.upper()} test", "season_label": "2026/2027", "season_value": "2026", "league": s, "division": "Top", "gender": "M",
                                                     **({"fiba": {"event": "fiba-test-event-2026"}} if s == "fiba" else {}), **({"conference": "SEC"} if s == "ncaa" else {})} for s in sources]}), encoding="utf-8")
        return ["--catalogue", str(cat), "--out", str(tmp_path / "out"), *extra]

    def test_the_sources_of_the_catalogue_are_listed_for_the_matrix_of_the_workflow(self, cli, tmp_path, capsys):
        assert cli.main(["--list-sources", *self._argv(tmp_path, "ncaa", "fiba")]) == 0
        assert json.loads(capsys.readouterr().out) == ["fiba", "ncaa"]

    def test_a_paused_competition_has_no_job(self, cli, tmp_path, capsys):
        argv = self._argv(tmp_path, "fiba")
        cat = Path(argv[1])
        data = json.loads(cat.read_text(encoding="utf-8"))
        data["competitions"][0]["active"] = False
        cat.write_text(json.dumps(data), encoding="utf-8")
        cli.main(["--list-sources", *argv])
        assert json.loads(capsys.readouterr().out) == []

    def test_a_good_run_exits_zero_and_a_failed_one_exits_one_so_the_job_goes_red(self, cli, tmp_path, db):
        registry.register(FixtureSource("fiba"))
        assert cli.main(["--source", "fiba", *self._argv(tmp_path, "fiba")], db=db, now=NOW) == 0
        registry.SOURCES["fiba"].boom = "down"
        assert cli.main(["--source", "fiba", *self._argv(tmp_path, "fiba")], db=db, now=NOW + timedelta(days=1)) == 1

    def test_a_source_with_no_scraper_yet_exits_zero_so_the_job_stays_green(self, cli, tmp_path, db):
        assert cli.main(["--source", "ncaa", *self._argv(tmp_path, "ncaa")], db=db, now=NOW) == 0
        assert not (tmp_path / "out").exists()

    def test_an_unknown_source_is_refused(self, cli, tmp_path, db):
        with pytest.raises(SystemExit):
            cli.main(["--source", "euroleague", *self._argv(tmp_path, "fiba")], db=db, now=NOW)
