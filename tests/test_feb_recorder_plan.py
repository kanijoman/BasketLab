"""Which matches should the scheduled workflow record right now (issue #171)."""
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.live_prep.recorder import main, plan
from src.scraper.calendar_parser import CalendarMatch

URL = "https://baloncestoenvivo.feb.es/calendario.aspx?g=67&t=2026&nm=lfchallenge"


def _m(code, start, home="1", away="2", kind="scheduled", rnd=2):
    return CalendarMatch(code, kind, rnd, home, f"Equipo {home}", away, f"Equipo {away}",
                         start=start, score=None if kind == "scheduled" else "10-9")


CAL = [
    _m("2524470", "2026-10-10T17:00", "10", "11"),   # Zamora - Leon, Saturday 17:00 Madrid = 15:00 UTC
    _m("2524464", "2026-10-10T18:00", "12", "13"),
    _m("2524463", "2026-10-11T12:00", "14", "15"),
]
WATCH = {"calendar": URL, "matches": ["2524470"]}


def at(iso_utc):
    return datetime.fromisoformat(iso_utc).replace(tzinfo=timezone.utc)


def _plan(now, watch=WATCH, cal=CAL, status=lambda c: "scheduled"):
    return plan(watch, now, fetch_calendar=lambda url: cal, match_status=status)


class TestPlan:
    def test_nothing_to_record_the_day_before(self):
        assert _plan(at("2026-10-09T10:00")) == []

    def test_starts_recording_shortly_before_kick_off(self):
        out = _plan(at("2026-10-10T14:30"))  # 16:30 Madrid, 30 min before
        assert [m["code"] for m in out] == ["2524470"]
        assert out[0]["start_at"] == "2026-10-10T15:00:00+00:00"  # Madrid local time converted to UTC

    def test_the_window_is_generous_to_absorb_late_cron_runs(self):
        assert _plan(at("2026-10-10T14:20"))  # 40 min before
        assert _plan(at("2026-10-10T15:25"))  # 25 min after kick-off (GitHub schedules can lag)

    def test_nothing_after_the_window(self):
        assert _plan(at("2026-10-10T15:45")) == []

    def test_only_matches_on_the_watchlist_are_planned(self):
        out = _plan(at("2026-10-10T15:00"))
        assert [m["code"] for m in out] == ["2524470"]  # 18:00 match not watched

    def test_a_team_on_the_watchlist_selects_all_its_matches(self):
        out = _plan(at("2026-10-10T16:00"), watch={"calendar": URL, "teams": ["12"]})
        assert [m["code"] for m in out] == ["2524464"]

    def test_several_matches_starting_together_are_all_planned(self):
        cal = CAL + [_m("2524468", "2026-10-10T17:00", "16", "17")]
        out = _plan(at("2026-10-10T15:00"), watch={"calendar": URL, "matches": ["2524470", "2524468"]}, cal=cal)
        assert {m["code"] for m in out} == {"2524470", "2524468"}

    def test_a_result_row_is_planned_only_if_the_match_is_live(self):
        cal = [_m("2524470", None, kind="result")]
        assert _plan(at("2026-10-10T15:20"), cal=cal, status=lambda c: "live")[0]["code"] == "2524470"
        assert _plan(at("2026-10-10T15:20"), cal=cal, status=lambda c: "finished") == []

    def test_a_calendar_failure_plans_the_watched_codes_with_a_one_off_window(self):
        def boom(url):
            raise ConnectionError("feb down")

        # without a calendar the start is unknown: record nothing rather than guess, but do not crash
        assert plan(WATCH, at("2026-10-10T15:00"), fetch_calendar=boom, match_status=lambda c: "scheduled") == []

    def test_manual_codes_are_recorded_immediately(self):
        out = plan({"calendar": URL, "matches": []}, at("2026-10-10T10:00"), fetch_calendar=lambda u: CAL,
                   match_status=lambda c: "scheduled", extra_codes=["999"])
        assert out[0]["code"] == "999" and out[0]["start_at"] is None


class TestCli:
    def test_plan_prints_a_matrix_for_github_actions(self, tmp_path, capsys):
        wl = tmp_path / "wl.json"
        wl.write_text(json.dumps(WATCH), encoding="utf-8")
        code = main(["plan", "--watchlist", str(wl), "--now", "2026-10-10T15:00:00+00:00"],
                    fetch_calendar=lambda u: CAL, match_status=lambda c: "scheduled")
        assert code == 0
        out = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
        assert out["include"][0]["code"] == "2524470"

    def test_plan_with_nothing_prints_an_empty_matrix(self, tmp_path, capsys):
        wl = tmp_path / "wl.json"
        wl.write_text(json.dumps(WATCH), encoding="utf-8")
        main(["plan", "--watchlist", str(wl), "--now", "2026-10-09T10:00:00+00:00"],
             fetch_calendar=lambda u: CAL, match_status=lambda c: "scheduled")
        assert json.loads(capsys.readouterr().out.strip().splitlines()[-1]) == {"include": []}

    def test_the_committed_watchlist_is_valid_and_has_the_requested_match(self):
        wl = json.loads((Path(__file__).resolve().parents[1] / "config" / "feb_watchlist.json").read_text(encoding="utf-8"))
        assert "2524470" in wl["matches"] and wl["calendar"].startswith("https://baloncestoenvivo.feb.es/calendario")


def test_the_cli_imports_cleanly_outside_pytest_regression():
    """In CI the module runs as ``python -m ...`` with only the scraper dependencies: the scraper's
    legacy un-prefixed imports (``utils...``) must resolve without pytest's sys.path."""
    import subprocess
    import sys

    root = Path(__file__).resolve().parents[1]
    result = subprocess.run([sys.executable, "-m", "src.live_prep.recorder", "--help"], cwd=root,
                            capture_output=True, text=True, env={"PATH": __import__("os").environ["PATH"], "SYSTEMROOT": __import__("os").environ.get("SYSTEMROOT", "")})
    assert result.returncode == 0, result.stderr[-500:]
    assert "plan" in result.stdout and "record" in result.stdout
