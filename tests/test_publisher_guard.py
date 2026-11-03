"""The live packages are never published from a database that lacks the phases of a competition (issue #724).

The phases of a ``groups: all`` competition are known from ``COLLECTION_META`` (what the FEB scrape wrote). The first refresh that seeded it into the archive was a partial one
(``only: tercera feb``) and the packages that followed were built from 10 groups: 3 packages instead of 12 and the rounds of one competition instead of eight, silently replacing
the complete publication. A competition of the catalogue with no phases known is now an error that stops the publication BEFORE anything is written, so the branch keeps the previous
packages until a complete refresh has run.
"""
import json
from unittest.mock import MagicMock, patch

from db_helpers import new_mock_db

from src.live_prep import publisher
from src.live_prep.publisher import competitions_without_phases
from src.services.competition_catalogue import load_catalogue, package_entries

TERCERA = "https://baloncestoenvivo.feb.es/calendario.aspx?g=3&t=2026&nm=tercerafeb"
PRIMERA = "https://baloncestoenvivo.feb.es/calendario.aspx?g=1&t=2026&nm=primerafeb"


def _entry(competition, url, **over):
    return {"competition": competition, "competition_url": url, "season_label": "2026/2027", "season_value": "2026", "year": "2026", "groups": "all", **over}


def _db(*metas):
    meta = new_mock_db("b")["COLLECTION_META"]
    for i, (url, label) in enumerate(metas):
        meta.insert_one({"_id": f"COL_{i}", "competition_url": url, "season_value": "2026", "group_label": label})
    db = MagicMock()
    db.repository.connection.get_collection.return_value = meta
    return db


def _entries(tmp_path, *entries):
    path = tmp_path / "competitions.json"
    path.write_text(json.dumps({"competitions": list(entries)}), encoding="utf-8")
    return package_entries(load_catalogue(path))


class TestCompetitionsWithoutPhases:
    def test_a_competition_with_no_metadata_is_reported_and_one_with_it_is_not(self, tmp_path):
        entries = _entries(tmp_path, _entry("TERCERA FEB", TERCERA), _entry("PRIMERA FEB", PRIMERA))
        assert competitions_without_phases(_db((TERCERA, "A-A"), (TERCERA, "A-B")), entries) == ["PRIMERA FEB"]
        assert competitions_without_phases(_db((TERCERA, "A-A"), (PRIMERA, "Liga Regular")), entries) == []

    def test_a_single_group_names_its_collection_so_it_never_lacks_phases(self, tmp_path):
        single = _entry("TERCERA FEB", TERCERA, groups="", group_value="90060", group_label='Liga Regular "A-B"')
        assert competitions_without_phases(_db(), _entries(tmp_path, single)) == []

    def test_a_group_filter_that_leaves_no_phase_counts_as_lacking(self, tmp_path):
        entries = _entries(tmp_path, _entry("TERCERA FEB", TERCERA, packages_groups=["A-B"]))
        assert competitions_without_phases(_db((TERCERA, "B-B")), entries) == ["TERCERA FEB"]
        assert competitions_without_phases(_db((TERCERA, "A-B")), entries) == []

    def test_the_real_catalogue_needs_every_active_feb_competition(self):
        entries = package_entries(load_catalogue("config/competitions.json"))
        assert len(competitions_without_phases(_db((TERCERA, "A-A")), entries)) == len(entries) - 1     # only 3a FEB is known: the other seven are missing
        assert competitions_without_phases(_db(), []) == []


class TestThePublicationStopsBeforeWritingAnything:
    def _run(self, tmp_path, monkeypatch, db, mkdir=False):
        monkeypatch.setenv("MONGODB_CONNECTION_STRING", "mongodb://localhost:27017")
        monkeypatch.setenv("PACKAGE_PASSWORD", "a-long-enough-password")
        out = tmp_path / "packages-out"
        with patch("src.database.MongoDBHandler", return_value=db), patch.object(publisher, "publish_all") as publish, \
                patch.object(publisher, "publish_round_bundles") as rounds:
            publish.return_value, rounds.return_value = [], []
            if mkdir:
                out.mkdir()                                                            # what publish_all does before it writes (it is patched here)
            code = publisher.main(["--out", str(out)])
        return code, out, publish, rounds

    def test_a_database_that_knows_only_one_competition_stops_with_a_clear_error_and_writes_nothing(self, tmp_path, monkeypatch, capsys):
        code, out, publish, rounds = self._run(tmp_path, monkeypatch, _db((TERCERA, "A-A")))
        assert code == 3
        err = capsys.readouterr().err
        assert "PRIMERA FEB" in err and "COLLECTION_META" in err and "refresh" in err.lower()
        assert not out.exists()                                                       # nothing for the workflow to publish: the branch keeps the previous packages
        publish.assert_not_called()
        rounds.assert_not_called()

    def test_with_the_phases_of_every_competition_it_goes_on(self, tmp_path, monkeypatch):
        entries = package_entries(load_catalogue("config/competitions.json"))
        metas = [(e.competition_url, "Liga Regular") for e in entries]
        code, _, publish, _ = self._run(tmp_path, monkeypatch, _db(*metas), mkdir=True)
        assert code == 0
        publish.assert_called_once()
