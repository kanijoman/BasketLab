"""The planner of the FBCYL recorder (issue #446): on 21/11/2026 four planner runs came out green, none planned the match of 17:00 and nothing was recorded, and nobody could tell why.

The calendar was read once, with no headers, and any failure became «no matches» without a trace. A calendar that cannot be read must be retried and, if it still fails, said (a warning of the run),
and the watchlist must hold the teams whose matches we want to see (the next one, on 25/11, was not the watched team's).
"""
import base64
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.live_prep import fbcyl_recorder as rec
from src.live_prep.recorder import Response

GROUP = "7298"
WATCHLIST = Path(__file__).resolve().parent.parent / "config" / "fbcyl_watchlist.json"
KICK_OFF = "2026-11-21 17:00:00"                                      # Madrid: 16:00 UTC
BEFORE_KICK_OFF = "2026-11-21T14:22:00+00:00"                          # the planner run of that Saturday that found nothing


def calendar(*matches):
    rows = {str(i): m for i, m in enumerate(matches)}
    payload = {"result": "OK", "messageData": {"rounds": {"8": {"date": "2026-11-21", "matches": rows}}}}
    return Response(200, {}, base64.b64encode(json.dumps(payload).encode()))


def match(home="40282", away="39609", day=KICK_OFF):
    return {"idMatch": "149411", "idLocalTeam": home, "idVisitorTeam": away, "nameLocalTeam": "FORMASPACK", "nameVisitorTeam": "UNILEON", "state": "0", "isLive": False, "matchDay": day}


@pytest.fixture
def watchlist(tmp_path):
    path = tmp_path / "watch.json"
    path.write_text(json.dumps({"groups": [GROUP], "teams": ["39609"]}))
    return str(path)


@pytest.fixture(autouse=True)
def no_waiting(monkeypatch):
    monkeypatch.setattr(rec.time, "sleep", lambda s: None)


def planned(watchlist, get, capsys):
    assert rec.main(["plan", "--watchlist", watchlist, "--now", BEFORE_KICK_OFF], get=get) == 0
    out = capsys.readouterr()
    return json.loads(out.out)["include"], out.err


def test_a_calendar_that_fails_at_first_is_asked_again_and_the_match_is_planned(watchlist, capsys):
    answers = [Response(500, {}, b""), Response(200, {}, b"<html>busy</html>"), calendar(match())]
    include, err = planned(watchlist, lambda url: answers.pop(0), capsys)
    assert [m["home_id"] for m in include] == ["40282"] and "::warning::" not in err


def test_a_calendar_that_never_answers_is_said_in_the_run_not_swallowed_as_no_matches(watchlist, capsys):
    include, err = planned(watchlist, lambda url: Response(500, {}, b""), capsys)
    assert include == [] and "::warning::" in err and GROUP in err


def test_a_calendar_that_raises_is_said_too_and_does_not_stop_the_run(watchlist, capsys):
    def down(url):
        raise ConnectionError("no route")

    include, err = planned(watchlist, down, capsys)
    assert include == [] and "::warning::" in err and "no route" in err


def test_an_honest_empty_calendar_day_is_not_a_warning(watchlist, capsys):
    include, err = planned(watchlist, lambda url: calendar(match(home="1", away="2")), capsys)
    assert include == [] and err == ""


def test_the_match_of_wednesday_25_11_is_planned_with_the_real_watchlist():
    watch = json.loads(WATCHLIST.read_text(encoding="utf-8"))
    wednesday = match(home="39704", away="40098", day="2026-11-25 20:30:00")          # Factufix Venta de Baños - Pucela, the only match that week
    kick_off = datetime(2026, 11, 25, 19, 30, tzinfo=timezone.utc)
    groups = {str(g) for g in watch["groups"]}
    assert groups, "a watchlist without groups plans nothing"
    assert rec.plan({**watch, "groups": [GROUP]}, kick_off, lambda g: [wednesday])


class TestTheRequestsAreMadeAsABrowserDoes:
    """Real cause of the unrecorded match of 21/11/2026 (#446), found on 23/11: the recorder asked with ``requests.get(url)`` and NO headers, and the servers of FBCYL (the ESB calendar, the stats and the
    streaming) close the connection without an answer to the default agent of ``requests`` (measured on 23/11: ``ConnectionError`` without headers and HTTP 200 with a plain ``Mozilla/5.0`` for the
    calendar, the moves, the stats and the live feed). The planner then planned nothing and the recorder could not have read anything either."""

    def test_every_request_of_the_recorder_carries_a_browser_user_agent(self, monkeypatch):
        seen = []

        class Answer:
            status_code, headers, content = 200, {}, b"{}"

        monkeypatch.setattr("requests.get", lambda url, **kw: seen.append(kw) or Answer())
        response = rec.http_get("https://esb.optimalwayconsulting.com/x")
        agent = seen[0]["headers"]["User-Agent"]
        assert response.status == 200 and agent.startswith("Mozilla/5.0") and "python-requests" not in agent

    def test_the_agent_names_no_project_and_no_person(self, monkeypatch):
        seen = []

        class Answer:
            status_code, headers, content = 200, {}, b""

        monkeypatch.setattr("requests.get", lambda url, **kw: seen.append(kw) or Answer())
        rec.http_get("https://x")
        assert set(seen[0]["headers"]) == {"User-Agent"} and "basketlab" not in seen[0]["headers"]["User-Agent"].lower()
