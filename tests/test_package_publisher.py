"""Scheduled publication of the live preparation packages to the ``live-packages`` branch (issue #175).

For every upcoming match of the club an encrypted package against that rival is built and written to
``<out>/<team_id>/<rival_id>.bpkg`` together with an ``index.json`` the app reads.
"""
import json
from unittest.mock import MagicMock

import pytest

from src.live_prep.package_crypto import decrypt_package
from src.live_prep.publisher import build_index, load_config, main, publish_all

OWN, R1, R2 = "1008631", "2001", "2002"
PASSWORD = "clave-larga-de-prueba"


def _match(code, rival, start, rnd=1, home=True):
    own = {"id": OWN, "name": "ADBA"}
    other = {"id": rival, "name": f"RIVAL {rival}"}
    return {"code": code, "start": start, "round": rnd, "home": own if home else other,
            "away": other if home else own, "opponent": other, "status": "scheduled", "is_home": home}


def _schedule(matches, warning=None):
    service = MagicMock()
    service.upcoming.return_value = {"matches": matches, "calendar_url": "u", "warning": warning}
    return service


def _builder(calls=None):
    def build(db, collection, team_id, rival_id, season=None, competition_meta=None, progress=None):
        if calls is not None:
            calls.append((collection, team_id, rival_id, competition_meta))
        package = MagicMock()
        package.dumps.return_value = json.dumps({"team": team_id, "rival": rival_id})
        return package
    return build


class TestPublishAll:
    def test_writes_one_decryptable_package_per_upcoming_rival_and_an_index(self, tmp_path):
        service = _schedule([_match("10", R1, "2026-10-10T17:00"), _match("11", R2, "2026-10-17T17:00", 2, False)])
        calls = []
        entries = publish_all(object(), tmp_path, PASSWORD, ["COL"], OWN, service=service, build=_builder(calls))
        assert [c[2] for c in calls] == [R1, R2]
        assert calls[0][3] == {"match": {"code": "10", "start": "2026-10-10T17:00", "round": 1,
                                         "home": {"id": OWN, "name": "ADBA"}, "away": {"id": R1, "name": f"RIVAL {R1}"}}}
        envelope = json.loads((tmp_path / OWN / f"{R1}.bpkg").read_text(encoding="utf-8"))
        assert json.loads(decrypt_package(envelope, PASSWORD)) == {"team": OWN, "rival": R1}
        index = json.loads((tmp_path / "index.json").read_text(encoding="utf-8"))
        assert [e["rival_id"] for e in index["packages"]] == [R1, R2]
        assert index["packages"][0]["file"] == f"{OWN}/{R1}.bpkg" and len(index["packages"][0]["sha256"]) == 64
        assert entries == index["packages"]

    def test_a_rival_with_two_upcoming_matches_gets_one_package_for_the_nearest(self, tmp_path):
        service = _schedule([_match("10", R1, "2026-10-10T17:00"), _match("12", R1, "2026-11-10T17:00", 5)])
        calls = []
        publish_all(object(), tmp_path, PASSWORD, ["COL"], OWN, service=service, build=_builder(calls))
        assert len(calls) == 1 and calls[0][3]["match"]["code"] == "10"

    def test_only_the_next_n_matches_are_published(self, tmp_path):
        matches = [_match(str(i), str(3000 + i), f"2026-10-{10 + i}T17:00") for i in range(5)]
        publish_all(object(), tmp_path, PASSWORD, ["COL"], OWN, service=_schedule(matches), build=_builder(), upcoming=2)
        assert len(json.loads((tmp_path / "index.json").read_text(encoding="utf-8"))["packages"]) == 2

    def test_a_failing_rival_is_skipped_and_reported_without_blocking_the_rest(self, tmp_path):
        good = _builder()

        def build(db, collection, team_id, rival_id, **kw):
            if rival_id == R1:
                raise ValueError("sin partidos del rival")
            return good(db, collection, team_id, rival_id, **kw)

        errors = []
        entries = publish_all(object(), tmp_path, PASSWORD, ["COL"], OWN,
                              service=_schedule([_match("10", R1, "2026-10-10T17:00"), _match("11", R2, "2026-10-17T17:00")]),
                              build=build, errors=errors)
        assert [e["rival_id"] for e in entries] == [R2]
        assert len(errors) == 1 and R1 in errors[0]

    def test_no_upcoming_matches_still_writes_an_empty_index(self, tmp_path):
        assert publish_all(object(), tmp_path, PASSWORD, ["COL"], OWN, service=_schedule([], "sin calendario"),
                           build=_builder()) == []
        assert json.loads((tmp_path / "index.json").read_text(encoding="utf-8"))["packages"] == []

    def test_stale_packages_of_a_previous_run_are_removed(self, tmp_path):
        old = tmp_path / OWN / "9999.bpkg"
        old.parent.mkdir(parents=True)
        old.write_text("old", encoding="utf-8")
        publish_all(object(), tmp_path, PASSWORD, ["COL"], OWN,
                    service=_schedule([_match("10", R1, "2026-10-10T17:00")]), build=_builder())
        assert not old.exists() and (tmp_path / OWN / f"{R1}.bpkg").exists()


class TestIndex:
    def test_index_carries_the_fields_the_app_lists(self):
        entry = {"team_id": OWN, "rival_id": R1, "rival": "X", "match": {"code": "1", "start": "s", "round": 1}, "file": "f", "sha256": "h"}
        index = build_index([entry], now="2026-10-09T12:00:00+00:00")
        assert index == {"v": 1, "generated_at": "2026-10-09T12:00:00+00:00", "packages": [entry]}


class TestConfigAndCli:
    def test_config_lists_the_club_and_how_many_matches_to_prepare(self, tmp_path):
        path = tmp_path / "c.json"
        path.write_text(json.dumps({"team_id": OWN, "upcoming": 3}), encoding="utf-8")
        assert load_config(path) == {"team_id": OWN, "upcoming": 3}

    def test_config_without_team_is_rejected(self, tmp_path):
        path = tmp_path / "c.json"
        path.write_text("{}", encoding="utf-8")
        with pytest.raises(ValueError, match="team_id"):
            load_config(path)

    def test_the_repository_config_is_valid(self):
        assert load_config()["team_id"]

    def test_cli_requires_the_password_and_the_connection(self, monkeypatch, tmp_path):
        monkeypatch.delenv("PACKAGE_PASSWORD", raising=False)
        assert main(["--out", str(tmp_path)]) == 2
        monkeypatch.setenv("PACKAGE_PASSWORD", "corta")
        assert main(["--out", str(tmp_path)]) == 2

    def test_importing_the_cli_does_not_need_a_database(self):
        import run_package_publish  # noqa: F401
