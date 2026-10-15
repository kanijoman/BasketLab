"""Scheduled publication of the live preparation packages to the ``live-packages`` branch (issue #175).

For every upcoming match of the club an encrypted package against that rival is built and written to
``<out>/<team_id>/<rival_id>.bpkg`` together with an ``index.json`` the app reads.
"""
import json
from unittest.mock import MagicMock

import pytest

from src.live_prep.package_crypto import decrypt_package
from src.live_prep.publisher import build_index, load_config, main, publish_all, publish_round_bundles

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


def _round_service(rounds):
    """``rounds``: collection -> the answer of next_round (a dict) or an exception to raise."""
    service = MagicMock()

    def next_round(collection):
        answer = rounds[collection]
        if isinstance(answer, Exception):
            raise answer
        return answer

    service.next_round.side_effect = next_round
    return service


def _round(rnd, *pairs):
    return {"round": rnd, "calendar_url": "u", "warning": None, "matches": [
        {"code": str(i), "start": "2026-10-17T17:00", "round": rnd, "home": {"id": h, "name": f"EQ {h}"}, "away": {"id": a, "name": f"EQ {a}"}}
        for i, (h, a) in enumerate(pairs, 1)]}


def _round_builder(calls):
    def build(db, collection, matches, club_team_id=None, roster_source=None, season=None):
        calls.append((collection, [m["code"] for m in matches], club_team_id))
        package = MagicMock()
        package.dumps.return_value = json.dumps({"c": collection})
        return [{"match": {k: m[k] for k in ("code", "start", "round", "home", "away")}, "own_id": m["home"]["id"],
                 "rival_id": m["away"]["id"], "is_club": OWN in (m["home"]["id"], m["away"]["id"]), "package": package} for m in matches]
    return build


class TestPublishRoundBundles:
    """One bundle per competition with the whole next round (issues #286, #172)."""

    def test_one_bundle_per_competition_with_every_match_of_its_next_round(self, tmp_path):
        service = _round_service({"A": _round(4, (OWN, R1), (R2, "3003")), "B": _round(9, ("5001", "5002"))})
        calls = []
        entries = publish_round_bundles(object(), tmp_path, PASSWORD, ["A", "B"], OWN, service=service, build=_round_builder(calls))
        assert calls == [("A", ["1", "2"], OWN), ("B", ["1"], OWN)]
        assert [(e["collection"], e["round"], e["club"], len(e["matches"])) for e in entries] == [("A", 4, True, 2), ("B", 9, False, 1)]
        assert all((tmp_path / e["file"]).exists() for e in entries)

    def test_a_competition_without_matches_to_play_gets_no_bundle(self, tmp_path):
        service = _round_service({"A": {"round": None, "matches": [], "calendar_url": None, "warning": "sin calendario"}})
        assert publish_round_bundles(object(), tmp_path, PASSWORD, ["A"], OWN, service=service, build=_round_builder([])) == []

    def test_a_failing_competition_is_reported_and_the_others_still_go(self, tmp_path):
        service = _round_service({"A": _round(1, (OWN, R1)), "B": _round(2, ("5001", "5002"))})

        def build(db, collection, matches, **kw):
            if collection == "A":
                raise MemoryError("sin memoria")
            return _round_builder([])(db, collection, matches, **kw)

        errors = []
        entries = publish_round_bundles(object(), tmp_path, PASSWORD, ["A", "B"], OWN, service=service, build=build, errors=errors)
        assert [e["collection"] for e in entries] == ["B"] and "A" in errors[0] and "MemoryError" in errors[0]

    def test_a_calendar_that_raises_is_a_reported_error_not_a_crash(self, tmp_path):
        service = _round_service({"A": ConnectionError("feb down")})
        errors = []
        assert publish_round_bundles(object(), tmp_path, PASSWORD, ["A"], OWN, service=service, build=_round_builder([]), errors=errors) == []
        assert "A" in errors[0] and "feb down" in errors[0]

    def test_stale_bundles_of_a_previous_run_are_removed(self, tmp_path):
        (tmp_path / "rounds").mkdir()
        (tmp_path / "rounds" / "OLD__r1.bpkgz").write_text("x", encoding="utf-8")
        publish_round_bundles(object(), tmp_path, PASSWORD, ["A"], OWN, service=_round_service({"A": _round(1, (OWN, R1))}), build=_round_builder([]))
        assert not (tmp_path / "rounds" / "OLD__r1.bpkgz").exists()

    def test_the_index_lists_the_rounds_and_the_club_without_changing_the_old_fields(self):
        entry = {"collection": "A", "round": 4, "file": "rounds/A__r4.bpkgz", "sha256": "h", "bytes": 5, "club": True, "matches": []}
        index = build_index([], rounds=[entry], club_team_id=OWN, now="2026-10-09T12:00:00+00:00")
        assert index == {"v": 1, "generated_at": "2026-10-09T12:00:00+00:00", "packages": [], "rounds": [entry], "club_team_id": OWN}
        assert "rounds" not in build_index([], now="n"), "without rounds the index is what it was"


class TestVercelGuard:
    def test_the_published_branch_tells_vercel_not_to_deploy_it_regression(self, tmp_path):
        """Bug: Vercel's Git integration built the live-packages branch on every publish and failed
        ('Root Directory "frontend" does not exist'), mailing the owner 3 times a day.
        The branch carries frontend/vercel.json (so the root directory exists) that disables its deployments."""
        publish_all(object(), tmp_path, PASSWORD, ["COL"], OWN, service=_schedule([]), build=_builder())
        config = json.loads((tmp_path / "frontend" / "vercel.json").read_text(encoding="utf-8"))
        assert config["git"]["deploymentEnabled"] is False


class TestIndex:
    def test_index_carries_the_fields_the_app_lists(self):
        entry = {"team_id": OWN, "rival_id": R1, "rival": "X", "match": {"code": "1", "start": "s", "round": 1}, "file": "f", "sha256": "h"}
        index = build_index([entry], now="2026-10-09T12:00:00+00:00")
        assert index == {"v": 1, "generated_at": "2026-10-09T12:00:00+00:00", "packages": [entry]}


class TestConfigAndCli:
    def test_config_lists_the_club_and_how_many_matches_to_prepare(self, tmp_path):
        path = tmp_path / "c.json"
        path.write_text(json.dumps({"team_id": OWN, "upcoming": 3}), encoding="utf-8")
        assert load_config(path) == {"team_id": OWN, "upcoming": 3, "rounds": True}

    def test_the_bundles_of_the_rounds_can_be_switched_off_in_the_config(self, tmp_path):
        path = tmp_path / "c.json"
        path.write_text(json.dumps({"team_id": OWN, "rounds": False}), encoding="utf-8")
        assert load_config(path)["rounds"] is False

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
