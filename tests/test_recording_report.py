"""Analysis of a FEB live recording (issue #171): the numbers #118 needs."""
import copy
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from src.live_core.vectors import unwrap_extended_json
from src.live_prep.recorder import Recorder, Response
from src.live_prep.recording_report import main, merged_documents, summarize, to_markdown

ROOT = Path(__file__).resolve().parents[1]
GAME = unwrap_extended_json(json.loads((ROOT / "src/JSON_samples/feb_game.json").read_text(encoding="utf-8")))


class Clock:
    def __init__(self):
        self.t = 1_800_000_000.0

    def now(self):
        return self.t

    def sleep(self, s):
        self.t += s

    def utc(self):
        return datetime(2026, 10, 10, 15, 0, 0, tzinfo=timezone.utc) + timedelta(seconds=self.t - 1_800_000_000.0)


def _doc(game, status, upto):
    """The sample game cut to its first ``upto`` play-by-play lines, split into the three endpoints."""
    lines = sorted(game["PLAYBYPLAY"]["LINES"], key=lambda l: int(l["num"]))[:upto]
    for i, l in enumerate(lines):  # event times run slower than the polls: every event is seen some seconds after it happened
        l["LogTimeUtc"] = (datetime(2026, 10, 10, 15, 0, 0) + timedelta(seconds=3 * i)).strftime("%Y-%m-%d %H:%M:%S")
    head = {"status": status, "TEAM": game["HEADER"]["TEAM"]}
    box = {"HEADER": head, "BOXSCORE": game["BOXSCORE"]}
    shots = {"HEADER": head, "SHOTCHART": game["SHOTCHART"]}
    keyf = {"HEADER": head, "PLAYBYPLAY": {"LINES": lines}}
    return box, shots, keyf


@pytest.fixture(scope="module")
def recording(tmp_path_factory):
    out = tmp_path_factory.mktemp("rec")
    clock = Clock()
    steps = [(404, None)] * 2 + [("2", 3), ("2", 3), ("2", 6), ("2", 9), ("3", 12)]
    state = {"i": 0}

    def get(url, token):
        kind = "boxscore" if "BoxScore" in url else "shotchart" if "ShotChart" in url else "keyfacts"
        status, upto = steps[min(state["i"], len(steps) - 1)]
        if kind == "boxscore":
            state["i"] += 1
        if status == 404:
            return Response(404, {}, b"")
        body = _doc(copy.deepcopy(GAME), status, upto)["boxscore shotchart keyfacts".split().index(kind)]
        return Response(200, {"Date": "x"}, json.dumps(body).encode())

    rec = Recorder("777", out, get, lambda c, force=False: "t", interval=10, not_started_interval=10, tail_polls=1,
                   now=clock.now, sleep=clock.sleep, utcnow=clock.utc)
    rec.run()
    return out


def test_summary_reports_status_transitions_and_counts(recording):
    s = summarize(recording)
    assert s["match_code"] == "777" and s["finished"] is True
    assert s["first_200_t"] and s["not_started_polls"] == 2
    assert [t["status"] for t in s["status_timeline"]] == ["2", "3"]


def test_update_cadence_is_measured_from_the_changes_of_the_play_by_play(recording):
    s = summarize(recording)
    assert s["pbp_changes"] >= 3 and s["cadence_s"]["median"] == pytest.approx(10.0, abs=0.1)


def test_event_delay_compares_the_log_time_with_the_poll_time(recording):
    delay = summarize(recording)["event_delay_s"]
    assert delay["n"] >= 3 and delay["median"] >= 0


def test_errors_token_and_http_status_counts_are_reported(recording):
    s = summarize(recording)
    assert s["errors"] == 0 and s["token_renewals"] == 0 and s["http_status"]["200"] > 0 and s["http_status"]["404"] == 2


def test_documents_are_rebuilt_from_the_three_endpoints(recording):
    docs = list(merged_documents(recording))
    assert docs and all({"HEADER", "BOXSCORE", "PLAYBYPLAY", "SHOTCHART"} <= set(d) for _, d in docs)
    sizes = [len(d["PLAYBYPLAY"]["LINES"]) for _, d in docs]
    assert sizes == sorted(sizes) and sizes[-1] == 12


def test_the_engine_replays_the_recording_without_crashing(recording):
    s = summarize(recording, replay=True)
    assert s["engine"]["updates"] >= 3 and s["engine"]["crashed"] is False
    assert s["engine"]["max_ms"] >= 0


def test_markdown_is_readable_and_names_the_key_findings(recording):
    md = to_markdown(summarize(recording, replay=True))
    assert md.startswith("# Grabación FEB 777") and "cadencia" in md.lower() and "retraso" in md.lower()


def test_cli_prints_the_report_and_writes_the_step_summary(recording, tmp_path, monkeypatch, capsys):
    summary = tmp_path / "s.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    assert main([str(recording), "--replay"]) == 0
    assert "Grabación FEB 777" in capsys.readouterr().out and "Grabación FEB 777" in summary.read_text(encoding="utf-8")


def test_a_recording_without_data_is_reported_not_crashed(tmp_path):
    (tmp_path / "polls.jsonl").write_text("", encoding="utf-8")
    s = summarize(tmp_path)
    assert s["polls"] == 0 and s["finished"] is False
