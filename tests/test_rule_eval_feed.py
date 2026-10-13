"""A finished game replayed "as live" for the rule evaluator (issue #238).

Each line becomes visible ``latency`` seconds after FEB logged it (``LogTimeUtc``; games without it fall back to
the game clock) and the app polls every ``poll`` seconds, so the engine sees what the tablet would have seen.
``shown_elapsed`` is the game-second the staff was watching when that poll arrived (what had been logged by then).
"""
import copy
import json
from pathlib import Path

from src.live_core.engine import LiveEngine
from src.live_core.recorded_feed import RecordedFeed
from src.live_prep.eval_feed import finished_game_polls, parse_log_time, recording_polls, timing_mode

A, B = "T1", "T2"
RECORDINGS = Path(__file__).parent / "recordings"


def line(num, time, log=None, text="(A) Ana: TIRO DE 2 ANOTADO", team=A, player="a1", action="shoot", period=1):
    row = {"num": str(num), "quarter": str(period), "time": time, "action": action, "text": text,
           "idTeam": team, "idPlayer": player, "deleted": None}
    if log:
        row["LogTimeUtc"] = f"2026-10-17 {log}"
    return row


def game(lines, shots=()):
    return {
        "HEADER": {"starttime": "17-10-2026 - 17:00", "status": "3", "statusText": "FINISHED", "quarter": "4",
                   "time": "FINAL", "TEAM": [{"id": A, "name": "Alfa", "pts": "4"}, {"id": B, "name": "Beta", "pts": "2"}]},
        "BOXSCORE": {"TEAM": [{"id": A, "name": "Alfa", "PLAYER": [{"id": "a1", "name": "Ana", "pts": "4"}]},
                              {"id": B, "name": "Beta", "PLAYER": [{"id": "b1", "name": "Bea", "pts": "2"}]}]},
        "PLAYBYPLAY": {"LINES": list(reversed(lines))},  # FEB serves the newest line first
        "SHOTCHART": {"quarters": 4, "duration": 10, "TEAM": [], "SHOTS": list(shots)},
    }


LOGGED = [
    line(1, "10:00", "12:00:00", "(A) Ana: Sustitución (Entra a pista)", action="subst"),
    line(2, "09:30", "12:01:30"),                                                    # elapsed 30
    line(3, "09:00", "12:02:00", "(B) Bea: TIRO DE 2 ANOTADO", team=B, player="b1"),  # elapsed 60
    line(4, "08:00", "12:04:00"),                                                    # elapsed 120
]


def epoch(text):
    return parse_log_time(f"2026-10-17 {text}")


def test_parse_log_time_reads_feb_utc_timestamps():
    assert parse_log_time("2026-10-17 12:00:10") - parse_log_time("2026-10-17 12:00:00") == 10
    assert parse_log_time(None) is None and parse_log_time("") is None and parse_log_time("garbage") is None


def test_a_line_is_visible_latency_seconds_after_it_was_logged():
    polls = list(finished_game_polls(game(LOGGED), latency_s=40, poll_s=10))
    counts = [len(p.doc["PLAYBYPLAY"]["LINES"]) for p in polls]
    assert counts == [1, 2, 3, 4]  # a poll without news is not delivered
    assert polls[0].t == epoch("12:00:40") and polls[1].t == epoch("12:02:10")
    assert polls[2].t == epoch("12:02:40") and polls[3].t == epoch("12:04:40")


def test_polls_are_on_the_polling_grid():
    polls = list(finished_game_polls(game(LOGGED), latency_s=40, poll_s=10))
    assert all((p.t - polls[0].t) % 10 == 0 for p in polls)


def test_shown_elapsed_is_what_had_been_logged_when_the_poll_arrived():
    polls = list(finished_game_polls(game(LOGGED), latency_s=40, poll_s=10))
    # at 12:02:10 the staff is already past line 3 (logged 12:02:00, second 60) but the document has lines 1-2
    assert [p.shown_elapsed for p in polls] == [0, 60, 60, 120]


def test_lines_logged_out_of_order_wait_for_the_slowest_one():
    late = copy.deepcopy(LOGGED)
    late[1]["LogTimeUtc"] = "2026-10-17 12:03:00"  # line 2 reached FEB after line 3
    polls = list(finished_game_polls(game(late), latency_s=40, poll_s=10))
    counts = [len(p.doc["PLAYBYPLAY"]["LINES"]) for p in polls]
    assert counts == [1, 3, 4] and polls[1].t == epoch("12:03:40")  # lines 2 and 3 appear together


def test_without_log_times_the_game_clock_stands_in_for_them():
    plain = [{k: v for k, v in l.items() if k != "LogTimeUtc"} for l in LOGGED]
    g = game(plain)
    assert timing_mode(game(LOGGED)) == "log_time" and timing_mode(g) == "game_clock"
    polls = list(finished_game_polls(g, latency_s=40, poll_s=10))
    assert [len(p.doc["PLAYBYPLAY"]["LINES"]) for p in polls] == [1, 2, 3, 4]
    assert [p.t for p in polls][:2] == [40, 70]            # seconds of game clock + latency
    assert [p.shown_elapsed for p in polls] == [30, 60, 60, 120]   # the last second logged by each poll time


def test_one_line_without_a_log_time_makes_the_whole_game_use_the_game_clock():
    mixed = copy.deepcopy(LOGGED)
    del mixed[2]["LogTimeUtc"]
    assert timing_mode(game(mixed)) == "game_clock"


def test_each_document_looks_like_a_live_one():
    polls = list(finished_game_polls(game(LOGGED), latency_s=40, poll_s=10))
    doc = polls[1].doc  # lines 1-2 visible
    header = doc["HEADER"]
    assert header["status"] == "2" and header["quarter"] == "1" and header["time"] == "09:30"
    assert [t["id"] for t in header["TEAM"]] == [A, B]
    assert {l["num"] for l in doc["PLAYBYPLAY"]["LINES"]} == {"1", "2"}
    players = [p for t in doc["BOXSCORE"]["TEAM"] for p in t["PLAYER"]]
    assert {p["id"] for p in players} == {"a1", "b1"} and all("pts" not in p for p in players)  # roster only


def test_the_shot_chart_is_cut_at_the_last_visible_line():
    shots = [{"quarter": "1", "t": "09:30", "x": "10", "y": "20", "team": "0", "m": "1", "player": "1"},
             {"quarter": "1", "t": "08:00", "x": "10", "y": "20", "team": "0", "m": "0", "player": "1"}]
    polls = list(finished_game_polls(game(LOGGED, shots), latency_s=40, poll_s=10))
    assert [len(p.doc["SHOTCHART"]["SHOTS"]) for p in polls] == [0, 1, 1, 2]


def test_the_engine_digests_every_poll_and_ends_with_the_final_score():
    engine, snaps = LiveEngine(), []
    for p in finished_game_polls(game(LOGGED), latency_s=40, poll_s=10):
        snaps.append(engine.update(p.doc))
    assert [s["elapsed"] for s in snaps] == [0, 30, 60, 120]
    assert snaps[-1]["score"] == {A: 4, B: 2}


def test_the_engine_does_not_modify_the_documents_it_is_given():
    """The replay shares line dictionaries between polls (no deep copies): the engine must leave them alone."""
    for p in finished_game_polls(game(LOGGED), latency_s=40, poll_s=10):
        before = json.dumps(p.doc, sort_keys=True)
        LiveEngine().update(p.doc)
        assert json.dumps(p.doc, sort_keys=True) == before


def test_a_game_without_play_by_play_has_no_polls():
    assert list(finished_game_polls(game([]), latency_s=40, poll_s=10)) == []


def test_the_real_sample_game_replays_to_its_official_score(feb_game_doc):
    engine, last, count = LiveEngine(), None, 0
    elapsed = []
    for p in finished_game_polls(feb_game_doc, latency_s=40, poll_s=10):
        last = engine.update(p.doc)
        elapsed.append(last["elapsed"])
        count += 1
    assert elapsed == sorted(elapsed)
    assert 100 < count < 600
    for team in feb_game_doc["HEADER"]["TEAM"]:
        assert last["score"][str(team["id"])] == int(team["pts"])


def test_recording_polls_follow_the_recording_and_skip_the_404_windows():
    feed = RecordedFeed.load(RECORDINGS / "2524470.rec.json.gz")
    polls = list(recording_polls(feed, poll_s=60))
    assert polls and all(p.shown_elapsed is None for p in polls)
    times = [p.t for p in polls]
    assert times == sorted(times) and all(t % 60 == 0 for t in times)
    assert not any(feed.in_any_gap(t) for t in times)          # the real 404 of the 4th quarter is not delivered
    assert 6000 not in times and len(polls[-1].doc["PLAYBYPLAY"]["LINES"]) == 458
