"""The FBCYL recorder (issue #444): does FBCYL publish a match WHILE it is played?

Eleven finished matches of the group A-1 show every move stamped within 12 seconds of the others, right after the end of the match: the table app seems to upload the whole play-by-play
in one go. The recorder watches the next match to prove it: it follows the calendar row (the ESB API answers Base64) until the match has a ``universallyid``, then polls the moves and the stats
and keeps what changes, with the time. ``fbcyl_recording_report`` turns it into the go / no-go.
"""
import base64
import gzip
import json
from datetime import datetime, timezone
from pathlib import Path

from src.live_prep import fbcyl_recorder as rec
from src.live_prep.fbcyl_recording_report import report, verdict
from src.live_prep.recorder import Response

GROUP = "7298"
UUID = "a" * 24


def row(home="39609", away="40060", uuid=None, state="0", live=False, match_day="2026-10-31 17:00:00", home_name="UNILEON B.F.LEÓN", away_name="C.B. VILLAMURIEL", **over):
    return {"idMatch": "149395", "idGroup": GROUP, "idLocalTeam": home, "idVisitorTeam": away, "nameLocalTeam": home_name, "nameVisitorTeam": away_name,
            "universallyid": uuid, "state": state, "isLive": live, "matchDay": match_day, "dayTime": "T", "localScore": None, "visitorScore": None,
            "matchStartedHour": None, **over}


def calendar_text(*rows, date="2026-11-01"):
    payload = {"result": "OK", "messageData": {"rounds": {"5": {"date": date, "matches": {str(i): r for i, r in enumerate(rows)}}}}}
    return base64.b64encode(json.dumps(payload).encode()).decode()


def test_the_calendar_is_decoded_and_flattened_into_rows_with_their_round():
    rows = rec.calendar_rows(calendar_text(row(), row(home="1", away="2", state="1")))
    assert [r["idLocalTeam"] for r in rows] == ["39609", "1"] and rows[0]["round"] == "5" and rows[0]["round_date"] == "2026-11-01"


def test_a_calendar_that_is_not_ok_or_not_base64_gives_no_rows_instead_of_a_crash():
    assert rec.calendar_rows("not base64 !!") == []
    assert rec.calendar_rows(base64.b64encode(b'{"result": "KO"}').decode()) == []


# --- planning -------------------------------------------------------------------------------------------------------------------------------

NOW = datetime(2026, 10, 31, 14, 30, tzinfo=timezone.utc)          # 15:30 in Madrid: the match is at 17:00, 90 minutes ahead
WATCH = {"groups": [GROUP], "teams": ["39609"]}


def plan(rows, now=NOW, watch=WATCH):
    return rec.plan(watch, now, lambda group: rows)


def test_a_watched_match_close_to_its_kick_off_is_planned_with_what_the_recorder_needs():
    [item] = plan([rec.with_round(row(), "5", "2026-11-01")])
    assert item["group"] == GROUP and item["home_id"] == "39609" and item["away_id"] == "40060"
    assert item["label"] == "UNILEON B.F.LEÓN - C.B. VILLAMURIEL" and item["start_at"] == "2026-10-31T16:00:00+00:00"


def test_matches_of_other_teams_far_from_kick_off_or_already_played_are_not_planned():
    other = rec.with_round(row(home="1", away="2"), "5", "2026-11-01")
    far = rec.with_round(row(match_day="2026-11-07 17:00:00"), "6", "2026-11-08")
    played = rec.with_round(row(state="1"), "4", "2026-10-25")
    assert plan([other, far, played]) == []


def test_a_match_that_is_live_is_planned_even_if_its_start_is_unknown():
    [item] = plan([rec.with_round(row(live=True, uuid=UUID, match_day=None), "5", "2026-11-01")], now=datetime(2026, 10, 31, 20, 0, tzinfo=timezone.utc))
    assert item["home_id"] == "39609"


def test_without_teams_every_match_of_the_group_is_watched():
    assert len(plan([rec.with_round(row(home="1", away="2"), "5", "2026-11-01")], watch={"groups": [GROUP]})) == 1


# --- recording ------------------------------------------------------------------------------------------------------------------------------

class World:
    """A scripted FBCYL: the calendar row and the answers of the two endpoints change with the time."""

    def __init__(self, script):
        self.script, self.clock, self.calls = script, 0.0, []

    def sleep(self, seconds):
        self.clock += seconds

    def now(self):
        return self.clock

    def get(self, url):
        self.calls.append((self.clock, url))
        step = self.script(self.clock)
        if "FCBQWeb" in url:
            return Response(200, {}, step["calendar"].encode())
        body = step.get("moves" if "Moves" in url else "stats")
        return Response(404 if body is None else 200, {"date": "x"}, b"" if body is None else json.dumps(body).encode())


def run(script, tmp_path, **kw):
    world = World(script)
    recorder = rec.FbcylRecorder(GROUP, "39609", "40060", tmp_path, world.get, interval=10, calendar_every_s=60, now=world.now, sleep=world.sleep,
                                 utcnow=lambda: datetime(2026, 10, 31, 15, 0, tzinfo=timezone.utc), **kw)
    return recorder, recorder.run(), world


def lines(path):
    return [json.loads(x) for x in Path(path).read_text(encoding="utf-8").splitlines()]


def test_it_only_watches_the_calendar_until_the_match_has_an_id_and_then_polls_moves_and_stats(tmp_path):
    def script(t):
        if t < 300:
            return {"calendar": calendar_text(row())}
        done = t > 400
        return {"calendar": calendar_text(row(uuid=UUID, state="1" if done else "0", live=not done)),
                "moves": [{"idMove": 1, "period": 1}] * (1 if t < 360 else 5), "stats": {"time": "t", "period": 1, "moves": []}}
    _, summary, world = run(script, tmp_path)
    endpoint_times = [t for t, url in world.calls if "msstats" in url]
    assert endpoint_times and min(endpoint_times) >= 300                       # nothing is asked of the match before it exists
    assert summary["finished"] and summary["reason"] == "finished"
    assert {p["endpoint"] for p in lines(tmp_path / "polls.jsonl")} == {"moves", "stats"}


def test_only_what_changes_is_kept_and_every_poll_says_so(tmp_path):
    def script(t):
        done = t > 100
        return {"calendar": calendar_text(row(uuid=UUID, state="1" if done else "0")), "moves": [{"idMove": 1}] * (1 if t < 50 else 3), "stats": {"time": "t"}}
    run(script, tmp_path)
    moves = [p for p in lines(tmp_path / "polls.jsonl") if p["endpoint"] == "moves"]
    assert [p["changed"] for p in moves].count(True) == 2 and all("sha" in p and "size" in p for p in moves)
    bodies = sorted((tmp_path / "bodies").glob("*moves*"))
    assert len(bodies) == 2 and json.loads(gzip.decompress(bodies[0].read_bytes())) == [{"idMove": 1}]
    assert moves[-1]["n_moves"] == 3                                          # readable without opening the bodies


def test_the_rows_of_the_calendar_are_kept_with_the_time(tmp_path):
    run(lambda t: {"calendar": calendar_text(row(uuid=UUID, state="1" if t > 70 else "0", live=t > 20)), "moves": [], "stats": {}}, tmp_path)
    snapshots = lines(tmp_path / "calendar.jsonl")
    assert snapshots[0]["row"]["state"] == "0" and snapshots[-1]["row"]["state"] == "1" and "t" in snapshots[-1]


def test_a_match_already_played_when_the_recorder_starts_is_left_alone(tmp_path):
    _, summary, world = run(lambda t: {"calendar": calendar_text(row(uuid=UUID, state="1"))}, tmp_path, skip_if_finished=True)
    assert summary["reason"] == "already_finished" and not [c for c in world.calls if "msstats" in c[1]]


def test_it_gives_up_when_the_match_never_appears_or_never_ends(tmp_path):
    _, summary, _ = run(lambda t: {"calendar": calendar_text(row())}, tmp_path, max_wait_minutes=5)
    assert summary["reason"] == "never_started"
    _, summary, _ = run(lambda t: {"calendar": calendar_text(row(uuid=UUID, live=True)), "moves": [], "stats": {}}, tmp_path / "b", max_minutes=3)
    assert summary["reason"] == "time_limit"


# --- the report: live or in one go ----------------------------------------------------------------------------------------------------------------

def record(tmp_path, counts):
    """A recording whose moves endpoint answered with ``counts`` moves, one reading every 5 minutes, and a calendar that says the match is live until the last one."""
    folder = tmp_path / "rec"
    folder.mkdir(parents=True)
    polls, calendar = [], []
    for i, n in enumerate(counts):
        t = datetime(2026, 10, 31, 15, 0, tzinfo=timezone.utc).timestamp() + 300 * i
        iso = datetime.fromtimestamp(t, timezone.utc).isoformat()
        polls.append({"t": iso, "endpoint": "moves", "status": 200, "changed": i == 0 or n != counts[i - 1], "n_moves": n, "size": 10 * n, "sha": str(i)})
        last = i == len(counts) - 1
        calendar.append({"t": iso, "row": {"universallyid": UUID, "state": "1" if last else "0", "isLive": not last, "localScore": None}})
    (folder / "polls.jsonl").write_text("\n".join(json.dumps(p) for p in polls), encoding="utf-8")
    (folder / "calendar.jsonl").write_text("\n".join(json.dumps(c) for c in calendar), encoding="utf-8")
    return folder


def test_moves_that_grow_during_the_match_are_live(tmp_path):
    assert verdict(record(tmp_path, [0, 40, 120, 250, 380, 460, 520]))["live"] is True


def test_moves_that_appear_all_at_once_when_the_match_ends_are_not_live(tmp_path):
    result = verdict(record(tmp_path, [0, 0, 0, 0, 0, 0, 520]))
    assert result["live"] is False and "de golpe" in result["reason"]


def test_the_report_says_the_go_no_go_in_words(tmp_path):
    assert "NO-GO" in report(record(tmp_path, [0, 0, 0, 0, 0, 0, 520]))
    assert "NO-GO" not in report(record(tmp_path / "x", [0, 40, 120, 250, 380, 460, 520]))
