"""FEB format canary (issue #136): detects changes in the FEB data BEFORE a live match does.

Pure checks over a finished game document: schema drift against a committed reference
document and invariants of the live engine (final score, fouls, shot totals), plus a CLI whose
exit code tells drift (1) from "could not fetch FEB" (2).
"""
import copy
import json
from pathlib import Path

import pytest

from src.live_core.vectors import unwrap_extended_json
from src.live_prep.canary import (
    CanaryReport,
    check_invariants,
    compare_signatures,
    main,
    run_checks,
    signature,
)

ROOT = Path(__file__).resolve().parents[1]
REFERENCE_PATH = ROOT / "src/JSON_samples/feb_game.json"
REF = unwrap_extended_json(json.loads(REFERENCE_PATH.read_text(encoding="utf-8")))


def mutated():
    return copy.deepcopy(REF)


class TestSignature:
    def test_covers_the_sections_the_engine_reads(self):
        sig = signature(REF)
        for prefix in ("HEADER", "BOXSCORE", "PLAYBYPLAY", "SHOTCHART"):
            assert any(p.startswith(prefix) for p in sig)

    def test_lists_are_collapsed_and_types_recorded(self):
        sig = signature({"HEADER": {"TEAM": [{"id": "1", "pts": "5"}, {"id": "2"}]}})
        assert sig["HEADER.TEAM[].id"] == {"str"}
        assert "HEADER.TEAM[].pts" in sig  # present in at least one element

    def test_ignores_sections_the_engine_does_not_use(self):
        assert not any(p.startswith(("RANKING", "BANNER", "_")) for p in signature({**REF, "RANKING": {"a": 1}}))


class TestCompare:
    def test_identical_documents_have_no_drift(self):
        d = compare_signatures(signature(REF), signature(mutated()))
        assert d == {"missing": [], "type_changes": [], "new": []}

    def test_a_removed_field_is_reported_as_missing(self):
        live = mutated()
        for line in live["PLAYBYPLAY"]["LINES"]:
            line.pop("time", None)
        assert "PLAYBYPLAY.LINES[].time" in compare_signatures(signature(REF), signature(live))["missing"]

    def test_a_changed_type_is_reported(self):
        live = mutated()
        live["HEADER"]["status"] = 3
        changes = compare_signatures(signature(REF), signature(live))["type_changes"]
        assert any(c[0] == "HEADER.status" for c in changes)

    def test_new_fields_are_only_informational(self):
        live = mutated()
        live["HEADER"]["newField"] = "x"
        d = compare_signatures(signature(REF), signature(live))
        assert d["new"] == ["HEADER.newField"] and not d["missing"] and not d["type_changes"]


class TestInvariants:
    def test_the_reference_game_satisfies_every_invariant(self):
        assert check_invariants(REF) == []

    def test_final_score_must_match_the_header(self):
        live = mutated()
        live["HEADER"]["TEAM"][0]["pts"] = str(int(live["HEADER"]["TEAM"][0]["pts"]) + 3)
        assert any("marcador" in e.lower() for e in check_invariants(live))

    def test_player_fouls_must_match_the_box_score(self):
        live = mutated()
        p = live["BOXSCORE"]["TEAM"][0]["PLAYER"][0]
        p["pf"] = str(int(p.get("pf") or 0) + 2)
        assert any("faltas" in e.lower() for e in check_invariants(live))

    def test_team_shooting_totals_must_match_the_box_score(self):
        live = mutated()
        live["BOXSCORE"]["TEAM"][0]["TOTAL"]["p3m"] = "99"
        assert any("triples" in e.lower() for e in check_invariants(live))

    def test_an_unfinished_game_is_rejected_as_a_canary_target(self):
        live = mutated()
        live["HEADER"]["status"] = "2"
        assert any("finalizado" in e.lower() for e in check_invariants(live))

    def test_empty_play_by_play_is_an_error(self):
        live = mutated()
        live["PLAYBYPLAY"]["LINES"] = []
        assert any("play-by-play" in e.lower() for e in check_invariants(live))

    def test_engine_crashes_are_reported_not_raised(self):
        live = mutated()
        live["PLAYBYPLAY"]["LINES"] = "garbage"
        errors = check_invariants(live)
        assert errors and any("motor" in e.lower() or "play-by-play" in e.lower() for e in errors)


class TestReport:
    def test_ok_when_there_are_no_errors(self):
        r = run_checks(copy.deepcopy(REF), REF)
        assert isinstance(r, CanaryReport) and r.ok and not r.errors

    def test_new_fields_warn_but_do_not_fail(self):
        live = mutated()
        live["HEADER"]["newField"] = "x"
        r = run_checks(live, REF)
        assert r.ok and any("newField" in w for w in r.warnings)

    def test_drift_and_invariant_violations_fail(self):
        live = mutated()
        live["HEADER"]["status"] = 3
        r = run_checks(live, REF)
        assert not r.ok and any("HEADER.status" in e for e in r.errors)

    def test_markdown_summary_names_the_match_and_the_problems(self):
        live = mutated()
        live["HEADER"]["TEAM"][0]["pts"] = "1"
        md = run_checks(live, REF, match_code="2477341").markdown()
        assert "2477341" in md and "marcador" in md.lower() and md.startswith("#")


class TestCli:
    def _fetch(self, doc):
        return lambda code: doc

    def test_exit_0_when_everything_matches(self, capsys):
        assert main(["--match", "1", "--reference", str(REFERENCE_PATH)], fetch=self._fetch(REF)) == 0
        assert "OK" in capsys.readouterr().out

    def test_exit_1_on_drift(self, capsys):
        live = mutated()
        live["HEADER"]["status"] = 3
        assert main(["--match", "1", "--reference", str(REFERENCE_PATH)], fetch=self._fetch(live)) == 1
        assert "HEADER.status" in capsys.readouterr().out

    def test_exit_2_when_feb_cannot_be_fetched(self, capsys):
        def boom(code):
            raise ConnectionError("feb down")

        assert main(["--match", "1", "--reference", str(REFERENCE_PATH)], fetch=boom) == 2
        assert "feb down" in capsys.readouterr().out

    def test_exit_2_when_the_match_comes_back_empty(self):
        assert main(["--match", "1", "--reference", str(REFERENCE_PATH)], fetch=lambda c: None) == 2

    def test_writes_the_github_step_summary(self, tmp_path, monkeypatch):
        summary = tmp_path / "summary.md"
        monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
        main(["--match", "1", "--reference", str(REFERENCE_PATH)], fetch=self._fetch(REF))
        assert "FEB" in summary.read_text(encoding="utf-8")

    def test_several_matches_fail_if_any_fails(self):
        bad = mutated()
        bad["HEADER"]["status"] = 3
        docs = {"1": REF, "2": bad}
        code = main(["--match", "1", "--match", "2", "--reference", str(REFERENCE_PATH)], fetch=lambda c: docs[c])
        assert code == 1
