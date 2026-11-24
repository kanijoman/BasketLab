"""The client of ESPN for the NCAA (#888, D4): polite, patient and honest, like the ones of FIBA and ACB, with what ESPN asked of it.

Measured on 23/11/2026: ESPN answers 403 to a user agent that names a bot (the one of FIBA's client) and 200 to a plain browser one, so that is what is sent (it names no project and no key).
"""
from http.client import IncompleteRead
import urllib.error

import pytest

from ncaa_helpers import Clock, Site, text

from src.external.ncaa_client import NcaaBudgetExhausted, NcaaClient, NcaaFetchError, NcaaNotFound
from src.external.ncaa_page import NcaaPageError

CONFERENCES = "/scoreboard/conferences"
STANDINGS = "/standings"


def client(site, clock=None, **options):
    clock = clock or Clock()
    return NcaaClient(fetch=site.fetch, sleep=clock.sleep, clock=clock.time, **options), clock


def http(code):
    return urllib.error.HTTPError("u", code, "x", {}, None)


def test_it_reads_the_conferences_of_a_season_with_the_url_of_its_sex_and_season():
    site = Site({CONFERENCES: text("conferences_mens_2026")})
    conferences = client(site)[0].conferences("M", 2025)
    assert len(conferences) == 31
    assert site.requests[0][0] == "https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/scoreboard/conferences?season=2026"          # the season of ESPN is the year it ends in


def test_it_reads_the_standings_of_the_women_with_their_own_url():
    site = Site({STANDINGS: text("standings_womens_2027")})
    teams = client(site)[0].standings("F", 2026)
    assert teams and "womens-college-basketball/standings?group=50&level=2&season=2027" in site.requests[0][0]


def test_the_user_agent_is_a_plain_browser_one_that_names_no_project_and_no_bot():
    site = Site({CONFERENCES: text("conferences_mens_2026")})
    client(site)[0].conferences("M", 2025)
    agent = site.requests[0][1]
    assert agent == "Mozilla/5.0" and "bot" not in agent.lower() and "basketlab" not in agent.lower()


def test_two_requests_are_never_closer_than_the_pause():
    site = Site({CONFERENCES: text("conferences_mens_2026"), STANDINGS: text("standings_mens_2026")})
    c, clock = client(site, pause=1.0)
    c.conferences("M", 2025)
    c.standings("M", 2025)
    assert clock.sleeps == [1.0]


def test_a_server_error_is_asked_again_after_a_wait_that_doubles_and_then_it_works():
    site = Site({CONFERENCES: [http(500), http(429), text("conferences_mens_2026")]})
    c, clock = client(site, pause=1.0)
    assert len(c.conferences("M", 2025)) == 31 and len(site.requests) == 3
    assert clock.sleeps[-2:] == [2.0, 4.0]


def test_a_response_cut_short_is_asked_again_and_if_it_never_comes_whole_it_is_a_fetch_error_regression():
    """#1088: the NCAA batch of 24/11/2026 died with ``IncompleteRead(645685 bytes read)`` after ~20 minutes: ``http.client.HTTPException`` is not an ``OSError``, so it skipped the retries and the whole run."""
    cut = IncompleteRead(b"x" * 10)
    c, _ = client(Site({CONFERENCES: [cut, text("conferences_mens_2026")]}))
    assert len(c.conferences("M", 2025)) == 31
    c, _ = client(Site({CONFERENCES: cut}), attempts=3)
    with pytest.raises(NcaaFetchError, match="IncompleteRead"):
        c.conferences("M", 2025)


def test_a_page_that_is_not_there_is_not_asked_again_and_a_request_that_is_refused_says_so():
    c, _ = client(Site({CONFERENCES: http(404)}))
    with pytest.raises(NcaaNotFound):
        c.conferences("M", 2025)
    refused = Site({CONFERENCES: http(403)})
    with pytest.raises(NcaaFetchError, match="403"):
        client(refused)[0].conferences("M", 2025)
    assert len(refused.requests) == 1


def test_an_answer_that_is_not_json_is_asked_again_and_ends_in_an_error_never_in_half_an_answer():
    site = Site({CONFERENCES: "<html>busy</html>"})
    with pytest.raises(NcaaFetchError):
        client(site, attempts=3)[0].conferences("M", 2025)
    assert len(site.requests) == 3


def test_an_answer_whose_format_the_reader_does_not_know_is_raised_as_it_is_and_not_asked_again():
    site = Site({CONFERENCES: "{}"})
    with pytest.raises(NcaaPageError):
        client(site)[0].conferences("M", 2025)
    assert len(site.requests) == 1


def test_the_budget_of_a_run_counts_every_request_retries_included_and_stops_the_run_when_it_is_spent():
    site = Site({CONFERENCES: [http(500), text("conferences_mens_2026")], STANDINGS: text("standings_mens_2026")})
    c, _ = client(site, max_requests=2)
    c.conferences("M", 2025)                           # two requests: the failed one and the good one
    with pytest.raises(NcaaBudgetExhausted):
        c.standings("M", 2025)
    assert len(site.requests) == 2 and "requests=2" in repr(c)


def test_it_reads_the_scoreboard_of_a_day_with_the_url_of_its_sex_and_the_division():
    site = Site({"/scoreboard?dates=20260115": text("scoreboard_mens_20260115")})
    games = client(site)[0].scoreboard("M", "2026-01-15")
    assert len(games) == 49 and "mens-college-basketball/scoreboard?dates=20260115&groups=50&limit=400" in site.requests[0][0]


def test_it_reads_a_game_with_the_url_of_its_sex():
    from ncaa_helpers import text as raw

    site = Site({"/summary?event=401825641": raw("game_womens_401825641")})
    game = client(site)[0].game("F", "401825641")
    assert game["game_id"] == "401825641" and "womens-college-basketball/summary?event=401825641" in site.requests[0][0]
