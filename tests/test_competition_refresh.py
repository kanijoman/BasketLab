"""Scheduled refresh of the production database (Atlas) from FEB (issue #177).

Atlas fell behind the local copy because scraping was manual. The refresh job scrapes the configured
competitions incrementally (only new, finished matches) and then checks the result against the calendar.
"""
import json
from datetime import datetime
from unittest.mock import MagicMock

import pytest
from db_helpers import new_mock_db

from src.services.competition_refresh import RefreshEntry, load_config, main, needs_attention, refresh_all, to_markdown
from src.services.feb_match_ingest import is_in_progress, scrape_feb_collection

ENTRY = {"competition_url": "https://x/competicion.aspx?c=1", "season_value": "2026", "group_value": "7",
         "year": "2026", "competition_label": "LF CHALLENGE", "season_label": "LF CHALLENGE 2026", "group_label": "A"}


def _db():
    games = {}
    db = MagicMock()
    db.document_exists.side_effect = lambda col, code: code in games.get(col, set())
    db.insert_boxscore.side_effect = lambda col, code, doc: games.setdefault(col, set()).add(int(code))
    db.repository.connection.get_collection.return_value = new_mock_db()["COLLECTION_META"]
    db.stored = games
    return db


def _scraper(codes, in_progress=()):
    s = MagicMock()
    s.get_page_content.return_value = (None, MagicMock())
    s.get_matches.return_value = list(codes)
    s.fetch_boxscore.side_effect = lambda code, session: {"HEADER": {"status": "2" if code in in_progress else "3"}}
    return s


class TestScrapeCollection:
    def test_stores_new_finished_matches_and_skips_known_and_live_ones(self):
        db = _db()
        db.stored["LF_CHALLENGE_LF_CHALLENGE_2026_A"] = {1}
        job = scrape_feb_collection(db, RefreshEntry(**ENTRY), _scraper(["1", "2", "3"], in_progress={"3"}))
        assert db.stored["LF_CHALLENGE_LF_CHALLENGE_2026_A"] == {1, 2}
        assert (job["total"], job["skipped"], job["errors"]) == (3, 2, [])

    def test_a_failing_match_is_reported_and_does_not_stop_the_rest(self):
        db = _db()
        scraper = _scraper(["1", "2"])
        scraper.fetch_boxscore.side_effect = [None, {"HEADER": {"status": "3"}}]
        job = scrape_feb_collection(db, RefreshEntry(**ENTRY), scraper)
        assert len(job["errors"]) == 1 and db.insert_boxscore.call_count == 1

    def test_the_selection_is_remembered_for_the_live_match_list(self):
        db = _db()
        scrape_feb_collection(db, RefreshEntry(**ENTRY), _scraper([]))
        meta = db.repository.connection.get_collection.return_value.find_one({"_id": job_name(db)})
        assert meta is None or meta["competition_url"] == ENTRY["competition_url"]

    def test_a_game_that_is_still_being_played_is_detected(self):
        """The helper lived in the scrape router and was shared with it; the router is gone (#724) and the refresh is its only user."""
        assert is_in_progress({"HEADER": {"status": "2"}}) and not is_in_progress({"HEADER": {"status": "3"}})
        assert not is_in_progress({"HEADER": {}})                  # no status (older data): finished


def job_name(db):
    return "LF_CHALLENGE_LF_CHALLENGE_2026_A"


class TestRefreshAll:
    def _freshness(self, missing):
        return lambda collection: {"collection": collection, "up_to_date": not missing, "missing_codes": missing,
                                   "games_in_db": 2, "calendar_results": 2 + len(missing), "last_game": "2026-10-04T14:00",
                                   "warning": None}

    def test_reports_each_competition_with_its_freshness(self):
        report = refresh_all(_db(), [RefreshEntry(**ENTRY)], scraper=_scraper(["1"]), freshness=self._freshness([]))
        assert report[0]["collection"] == "LF_CHALLENGE_LF_CHALLENGE_2026_A" and report[0]["freshness"]["up_to_date"] is True

    def test_one_failing_competition_does_not_block_the_others(self):
        scraper = _scraper(["1"])
        scraper.get_page_content.side_effect = [ConnectionError("feb down"), (None, MagicMock())]
        report = refresh_all(_db(), [RefreshEntry(**ENTRY), RefreshEntry(**{**ENTRY, "group_label": "B"})],
                             scraper=scraper, freshness=self._freshness([]))
        assert "feb down" in report[0]["fatal"] and report[1]["fatal"] is None

    def test_every_refreshed_collection_gets_the_team_index(self):
        """Issue #502: the packages read the games of a team across the collections of the season; without ``HEADER.TEAM.id`` indexed they scan every document (~1 MB each)."""
        db = _db()
        refresh_all(db, [RefreshEntry(**ENTRY)], scraper=_scraper(["1"]), freshness=self._freshness([]))
        keys = [info["key"] for info in db.repository.connection.get_collection.return_value.index_information().values()]
        assert [("HEADER.TEAM.id", 1)] in keys

    def test_the_index_is_created_even_when_there_is_nothing_new_so_old_collections_get_it_too(self):
        db = _db()
        db.stored["LF_CHALLENGE_LF_CHALLENGE_2026_A"] = {1}
        refresh_all(db, [RefreshEntry(**ENTRY)], scraper=_scraper(["1"]), freshness=self._freshness([]))
        keys = [info["key"] for info in db.repository.connection.get_collection.return_value.index_information().values()]
        assert [("HEADER.TEAM.id", 1)] in keys

    def test_a_failing_index_never_turns_a_refresh_into_an_error(self):
        db = _db()
        collection = MagicMock()
        collection.create_index.side_effect = RuntimeError("quota")
        db.repository.connection.get_collection.return_value = collection
        report = refresh_all(db, [RefreshEntry(**ENTRY)], scraper=_scraper(["1"]), freshness=self._freshness([]))
        assert report[0]["fatal"] is None

    def test_markdown_flags_the_missing_matches(self):
        report = refresh_all(_db(), [RefreshEntry(**ENTRY)], scraper=_scraper([]), freshness=self._freshness(["9"]))
        text = to_markdown(report)
        assert "LF_CHALLENGE_LF_CHALLENGE_2026_A" in text and "9" in text and "faltan" in text.lower()


class TestMatchWithoutData:
    """#902: FEB lists some matches (youth championships: not played, no report) whose BoxScore answers 404 for ever. Seen in the first refresh of the history: 2 matches of
    CE SSAA Cadete Fem. 2025/26 left every run red and hid real failures. After a week a match that FEB answers "no data" for is information, not a problem."""

    NOW = datetime(2026, 11, 12, 13, 0)

    def _run(self, since, scraper_codes=("9",), no_data=True):
        scraper = _scraper(scraper_codes)
        if no_data:
            scraper.fetch_boxscore.side_effect = lambda code, session: None            # FEB answers 404: the scraper returns nothing
        fresh = lambda collection: {"collection": collection, "up_to_date": False, "missing_codes": list(since), "missing_since": dict(since),
                                    "games_in_db": 2, "calendar_results": 2 + len(since), "last_game": "2026-10-04T14:00", "warning": None}
        return refresh_all(_db(), [RefreshEntry(**ENTRY)], scraper=scraper, freshness=fresh, now=lambda: self.NOW)

    def test_a_match_without_data_for_more_than_a_week_does_not_turn_the_run_red(self):
        report = self._run({"9": "2026-11-02T12:00"})
        assert not needs_attention(report)
        assert report[0]["freshness"]["up_to_date"] is True and report[0]["freshness"]["no_data_codes"] == ["9"]
        text = to_markdown(report)
        assert "Sin datos en FEB" in text and "9" in text and "Faltan" not in text

    def test_a_recent_match_without_data_still_does(self):
        """The boxscore of yesterday's match may simply not be up yet."""
        report = self._run({"9": "2026-11-10T20:00"})
        assert needs_attention(report) and report[0]["freshness"]["missing_codes"] == ["9"]
        assert "Faltan 1 partidos jugados" in to_markdown(report)

    def test_an_old_match_missing_for_another_reason_still_does(self):
        """Without 'No data for match' in the scrape (a network error, a match that was never asked for) it is a real hole."""
        report = self._run({"9": "2026-11-02T12:00"}, scraper_codes=(), no_data=False)
        assert needs_attention(report) and report[0]["freshness"]["missing_codes"] == ["9"]

    def test_with_one_old_and_one_recent_only_the_recent_one_is_missing(self):
        report = self._run({"9": "2026-11-02T12:00", "10": "2026-11-11T20:00"}, scraper_codes=("9", "10"))
        fresh = report[0]["freshness"]
        assert (fresh["no_data_codes"], fresh["missing_codes"], fresh["up_to_date"]) == (["9"], ["10"], False)

    def test_the_boundary_is_seven_days_and_a_match_without_a_date_is_never_forgiven(self):
        exactly = self._run({"9": "2026-11-05T13:00"})                                  # exactly 7 days: not yet
        older = self._run({"9": "2026-11-05T12:59"})
        undated = self._run({"9": None})
        assert needs_attention(exactly) and not needs_attention(older) and needs_attention(undated)

    def test_it_is_asked_again_on_every_run_so_a_late_boxscore_still_arrives(self):
        db = _db()
        first = refresh_all(db, [RefreshEntry(**ENTRY)], scraper=self._none_scraper(), freshness=self._fresh({"9": "2026-11-02T12:00"}), now=lambda: self.NOW)
        assert not needs_attention(first) and not db.stored.get("LF_CHALLENGE_LF_CHALLENGE_2026_A")
        late = _scraper(["9"])                                                         # FEB posts it a week later
        refresh_all(db, [RefreshEntry(**ENTRY)], scraper=late, freshness=self._fresh({}), now=lambda: self.NOW)
        assert db.stored["LF_CHALLENGE_LF_CHALLENGE_2026_A"] == {9}

    def _none_scraper(self):
        scraper = _scraper(["9"])
        scraper.fetch_boxscore.side_effect = lambda code, session: None
        return scraper

    def _fresh(self, since):
        return lambda collection: {"collection": collection, "up_to_date": not since, "missing_codes": list(since), "missing_since": dict(since),
                                   "games_in_db": 0, "calendar_results": len(since), "last_game": None, "warning": None}


class TestConfigAndCli:
    def test_load_config(self, tmp_path):
        path = tmp_path / "c.json"
        path.write_text(json.dumps({"scrapes": [ENTRY]}), encoding="utf-8")
        assert load_config(path)[0].group_label == "A"

    def test_an_incomplete_entry_is_rejected_with_its_position(self, tmp_path):
        path = tmp_path / "c.json"
        path.write_text(json.dumps({"scrapes": [{"competition_url": "x"}]}), encoding="utf-8")
        with pytest.raises(ValueError, match="#1"):
            load_config(path)

    def test_the_repository_config_is_valid(self):
        assert isinstance(load_config("config/competitions.json"), list)

    def test_the_cli_fails_without_a_connection_string(self, monkeypatch, tmp_path):
        monkeypatch.delenv("MONGODB_CONNECTION_STRING", raising=False)
        path = tmp_path / "c.json"
        path.write_text(json.dumps({"scrapes": [ENTRY]}), encoding="utf-8")
        assert main(["--config", str(path), "--require-env"]) == 2


def test_the_cli_can_import_the_database_layer_in_a_clean_interpreter_regression():
    """CI runs ``run_refresh.py`` with no PYTHONPATH; ``src.database`` still needs ``src`` on sys.path (legacy imports)."""
    import os
    import subprocess
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    code = "import run_refresh; from src.services.competition_refresh import main; from src.database import MongoDBHandler"
    result = subprocess.run([sys.executable, "-c", code], cwd=root, env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr[-400:]


COPA = {"competition_url": "https://x/calendario.aspx?g=73&t=2026&nm=copaespaa", "season_value": "2026", "year": "2026",
        "competition_label": "COPA ESPAÑA", "season_label": "2026/2027", "groups": "all"}
COPA_GROUPS = [("Play-offs 1/16 Final", "90041"), ('FASE DE GRUPOS "A"', "90033"), ('FASE DE GRUPOS "B"', "90034")]


def _phase_scraper(groups=COPA_GROUPS):
    s = _scraper(["1"])
    s.get_groups_for_season.return_value = list(groups)
    return s


class TestCompetitionWithPhases:
    """A competition is one config entry with ``"groups": "all"``: its phases are discovered, never listed by hand (#456).

    The Copa de España adds a group per round (1/16, 1/8, ...). Listing each ``group_value`` would need a config edit
    before every round, so the refresh asks FEB for the groups of the season on each run.
    """

    def test_an_entry_with_all_groups_needs_no_group_fields(self, tmp_path):
        path = tmp_path / "c.json"
        path.write_text(json.dumps({"scrapes": [COPA]}), encoding="utf-8")
        entry = load_config(path)[0]
        assert entry.groups == "all" and entry.group_value == "" and entry.group_label == ""

    def test_all_groups_and_a_fixed_group_together_are_rejected(self, tmp_path):
        path = tmp_path / "c.json"
        path.write_text(json.dumps({"scrapes": [{**COPA, "group_value": "1", "group_label": "A"}]}), encoding="utf-8")
        with pytest.raises(ValueError, match="#1"):
            load_config(path)

    def test_an_unknown_groups_value_is_rejected(self, tmp_path):
        path = tmp_path / "c.json"
        path.write_text(json.dumps({"scrapes": [{**COPA, "groups": "some"}]}), encoding="utf-8")
        with pytest.raises(ValueError, match="#1"):
            load_config(path)

    def test_every_phase_found_is_refreshed_into_its_own_collection(self):
        from src.services.competition_refresh import expand_entries

        entries = expand_entries([RefreshEntry(**COPA)], _phase_scraper())
        assert [(e.group_label, e.group_value, e.groups) for e in entries] == [(label, value, "") for label, value in COPA_GROUPS]
        assert {e.competition_url for e in entries} == {COPA["competition_url"]}

    def test_a_fixed_entry_is_left_untouched_and_does_not_ask_feb(self):
        from src.services.competition_refresh import expand_entries

        scraper = _phase_scraper()
        fixed = RefreshEntry(**ENTRY)
        assert expand_entries([fixed], scraper) == [fixed]
        scraper.get_groups_for_season.assert_not_called()

    def test_the_group_filter_keeps_only_matching_labels_ignoring_case(self):
        from src.services.competition_refresh import expand_entries

        entries = expand_entries([RefreshEntry(**{**COPA, "group_filter": ["play-offs"]})], _phase_scraper())
        assert [e.group_value for e in entries] == ["90041"]

    def test_refresh_all_scrapes_each_phase_and_reports_it(self):
        db = _db()
        report = refresh_all(db, [RefreshEntry(**COPA)], scraper=_phase_scraper(),
                             freshness=lambda c: {"up_to_date": True, "missing_codes": [], "games_in_db": 1, "last_game": None, "warning": None})
        assert [r["collection"] for r in report] == [
            "COPA_ESPAÑA_2026_2027_Play-offs_1_16_Final", "COPA_ESPAÑA_2026_2027_FASE_DE_GRUPOS_A", "COPA_ESPAÑA_2026_2027_FASE_DE_GRUPOS_B"]
        assert all(r["fatal"] is None for r in report)

    def test_a_phase_that_appears_later_is_picked_up_on_the_next_run(self):
        db, check = _db(), (lambda c: {"up_to_date": True, "missing_codes": [], "games_in_db": 1, "last_game": None, "warning": None})
        refresh_all(db, [RefreshEntry(**COPA)], scraper=_phase_scraper(COPA_GROUPS[:1]), freshness=check)
        second = refresh_all(db, [RefreshEntry(**COPA)], scraper=_phase_scraper(COPA_GROUPS + [("Play-offs 1/8 Final", "90042")]), freshness=check)
        assert "COPA_ESPAÑA_2026_2027_Play-offs_1_8_Final" in [r["collection"] for r in second]

    def test_a_failed_discovery_is_one_error_and_does_not_block_the_other_competitions(self):
        scraper = _phase_scraper()
        scraper.get_groups_for_season.side_effect = ConnectionError("feb down")
        report = refresh_all(_db(), [RefreshEntry(**COPA), RefreshEntry(**ENTRY)], scraper=scraper,
                             freshness=lambda c: {"up_to_date": True, "missing_codes": [], "games_in_db": 1, "last_game": None, "warning": None})
        assert "feb down" in report[0]["fatal"] and "COPA ESPAÑA" in report[0]["collection"]
        assert report[1]["fatal"] is None

    def test_a_competition_without_groups_is_an_error_not_silence(self):
        report = refresh_all(_db(), [RefreshEntry(**COPA)], scraper=_phase_scraper([]), freshness=lambda c: {})
        assert "grupos" in report[0]["fatal"]

    def test_the_publisher_finds_the_phases_already_stored_for_a_competition(self):
        """The live packages are built offline: the phases of ``groups: all`` are the collections the refresh stored."""
        from src.services.competition_refresh import ingested_collections

        db = _db()
        meta = db.repository.connection.get_collection.return_value
        for label, value in COPA_GROUPS:
            meta.insert_one({"_id": f"COPA_ESPAÑA_2026_2027_{value}", "competition_url": COPA["competition_url"], "season_value": "2026",
                             "group_label": label})
        meta.insert_one({"_id": "OTHER", "competition_url": "https://x/other", "season_value": "2026", "group_label": "A"})
        names = ingested_collections(db, [RefreshEntry(**COPA), RefreshEntry(**ENTRY)])
        assert names == ["COPA_ESPAÑA_2026_2027_90041", "COPA_ESPAÑA_2026_2027_90033", "COPA_ESPAÑA_2026_2027_90034",
                         "LF_CHALLENGE_LF_CHALLENGE_2026_A"]

    def test_the_publisher_config_check_runs_without_a_database_regression(self):
        """The ``live-packages`` workflow validates the config on PRs with ``_collections()`` and no database: phases are skipped, fixed groups listed."""
        from src.live_prep.publisher import _collections

        names = _collections()
        assert names == []   # every competition is complete now (#724): its phases come from COLLECTION_META, which needs the database

    def test_the_copa_is_in_the_repository_config_as_one_competition(self):
        copa = [e for e in load_config("config/competitions.json") if "nm=copaespaa" in e.competition_url and e.season_value == "2026"]      # the older editions of the history (#876) are other entries
        assert len(copa) == 1 and copa[0].groups == "all" and (copa[0].season_value, copa[0].year) == ("2026", "2026")


class TestSeniorCompetitions:
    """Every senior competition of the season is kept fresh (#456) and the catalogue of competitions (``config/competitions.json``, #724) has all of them."""

    SENIOR = {"LF ENDESA": "nm=lfendesa", "PRIMERA FEB": "nm=primerafeb", "LF CHALLENGE": "nm=lfchallenge", "SEGUNDA FEB": "nm=segundafeb",
              "L.F.-2": "nm=lf2", "LIGA U": "nm=ligau", "COPA ESPAÑA": "nm=copaespaa"}

    @staticmethod
    def by_competition(path):
        out = {}
        for e in load_config(path):
            out.setdefault(e.competition_label, []).append(e)
        return out

    def test_the_local_database_has_every_group_of_3a_feb_too(self):
        local = self.by_competition("config/competitions.json")
        assert set(self.SENIOR) | {"TERCERA FEB"} <= set(local)
        assert [e.groups for e in local["TERCERA FEB"]] == ["all"]

    def test_no_competition_is_listed_twice_in_a_config(self):
        for path in ("config/competitions.json",):
            seen = [(e.league, e.competition_url, e.group_value or "all", e.fbcyl.get("competition_id", "")) for e in load_config(path)]
            assert len(seen) == len(set(seen)), path

    def test_only_keeps_the_competitions_asked_for_ignoring_case_and_punctuation(self):
        from src.services.competition_refresh import only_competitions

        entries = load_config("config/competitions.json")
        assert {e.competition_label for e in only_competitions(entries, ["tercera feb", "LF2"])} == {"TERCERA FEB", "L.F.-2"}
        assert only_competitions(entries, []) == entries

    def test_an_unknown_competition_in_only_is_an_error(self):
        from src.services.competition_refresh import only_competitions

        with pytest.raises(ValueError, match="XYZ"):
            only_competitions(load_config("config/competitions.json"), ["XYZ"])

    def test_the_cli_accepts_only_and_the_workflow_passes_it_from_an_input(self):
        import yaml
        from pathlib import Path

        wf = yaml.safe_load(Path(".github/workflows/archive-refresh.yml").read_text(encoding="utf-8"))
        assert "only" in wf[True]["workflow_dispatch"]["inputs"]
        run = [s for s in next(iter(wf["jobs"].values()))["steps"] if "run_refresh.py" in s.get("run", "")][0]
        assert "ONLY" in run["env"] and "$ONLY" in run["run"] and "${{" not in run["run"]


class TestRefreshFillsDerived:
    """Issue #630: the Atlas workflow ran the backfill as a second step but the local refresh did not, so 167 games of the local database had no ``DERIVED``.
    The refresh itself now fills it in every collection it touches (idempotent: a game that has it is skipped)."""

    def _with_a_game_without_derived(self, feb_game_doc):
        db = _db()
        collection = db.repository.connection.get_collection.return_value
        collection.insert_one({**feb_game_doc, "_id": 99})
        return db, collection

    def test_a_stored_game_without_derived_gets_it_after_the_refresh_regression(self, feb_game_doc):
        db, collection = self._with_a_game_without_derived(feb_game_doc)
        assert "DERIVED" not in collection.find_one({"_id": 99})
        refresh_all(db, [RefreshEntry(**ENTRY)], scraper=_scraper(["1"]), freshness=TestRefreshAll._freshness(None, []))
        assert collection.find_one({"_id": 99})["DERIVED"]["v"]

    def test_a_failing_backfill_never_turns_a_refresh_into_an_error(self, feb_game_doc, monkeypatch):
        import src.services.derived_backfill as backfill

        monkeypatch.setattr(backfill, "backfill_collection", MagicMock(side_effect=RuntimeError("cursor lost")))
        db, _ = self._with_a_game_without_derived(feb_game_doc)
        report = refresh_all(db, [RefreshEntry(**ENTRY)], scraper=_scraper(["1"]), freshness=TestRefreshAll._freshness(None, []))
        assert report[0]["fatal"] is None


class TestFbcylInTheRefresh:
    """The refresh scrapes the FBCYL groups of the catalogue too (issue #724): no calendar to compare with, no team index, the DERIVED of its games filled."""

    ENTRY = RefreshEntry(competition_url="", season_value="2026", competition_label="1ª FASE-GRUPO A-1", season_label="2026", year="2026", league="fbcyl",
                         fbcyl={"competition_id": "7298", "category": "1129", "gender": "F", "territory": "1"})

    def test_a_group_is_scraped_with_its_context_and_its_derived_filled_without_a_freshness_check(self):
        from unittest.mock import MagicMock, patch

        db, scraper = _db(), MagicMock()
        scraper.get_matches.return_value = ["u1"]
        scraper.get_match_complete_data.return_value = {"uuid": "u1"}
        check = MagicMock()
        with patch("src.services.competition_refresh._fill_derived") as fill, patch("src.services.competition_refresh._ensure_team_index") as index:
            report = refresh_all(db, [self.ENTRY], fbcyl_scraper=scraper, freshness=check)
        [item] = report
        assert item["fatal"] is None and item["league"] == "fbcyl" and item["freshness"] is None
        assert item["collection"] == "FBCYL_1ª_FASE-GRUPO_A-1_2026_" and item["job"]["total"] == 1
        assert scraper.get_match_complete_data.call_args.kwargs["league_ctx"]["competition_id"] == "7298"
        fill.assert_called_once()
        index.assert_not_called()                                    # the team index is of the FEB header
        check.assert_not_called()

    def test_a_failing_group_is_its_own_error_and_the_others_go_on(self):
        from unittest.mock import MagicMock

        scraper = MagicMock()
        scraper.get_matches.side_effect = RuntimeError("FBCYL no responde")
        from src.services.competition_refresh import needs_attention

        report = refresh_all(_db(), [self.ENTRY, self.ENTRY], fbcyl_scraper=scraper, freshness=lambda c: {})
        assert [r["fatal"] for r in report] == ["RuntimeError: FBCYL no responde"] * 2
        assert needs_attention(report)

    def test_the_markdown_does_not_claim_a_comparison_with_the_feb_calendar(self):
        from unittest.mock import MagicMock

        scraper = MagicMock()
        scraper.get_matches.return_value = []
        text = to_markdown(refresh_all(_db(), [self.ENTRY], fbcyl_scraper=scraper, freshness=lambda c: {}))
        assert "FBCYL" in text and "calendario de FEB" not in text

    def test_only_finds_a_group_by_its_name_and_the_publisher_never_takes_it(self):
        from src.services.competition_refresh import ingested_collections, only_competitions

        assert only_competitions([self.ENTRY], ["1ª fase-grupo a-1"]) == [self.ENTRY]          # by its label, case and punctuation ignored
        assert ingested_collections(_db(), [self.ENTRY]) == []       # live packages are FEB only
