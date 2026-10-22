"""Structured competition data in the published index (issue #438, epic #435).

The app labelled and filtered the matches parsing the name of the collection. The publisher now writes ``competition: {key, label,
competition, group, season, level, gender}`` in every entry of ``rounds[]`` and ``packages[]`` (additive: an app that predates it ignores it)
and prepares the packages of every club listed for a competition, not just one club for all of them.
"""
import json
from unittest.mock import MagicMock

import pytest
from db_helpers import new_mock_db

from src.live_prep.competition_info import competition_infos, normalize_catalog, public
from src.live_prep.package_crypto import decrypt_package
from src.live_prep.publisher import load_config, publish_all, publish_round_bundles
from tests.test_package_publisher import OWN, PASSWORD, R1, _builder, _match, _round, _round_builder, _round_service, _schedule

SEGUNDA = "SEGUNDA_FEB_2026_2027_Liga_Regular_A"
CATALOG = [{"competition": "SEGUNDA FEB", "level": 3, "gender": "M", "clubs": ["1008857", "1008978"]},
           {"competition": "COPA ESPAÑA", "gender": "M"}]


def _db(*docs):
    metas = new_mock_db()["COLLECTION_META"]
    for doc in docs:
        metas.insert_one(doc)
    db = MagicMock()
    db.repository.connection.get_collection.return_value = metas
    return db


META = {"_id": SEGUNDA, "competition_label": "SEGUNDA FEB", "season_label": "2026/2027", "group_label": 'Liga Regular "A"'}


class TestInfo:
    def test_the_data_comes_from_the_scrape_metadata_and_the_catalog(self):
        info = competition_infos(_db(META), [SEGUNDA], normalize_catalog(CATALOG), ["1008631"])[SEGUNDA]
        assert info == {"key": SEGUNDA, "label": 'SEGUNDA FEB · Liga Regular "A"', "competition": "SEGUNDA FEB", "group": 'Liga Regular "A"',
                        "season": "2026/2027", "level": 3, "gender": "M", "clubs": ["1008857", "1008978"], "rule_config": {"gender": "M"}}

    def test_a_competition_not_in_the_catalog_keeps_the_default_club_and_no_level(self):
        meta = {**META, "_id": "X", "competition_label": "LF CHALLENGE"}
        info = competition_infos(_db(meta), ["X"], normalize_catalog(CATALOG), ["1008631"])["X"]
        assert info["clubs"] == ["1008631"] and info["level"] is None and info["gender"] is None

    def test_the_catalog_matches_the_competition_ignoring_case_and_punctuation(self):
        meta = {**META, "_id": "X", "competition_label": "L.F.-2"}
        info = competition_infos(_db(meta), ["X"], normalize_catalog([{"competition": "lf2", "level": 3, "gender": "F"}]), ["1"])["X"]
        assert (info["level"], info["gender"]) == (3, "F")

    def test_a_collection_without_metadata_is_labelled_with_its_name(self):
        info = competition_infos(_db(), ["ALGO_2026"], normalize_catalog([]), ["1"])["ALGO_2026"]
        assert (info["key"], info["label"], info["competition"], info["group"]) == ("ALGO_2026", "ALGO_2026", "ALGO_2026", "")

    def test_a_database_that_fails_reading_the_metadata_does_not_stop_the_publication(self):
        db = MagicMock()
        db.repository.connection.get_collection.side_effect = RuntimeError("down")
        assert competition_infos(db, ["A"], normalize_catalog([]), ["1"])["A"]["key"] == "A"

    def test_the_published_form_has_no_clubs(self):
        info = competition_infos(_db(META), [SEGUNDA], normalize_catalog(CATALOG), ["1"])[SEGUNDA]
        assert "clubs" not in public(info) and public(info)["level"] == 3


class TestCatalog:
    def test_the_config_accepts_a_catalog_and_defaults_to_none(self, tmp_path):
        path = tmp_path / "c.json"
        path.write_text(json.dumps({"team_id": OWN, "competitions": CATALOG}), encoding="utf-8")
        assert load_config(path)["competitions"] == normalize_catalog(CATALOG)
        path.write_text(json.dumps({"team_id": OWN}), encoding="utf-8")
        assert load_config(path)["competitions"] == []

    @pytest.mark.parametrize("bad", [{"level": 1}, {"competition": "X", "gender": "Z"}, {"competition": "X", "level": "uno"},
                                     {"competition": "X", "clubs": "1008857"}])
    def test_an_invalid_entry_is_rejected(self, tmp_path, bad):
        path = tmp_path / "c.json"
        path.write_text(json.dumps({"team_id": OWN, "competitions": [bad]}), encoding="utf-8")
        with pytest.raises(ValueError, match="competitions"):
            load_config(path)

    def test_the_repository_catalog_covers_every_senior_competition_with_its_clubs(self):
        catalog = {c["competition"]: c for c in load_config()["competitions"]}
        assert {"LF ENDESA", "PRIMERA FEB", "LF CHALLENGE", "SEGUNDA FEB", "L.F.-2", "TERCERA FEB", "COPA ESPAÑA"} <= set(catalog)
        assert {"1008857", "1008978"} <= set(catalog["SEGUNDA FEB"]["clubs"]) and "1010490" in catalog["TERCERA FEB"]["clubs"]
        assert {"1008857", "1008978", "1010490"} <= set(catalog["COPA ESPAÑA"]["clubs"])
        assert catalog["LF CHALLENGE"]["gender"] == "F" and catalog["SEGUNDA FEB"]["gender"] == "M"


class TestPublishedIndex:
    INFO = {"key": "COL", "label": "X · A", "competition": "X", "group": "A", "season": "2026/2027", "level": 3, "gender": "M", "clubs": [OWN]}

    def test_a_round_entry_carries_the_competition_without_clubs(self, tmp_path):
        service = _round_service({"COL": _round(4, (OWN, R1))})
        entries = publish_round_bundles(object(), tmp_path, PASSWORD, ["COL"], OWN, service=service, build=_round_builder([]),
                                        competitions={"COL": self.INFO})
        assert entries[0]["competition"] == public(self.INFO) and "clubs" not in entries[0]["competition"]

    def test_without_competition_data_the_entry_is_what_it_was(self, tmp_path):
        service = _round_service({"COL": _round(4, (OWN, R1))})
        entries = publish_round_bundles(object(), tmp_path, PASSWORD, ["COL"], OWN, service=service, build=_round_builder([]))
        assert "competition" not in entries[0]

    def test_a_package_entry_carries_the_competition(self, tmp_path):
        service = _schedule([_match("10", R1, "2026-10-10T17:00")])
        entries = publish_all(object(), tmp_path, PASSWORD, ["COL"], OWN, service=service, build=_builder(), competitions={"COL": self.INFO})
        assert entries[0]["competition"] == public(self.INFO)

    def test_each_club_of_a_competition_gets_the_packages_of_its_rivals(self, tmp_path):
        """2ª FEB A and B have different clubs of interest: the clubs of each collection, not one for all."""
        asked, calls = [], []
        service = MagicMock()

        def upcoming(collection, team_id, limit):
            asked.append((collection, team_id))
            return {"matches": [{**_match("10", R1, "2026-10-10T17:00"), "opponent": {"id": f"r{team_id}", "name": "R"}}],
                    "calendar_url": "u", "warning": None}

        service.upcoming.side_effect = upcoming
        info = {**self.INFO, "clubs": ["c1", "c2"]}
        entries = publish_all(object(), tmp_path, PASSWORD, ["COL"], OWN, service=service, build=_builder(calls), competitions={"COL": info})
        assert asked == [("COL", "c1"), ("COL", "c2")]
        assert [(e["team_id"], e["file"]) for e in entries] == [("c1", "c1/rc1.bpkg"), ("c2", "c2/rc2.bpkg")]
        assert all((tmp_path / e["file"]).exists() for e in entries)

    def test_the_package_of_a_club_is_sealed_for_that_club(self, tmp_path):
        info = {**self.INFO, "clubs": ["c1"]}
        service = _schedule([_match("10", R1, "2026-10-10T17:00")])
        entries = publish_all(object(), tmp_path, PASSWORD, ["COL"], OWN, service=service, build=_builder(), competitions={"COL": info})
        envelope = json.loads((tmp_path / entries[0]["file"]).read_text(encoding="utf-8"))
        assert json.loads(decrypt_package(envelope, PASSWORD))["team"] == "c1"

    def test_the_rounds_still_mark_the_club_of_the_config(self, tmp_path):
        service = _round_service({"COL": _round(4, (OWN, R1))})
        entries = publish_round_bundles(object(), tmp_path, PASSWORD, ["COL"], OWN, service=service, build=_round_builder([]),
                                        competitions={"COL": self.INFO})
        assert entries[0]["club"] is True

    def test_the_stale_packages_of_a_club_with_no_rival_now_are_removed_regression(self, tmp_path):
        """A club listed for the competition whose matches ran out must not keep last week's package (one directory per club)."""
        old = tmp_path / "c2" / "9999.bpkg"
        old.parent.mkdir(parents=True)
        old.write_text("old", encoding="utf-8")
        info = {**self.INFO, "clubs": ["c1", "c2"]}
        service = MagicMock()
        service.upcoming.side_effect = lambda collection, team_id, limit: {
            "matches": [_match("10", R1, "2026-10-10T17:00")] if team_id == "c1" else [], "calendar_url": "u", "warning": None}
        publish_all(object(), tmp_path, PASSWORD, ["COL"], OWN, service=service, build=_builder(), competitions={"COL": info})
        assert not old.exists()
