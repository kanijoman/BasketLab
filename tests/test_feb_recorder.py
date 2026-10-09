"""FEB live-feed recorder (issue #171): records what FEB serves during a match so the live engine
can be validated and replayed offline."""
import gzip
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.live_prep.recorder import ENDPOINTS, Recorder, Response


class FakeClock:
    """Monotonic fake time: sleeping advances it; no real waiting."""

    def __init__(self, start=1_800_000_000.0):
        self.t = start
        self.sleeps = []

    def now(self):
        return self.t

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.t += seconds


def _box(status, lines=0, pts=(0, 0)):
    return {"HEADER": {"status": status, "statusText": {"0": "", "2": "LIVE", "3": "FINISHED"}.get(status, ""),
                       "TEAM": [{"id": "1", "pts": str(pts[0])}, {"id": "2", "pts": str(pts[1])}]},
            "PLAYBYPLAY": {"LINES": [{"num": i, "LogTimeUtc": "2027-01-01T17:00:%02d" % (i % 60)} for i in range(lines)]}}


class FakeFeb:
    """Serves a scripted sequence per endpoint; the last entry repeats."""

    def __init__(self, box, shots=None, keyfacts=None):
        self.script = {"boxscore": box, "shotchart": shots or [(200, {"SHOTS": []})], "keyfacts": keyfacts or [(200, {"FACTS": []})]}
        self.calls = {k: 0 for k in self.script}
        self.tokens = []

    def get(self, url, token):
        ep = next(k for k, template in ENDPOINTS.items() if url == template.format(match_code="777"))
        seq = self.script[ep]
        status, body = seq[min(self.calls[ep], len(seq) - 1)]
        self.calls[ep] += 1
        raw = json.dumps(body).encode() if body is not None else b""
        return Response(status, {"Date": "Sat, 10 Oct 2026 15:00:00 GMT", "ETag": f'"{self.calls[ep]}"', "X-Secret": "hide"}, raw)

    def token(self, code, force=False):
        self.tokens.append(force)
        return f"tok{len(self.tokens)}"


def _run(tmp_path, feb, **kw):
    clock = FakeClock()
    rec = Recorder("777", tmp_path, feb.get, feb.token, now=clock.now, sleep=clock.sleep,
                   utcnow=lambda: datetime.fromtimestamp(clock.t, timezone.utc), **kw)
    return rec, clock


def _lines(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines()]


LIVE_GAME = [(404, None), (404, None), (200, _box("2", 1)), (200, _box("2", 1)), (200, _box("2", 5, (10, 8))),
             (200, _box("2", 9, (20, 18))), (200, _box("3", 12, (22, 18)))]


class TestRun:
    def test_records_from_not_started_to_finished_and_stops(self, tmp_path):
        feb = FakeFeb(LIVE_GAME)
        rec, _ = _run(tmp_path, feb, interval=10, tail_polls=2)
        result = rec.run()
        assert result["finished"] is True and result["reason"] == "finished"
        polls = [p for p in _lines(tmp_path / "polls.jsonl") if p["endpoint"] == "boxscore"]
        assert [p["status"] for p in polls][:3] == [404, 404, 200]
        assert [p["game_status"] for p in polls if p["status"] == 200][-1] == "3"
        assert len(polls) >= len(LIVE_GAME)

    def test_polls_every_endpoint_each_round(self, tmp_path):
        feb = FakeFeb(LIVE_GAME)
        rec, _ = _run(tmp_path, feb, interval=10, tail_polls=1)
        rec.run()
        live_polls = [p for p in _lines(tmp_path / "polls.jsonl") if p["endpoint"] == "boxscore" and p["status"] == 200]
        assert feb.calls["shotchart"] == feb.calls["keyfacts"] == len(live_polls) > 0  # nothing else is asked while 404

    def test_bodies_are_stored_only_when_they_change(self, tmp_path):
        rec, _ = _run(tmp_path, FakeFeb(LIVE_GAME), interval=10, tail_polls=3)
        rec.run()
        box_polls = [p for p in _lines(tmp_path / "polls.jsonl") if p["endpoint"] == "boxscore" and p["status"] == 200]
        changed = [p for p in box_polls if p["changed"]]
        files = sorted((tmp_path / "bodies").glob("*boxscore*"))
        assert len(changed) == 4 and len(files) == 4 and len(box_polls) > 4  # 4 distinct bodies, more polls
        assert json.loads(gzip.decompress(files[-1].read_bytes()))["HEADER"]["status"] == "3"

    def test_poll_records_keep_timing_and_selected_headers_only(self, tmp_path):
        rec, _ = _run(tmp_path, FakeFeb(LIVE_GAME), interval=10, tail_polls=1)
        rec.run()
        p = next(p for p in _lines(tmp_path / "polls.jsonl") if p["status"] == 200)
        assert {"t", "mono", "endpoint", "status", "ms", "size", "sha", "changed", "headers"} <= set(p)
        assert "ETag" in p["headers"] and "Date" in p["headers"] and "X-Secret" not in p["headers"]

    def test_play_by_play_growth_and_latest_event_time_are_tracked(self, tmp_path):
        rec, _ = _run(tmp_path, FakeFeb(LIVE_GAME), interval=10, tail_polls=1)
        rec.run()
        live = [p for p in _lines(tmp_path / "polls.jsonl") if p["endpoint"] == "boxscore" and p["status"] == 200]
        assert [p["pbp_lines"] for p in live][:5] == [1, 1, 5, 9, 12]
        assert live[0]["last_log_utc"].startswith("2027-01-01T17:00")

    def test_a_401_renews_the_token_and_retries_once(self, tmp_path):
        feb = FakeFeb([(401, None), (200, _box("3", 3))])
        rec, _ = _run(tmp_path, feb, interval=10, tail_polls=1)
        rec.run()
        assert feb.tokens[0] is False and True in feb.tokens
        assert rec.summary["token_renewals"] >= 1

    def test_transient_errors_are_recorded_and_polling_continues(self, tmp_path):
        class Flaky(FakeFeb):
            def get(self, url, token):
                if self.calls["boxscore"] == 1 and url == ENDPOINTS["boxscore"].format(match_code="777"):
                    self.calls["boxscore"] += 1
                    raise ConnectionError("reset")
                return super().get(url, token)

        feb = Flaky([(200, _box("2", 1)), (200, _box("3", 2))])
        rec, _ = _run(tmp_path, feb, interval=10, tail_polls=1)
        result = rec.run()
        assert result["finished"] is True
        errors = [p for p in _lines(tmp_path / "polls.jsonl") if p.get("error")]
        assert errors and "reset" in errors[0]["error"]

    def test_stops_at_the_time_limit_when_the_match_never_finishes(self, tmp_path):
        rec, clock = _run(tmp_path, FakeFeb([(200, _box("2", 1))]), interval=10, max_minutes=5)
        result = rec.run()
        assert result["finished"] is False and result["reason"] == "time_limit"
        assert clock.t - 1_800_000_000.0 <= 5 * 60 + 60

    def test_waits_for_the_scheduled_start_before_polling_fast(self, tmp_path):
        clock = FakeClock()
        feb = FakeFeb([(404, None), (200, _box("3", 1))])
        start = datetime.fromtimestamp(clock.t + 1800, timezone.utc)  # kicks off in 30 min
        rec = Recorder("777", tmp_path, feb.get, feb.token, now=clock.now, sleep=clock.sleep,
                       utcnow=lambda: datetime.fromtimestamp(clock.t, timezone.utc), interval=10, tail_polls=1,
                       pre_start_s=300)
        rec.run(start_at=start)
        assert sum(clock.sleeps[:3]) >= 1500  # slept ~25 min before the first poll
        assert feb.calls["boxscore"] <= 4

    def test_skips_recording_when_the_match_is_already_finished_and_asked_to(self, tmp_path):
        rec, _ = _run(tmp_path, FakeFeb([(200, _box("3", 40))]), interval=10, skip_if_finished=True)
        result = rec.run()
        assert result["reason"] == "already_finished" and result["finished"] is True
        assert not (tmp_path / "bodies").exists() or not any((tmp_path / "bodies").iterdir())

    def test_writes_meta_with_the_run_summary(self, tmp_path):
        rec, _ = _run(tmp_path, FakeFeb(LIVE_GAME), interval=10, tail_polls=1)
        rec.run()
        meta = json.loads((tmp_path / "meta.json").read_text(encoding="utf-8"))
        assert meta["match_code"] == "777" and meta["result"]["finished"] is True and meta["interval_s"] == 10
        assert meta["result"]["polls"] > 0 and meta["result"]["bodies_saved"] > 0

    def test_calendar_snapshots_are_recorded_to_learn_how_a_live_match_looks(self, tmp_path):
        rows = iter([{"kind": "scheduled", "start": "2026-10-10T17:00"}, {"kind": "result", "score": "0-0"}])
        rec, _ = _run(tmp_path, FakeFeb(LIVE_GAME), interval=10, tail_polls=1, calendar_row=lambda code: next(rows, {"kind": "result", "score": "9-9"}),
                      calendar_every_s=20)
        rec.run()
        cal = _lines(tmp_path / "calendar.jsonl")
        assert cal and cal[0]["row"]["kind"] == "scheduled" and any(c["row"]["kind"] == "result" for c in cal)


class TestAnnotations:
    """Every endpoint answers with the same document skeleton; the poll log pulls out the useful facts."""

    def test_play_by_play_facts_are_read_from_the_keyfacts_endpoint(self, tmp_path):
        lines = [{"num": str(i), "LogTimeUtc": f"2026-10-10 15:0{i}:00"} for i in range(1, 4)]
        feb = FakeFeb([(200, _box("3", 0))], keyfacts=[(200, {"HEADER": {"status": "3"}, "PLAYBYPLAY": {"LINES": lines}})])
        rec, _ = _run(tmp_path, feb, interval=10, tail_polls=0)
        rec.run()
        kf = next(p for p in _lines(tmp_path / "polls.jsonl") if p["endpoint"] == "keyfacts")
        assert kf["pbp_lines"] == 3 and kf["last_log_utc"] == "2026-10-10 15:03:00"

    def test_shot_count_is_read_from_the_shotchart_endpoint(self, tmp_path):
        feb = FakeFeb([(200, _box("3", 0))], shots=[(200, {"SHOTCHART": {"SHOTS": [{"x": 1}, {"x": 2}]}})])
        rec, _ = _run(tmp_path, feb, interval=10, tail_polls=0)
        rec.run()
        sc = next(p for p in _lines(tmp_path / "polls.jsonl") if p["endpoint"] == "shotchart")
        assert sc["shots"] == 2

    def test_non_json_bodies_do_not_break_the_recorder(self, tmp_path):
        class Html(FakeFeb):
            def get(self, url, token):
                r = super().get(url, token)
                return Response(r.status, r.headers, b"<html>oops</html>") if "ShotChart" in url else r

        rec, _ = _run(tmp_path, Html([(200, _box("3", 1))]), interval=10, tail_polls=0)
        assert rec.run()["finished"] is True

