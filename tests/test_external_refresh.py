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
    entries = [{"competition": f"{s.upper()} test", "season_label": "2026/2027", "season_value": "2026", "league": s, "division": "Top", "gender": "M", **({"fiba": {"event": "fiba-test-event-2026"}} if s == "fiba" else {}), **({"acb": {"competition_id": 1, "edition_id": 91}} if s == "acb" else {}), **({"conference": "SEC", "ncaa": {"conference_id": "23"}} if s == "ncaa" else {})} for s in sources]
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


class TestGamesStoredAsUnreliableWhenTheRuleChanges:
    """A game flagged unreliable under an older reconciliation rule is judged again from what is stored (no request to the site, no budget), once per version of the rule: a game that is really bad is not asked for again every day."""

    def _stored_unreliable(self, tmp_path, stamp):
        """A run that stores the real sample game, then an archive in which that game is flagged unreliable (as an older rule did) with ``stamp`` as the version it was judged with."""
        from src.local_data.archive import dump_archive

        source = FixtureSource("fiba", docs=FixtureSource("fiba").docs[:1])
        registry.register(source)
        cat = _catalogue(tmp_path, "fiba")
        first = new_mock_db("BASKETBALL")
        refresh_source("fiba", cat, first, tmp_path / "out", NOW)
        name = next(iter(external_collections(cat)))
        flagged = {"_reliable": False, "_mismatches": ["ORB", "DRB"]}
        first[name].update_one({}, {"$set": flagged, **({"$unset": {"_reconciled_with": ""}} if stamp is None else {})})
        if stamp is not None:
            first[name].update_one({}, {"$set": {"_reconciled_with": stamp}})
        dump_archive(first, tmp_path / "out" / "fiba", light=lambda _n: False, only=[name], allow_shrink=False)
        source.docs.clear()                                                    # the site has nothing new to say
        return source, cat, name

    def test_a_game_judged_with_an_older_rule_is_judged_again_without_asking_the_site(self, tmp_path):
        source, cat, name = self._stored_unreliable(tmp_path, stamp=None)
        db = new_mock_db("BASKETBALL")
        status = refresh_source("fiba", cat, db, tmp_path / "out", NOW + timedelta(days=1))
        doc = db[name].find_one()
        assert doc["_reliable"] is True and "_mismatches" not in doc and status["unreliable"] == 0 and status["updated"] == 1
        assert len(source.known[-1]) == 1                                      # it was never asked for again: it is a known id

    def test_a_light_game_without_play_by_play_is_not_judged_again_regression(self, tmp_path):
        """#967: an old season of NCAA keeps the box alone; judging it again without its play-by-play would flip a good game. Its flag stays."""
        from src.local_data.archive import dump_archive

        _source, cat, name = self._stored_unreliable(tmp_path, stamp=None)
        db = new_mock_db("BASKETBALL")
        refresh_source("fiba", cat, db, tmp_path / "out", NOW + timedelta(days=1))          # restores the archive (judged again: reliable)
        db[name].update_one({}, {"$set": {"_reliable": False, "_mismatches": ["ORB"]}, "$unset": {"_reconciled_with": "", "PLAYBYPLAY": ""}})
        dump_archive(db, tmp_path / "out" / "fiba", light=lambda _n: False, only=[name], allow_shrink=False)
        again = new_mock_db("BASKETBALL")
        status = refresh_source("fiba", cat, again, tmp_path / "out", NOW + timedelta(days=2))
        assert again[name].find_one()["_reliable"] is False and status["updated"] == 0

    def test_a_game_judged_with_the_current_rule_is_left_as_it_is(self, tmp_path):
        from src.market.box_reconciliation import RECONCILE_VERSION

        _source, cat, name = self._stored_unreliable(tmp_path, stamp=RECONCILE_VERSION)
        db = new_mock_db("BASKETBALL")
        status = refresh_source("fiba", cat, db, tmp_path / "out", NOW + timedelta(days=1))
        assert db[name].find_one()["_reliable"] is False and status["unreliable"] == 1 and status["updated"] == 0

    def test_a_game_that_is_still_unreliable_is_stamped_so_it_is_not_judged_again_until_the_rule_changes(self, tmp_path, db):
        from src.market.box_reconciliation import RECONCILE_VERSION

        registry.register(FixtureSource("fiba"))
        cat = _catalogue(tmp_path, "fiba")
        refresh_source("fiba", cat, db, tmp_path / "out", NOW)
        stored = list(db[next(iter(external_collections(cat)))].find())
        assert len(stored) == 13 and all(d["_reconciled_with"] == RECONCILE_VERSION for d in stored)
        assert refresh_source("fiba", cat, db, tmp_path / "out", NOW + timedelta(days=1))["updated"] == 0


class TestGamesStoredBeforeAFieldExisted:
    """A source that starts to keep a new field (FIBA's bio, #887) says which stored games lack it (``refetch_filter``): they are not "known", so the source asks for them once more. After that they have the
    field (empty or not), so it is not asked for again."""

    def _run(self, tmp_path, source, db, day=0):
        registry.register(source) if source.name not in registry.SOURCES else None
        return refresh_source("fiba", _catalogue(tmp_path, "fiba"), db, tmp_path / "out", NOW + timedelta(days=day))

    def test_a_stored_game_without_the_field_is_asked_for_again_and_one_with_it_is_not(self, tmp_path, db):
        source = FixtureSource("fiba", docs=FixtureSource("fiba").docs[:2])
        source.refetch_filter = {"BOXSCORE.TEAM.PLAYER.birth": {"$exists": False}}
        self._run(tmp_path, source, db)
        assert source.known[-1] == frozenset()                                       # the first run knows nothing
        name = next(iter(external_collections(_catalogue(tmp_path, "fiba"))))
        with_field, without = (d["_id"] for d in db[name].find())
        doc = db[name].find_one({"_id": with_field})
        for team in doc["BOXSCORE"]["TEAM"]:
            for player in team["PLAYER"]:
                player["birth"] = None                                                # stored by the version that keeps the field (empty is still the field)
        db[name].replace_one({"_id": with_field}, doc)
        from src.local_data.archive import dump_archive

        dump_archive(db, tmp_path / "out" / "fiba", light=lambda _n: False, only=[name], allow_shrink=False)        # the next run restores the archive, so the change has to be in it
        self._run(tmp_path, source, db, day=1)
        assert source.known[-1] == frozenset({with_field}) and without not in source.known[-1]

    def test_a_source_without_the_filter_knows_every_stored_game(self, tmp_path, db):
        source = FixtureSource("fiba", docs=FixtureSource("fiba").docs[:2])
        self._run(tmp_path, source, db)
        self._run(tmp_path, source, db, day=1)
        assert len(source.known[-1]) == 2


class TestLightSeasons:
    """#967 (decision of 24/11/2026): a source that asks for it (NCAA) keeps play-by-play and shots only of the current season and the previous one; the older ones keep the box alone."""

    @staticmethod
    def _catalogue(tmp_path, seasons):
        entries = [{"competition": "D1 Men", "season_label": f"{y}/{y + 1}", "season_value": str(y), "league": "ncaa", "division": "D1", "gender": "M", "conference": "SEC", "ncaa": {"conference_id": "23"}, "active": True}
                   for y in seasons]
        path = tmp_path / "competitions.json"
        path.write_text(json.dumps({"competitions": entries}), encoding="utf-8")
        return load_catalogue(path)

    @staticmethod
    def _stored(out, name):
        import gzip

        manifest = json.loads((out / "ncaa" / "archive.json").read_text(encoding="utf-8"))
        entry = next(c for c in manifest["collections"] if c["name"] == name)
        docs = [json.loads(line) for line in gzip.decompress((out / "ncaa" / entry["file"]).read_bytes()).splitlines()]
        return entry, docs

    def _run(self, tmp_path, db, source, days=0, seasons=(2023, 2024, 2025)):
        registry.SOURCES.clear()
        registry.register(source)
        return refresh_source("ncaa", self._catalogue(tmp_path, seasons), db, tmp_path / "out", NOW + timedelta(days=days))

    def test_only_the_two_latest_seasons_keep_play_by_play_and_shots(self, tmp_path, db):
        source = FixtureSource("ncaa")
        source.light_history = True
        self._run(tmp_path, db, source)
        names = sorted(external_collections(self._catalogue(tmp_path, (2023, 2024, 2025))))
        full = [self._stored(tmp_path / "out", n) for n in names[1:]]
        old_entry, old_docs = self._stored(tmp_path / "out", names[0])
        assert old_entry["light"] is True and old_docs and all("PLAYBYPLAY" not in d and "SHOTCHART" not in d and "BOXSCORE" in d for d in old_docs)
        assert all(e["light"] is False and any("PLAYBYPLAY" in d for d in docs) for e, docs in full)
        assert any("SHOTCHART" in d for _e, docs in full for d in docs)

    def test_a_source_that_does_not_ask_for_it_keeps_every_season_complete(self, tmp_path, db):
        self._run(tmp_path, db, FixtureSource("ncaa"))
        names = sorted(external_collections(self._catalogue(tmp_path, (2023, 2024, 2025))))
        entry, docs = self._stored(tmp_path / "out", names[0])
        assert entry["light"] is False and any("PLAYBYPLAY" in d for d in docs)

    def test_running_again_changes_nothing_and_the_light_games_are_not_asked_for_again(self, tmp_path, db):
        source = FixtureSource("ncaa")
        source.light_history = True
        self._run(tmp_path, db, source)
        first = _bytes(tmp_path / "out", "ncaa")
        fresh = new_mock_db("BASKETBALL")                         # a refresh restores the (light) archive into an empty Mongo
        again = FixtureSource("ncaa")
        again.light_history = True
        status = self._run(tmp_path, fresh, again, days=1)
        assert _bytes(tmp_path / "out", "ncaa") == first and status["new"] == 0 and status["ok"] is True
        assert len(again.known[0]) == 13                           # the games of the oldest season are known: no request for them

    def test_a_season_that_becomes_old_is_lightened_on_the_next_run(self, tmp_path, db):
        source = FixtureSource("ncaa")
        source.light_history = True
        self._run(tmp_path, db, source, seasons=(2024, 2025))
        name = sorted(external_collections(self._catalogue(tmp_path, (2024, 2025))))[0]
        assert self._stored(tmp_path / "out", name)[0]["light"] is False
        self._run(tmp_path, new_mock_db("BASKETBALL"), source, days=1, seasons=(2024, 2025, 2026))             # 2026 starts: the catalogue lists three seasons
        assert self._stored(tmp_path / "out", name)[0]["light"] is True


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

    def test_a_run_that_fails_midway_keeps_what_it_had_already_read_and_does_not_move_its_date_regression(self, tmp_path, db):
        """#1090: the archive was written only after every entry, so an exception at game 900 of 1,200 lost the 20 minutes of reading. The games already merged are saved; ``last_ok`` stays, so the next run asks again."""
        class Dies(FixtureSource):
            def fetch(self, entry, since, known=frozenset()):
                for doc in self.docs[:5]:
                    yield doc
                raise RuntimeError("the connection died at game 6")

        registry.register(Dies("ncaa"))
        cat = _catalogue(tmp_path, "ncaa")
        status = refresh_source("ncaa", cat, db, tmp_path / "out", NOW)
        assert status["ok"] is False and "game 6" in status["error"] and status["last_ok"] is None
        assert status["saved"] == 5 and _status(tmp_path / "out", "ncaa")["saved"] == 5
        fresh = new_mock_db("BASKETBALL")
        again = FixtureSource("ncaa")
        registry.SOURCES.clear()
        registry.register(again)
        done = refresh_source("ncaa", cat, fresh, tmp_path / "out", NOW + timedelta(days=1))
        assert done["ok"] is True and done["games"] == 13 and done["new"] == 8       # the 5 saved ones are not new again
        assert again.asked == [("NCAA test", None)] and len(again.known[-1]) == 5      # no good run yet: everything is asked for, but it knows what it already has

    def test_a_run_that_fails_before_restoring_the_archive_does_not_write_one(self, tmp_path, db, monkeypatch):
        registry.register(FixtureSource("ncaa"))
        cat = _catalogue(tmp_path, "ncaa")
        refresh_source("ncaa", cat, db, tmp_path / "out", NOW)
        before = _bytes(tmp_path / "out", "ncaa")
        import src.external.refresh as refresh
        monkeypatch.setattr(refresh, "load_archive", lambda *a, **k: (_ for _ in ()).throw(OSError("the archive cannot be read")))
        status = refresh_source("ncaa", cat, new_mock_db("BASKETBALL"), tmp_path / "out", NOW + timedelta(days=1))
        assert status["ok"] is False and "saved" not in status and _bytes(tmp_path / "out", "ncaa") == before

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
                                                     **({"fiba": {"event": "fiba-test-event-2026"}} if s == "fiba" else {}), **({"conference": "SEC", "ncaa": {"conference_id": "23"}} if s == "ncaa" else {})} for s in sources]}), encoding="utf-8")
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

    def test_a_source_with_no_scraper_yet_exits_zero_so_the_job_stays_green(self, cli, tmp_path, db, monkeypatch):
        monkeypatch.setattr("src.external.sources.default_source", lambda name, budget=None: None)         # every source of today has its scraper (ACB, FIBA and NCAA): one that has none yet is simulated
        assert cli.main(["--source", "ncaa", *self._argv(tmp_path, "ncaa")], db=db, now=NOW) == 0
        assert not (tmp_path / "out").exists()

    def test_an_unknown_source_is_refused(self, cli, tmp_path, db):
        with pytest.raises(SystemExit):
            cli.main(["--source", "basketball", *self._argv(tmp_path, "fiba")], db=db, now=NOW)


class TestARunThatStoppedForItsBudget:
    """A source that stops for its budget (the first load of NCAA goes by batches, #888) has not seen everything since the last good run: what it read is kept, but the date the next run starts
    from must not move, or the days it did not reach would be skipped for ever."""

    def run(self, tmp_path, db, source, when):
        registry.SOURCES.pop("fiba", None)
        registry.register(source)
        return refresh_source("fiba", _catalogue(tmp_path, "fiba"), db, tmp_path / "out", when)

    def test_a_partial_run_keeps_its_games_says_it_is_partial_and_does_not_move_the_date(self, tmp_path, db):
        complete = FixtureSource("fiba")
        self.run(tmp_path, db, complete, NOW)
        partial = FixtureSource("fiba")
        partial.complete = False
        status = self.run(tmp_path, db, partial, NOW + timedelta(days=1))
        assert status["ok"] is True and status["partial"] is True and status["last_ok"] == "2026-11-17T07:00:00Z" and status["games"] == 13
        assert _status(tmp_path / "out", "fiba")["partial"] is True

    def test_the_next_run_starts_from_the_date_of_the_last_complete_one(self, tmp_path, db):
        self.run(tmp_path, db, FixtureSource("fiba"), NOW)
        partial = FixtureSource("fiba")
        partial.complete = False
        self.run(tmp_path, db, partial, NOW + timedelta(days=1))
        after = FixtureSource("fiba")
        self.run(tmp_path, db, after, NOW + timedelta(days=2))
        assert after.asked[0][1] == "2026-11-14"                      # 17/11 minus the window of 3 days: the partial run of the 18th did not move it

    def test_a_first_load_that_never_completes_has_no_date_so_the_next_one_asks_for_everything(self, tmp_path, db):
        partial = FixtureSource("fiba")
        partial.complete = False
        status = self.run(tmp_path, db, partial, NOW)
        assert status["last_ok"] is None and status["partial"] is True
        after = FixtureSource("fiba")
        self.run(tmp_path, db, after, NOW + timedelta(days=1))
        assert after.asked[0][1] is None

    def test_a_complete_run_says_nothing_about_being_partial_and_moves_the_date(self, tmp_path, db):
        status = self.run(tmp_path, db, FixtureSource("fiba"), NOW)
        assert "partial" not in status and status["last_ok"] == "2026-11-17T07:00:00Z"
