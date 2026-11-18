"""The client of the public site of FIBA (#887, D3b): polite, patient and honest about what went wrong.

Polite: one request every 2 seconds at most, with an identifiable user agent and no key. Patient: a page that comes back generic (seen 2 times in ~10 requests by the spike #915), cut or lost to the network is asked
again with a longer wait each time. Honest: a page that is not there (404) or whose format the reader does not know is NOT retried and says so, and a page that stays generic ends in an error, never in half a game.
The site is a fake that serves the REAL pages of ``tests/fixtures/fiba`` as HTML.
"""
import urllib.error

import pytest

from fiba_helpers import Clock, Site, flight, html_of

from src.external.fiba_client import FibaClient, FibaFetchError, FibaNotFound
from src.external.fiba_page import FibaPageError, extract_flight, parse_event_games

GAME = "/en/events/fiba-u18-eurobasket-2025/games/125809-FRA-AUT"
EVENT = "/en/events/fiba-u18-eurobasket-2025"
EVENT_NAME, SLUG = "fiba-u18-eurobasket-2025", "125809-FRA-AUT"


def client(site, clock=None, **options):
    clock = clock or Clock()
    return FibaClient(fetch=site.fetch, sleep=clock.sleep, clock=clock.time, **options), clock


def test_the_pages_of_the_fake_site_are_the_real_ones_as_the_site_serves_them():
    assert extract_flight(html_of(flight("125809"))) == flight("125809")


class TestAGame:
    def test_it_fetches_the_page_of_the_game_and_reads_it(self):
        site = Site({GAME: html_of(flight("125809"))})
        game = client(site)[0].game(EVENT_NAME, SLUG)
        assert game["game_id"] == 125809 and [t["score"] for t in game["teams"]] == [95, 56]
        assert [url for url, _ in site.requests] == [f"https://www.fiba.basketball{GAME}"]

    def test_it_is_a_generic_agent_that_names_no_project_and_sends_no_key(self):
        site = Site({GAME: html_of(flight("125809"))})
        client(site)[0].game(EVENT_NAME, SLUG)
        agent = site.requests[0][1]
        assert "research" in agent and "key" not in agent.lower()
        assert "basketlab" not in agent.lower()                                  # no name of the project goes to an outside service

    def test_a_page_that_comes_back_generic_is_asked_again_after_a_pause(self):
        site = Site({GAME: [html_of(flight("fiba-u18-eurobasket-2025")), html_of(flight("125809"))]})            # the first answer is the page of an event: no game in it
        cli, clock = client(site)
        assert cli.game(EVENT_NAME, SLUG)["game_id"] == 125809
        assert len(site.requests) == 2 and clock.slept and all(s >= 2 for s in clock.slept)

    def test_a_page_that_stays_generic_ends_in_an_error_after_every_attempt_not_in_half_a_game(self):
        site = Site({GAME: html_of(flight("fiba-u18-eurobasket-2025"))})
        cli, _ = client(site, attempts=3)
        with pytest.raises(FibaFetchError, match="generic|3 attempts"):
            cli.game(EVENT_NAME, SLUG)
        assert len(site.requests) == 3

    def test_each_wait_is_longer_than_the_one_before(self):
        generic = html_of(flight("fiba-u18-eurobasket-2025"))
        site = Site({GAME: [generic, generic, html_of(flight("125809"))]})
        cli, clock = client(site)
        cli.game(EVENT_NAME, SLUG)
        waits = [s for s in clock.slept if s > 2]
        assert len(waits) >= 2 and waits == sorted(waits) and waits[0] < waits[-1]

    def test_a_page_cut_in_the_middle_is_asked_again_too(self):
        text = flight("125809")
        cut = html_of(text[: text.index('"gameDetails":') + 40])
        site = Site({GAME: [cut, html_of(text)]})
        assert client(site)[0].game(EVENT_NAME, SLUG)["game_id"] == 125809 and len(site.requests) == 2

    def test_the_network_failing_is_asked_again_and_a_time_out_ends_in_an_error(self):
        site = Site({GAME: [TimeoutError("slow"), urllib.error.URLError("down"), html_of(flight("125809"))]})
        assert client(site)[0].game(EVENT_NAME, SLUG)["game_id"] == 125809
        dead = Site({GAME: TimeoutError("slow")})
        with pytest.raises(FibaFetchError, match="slow"):
            client(dead, attempts=2)[0].game(EVENT_NAME, SLUG)
        assert len(dead.requests) == 2

    def test_a_page_that_is_not_there_is_not_asked_again(self):
        site = Site({GAME: urllib.error.HTTPError("u", 404, "Not Found", {}, None)})
        with pytest.raises(FibaNotFound):
            client(site)[0].game(EVENT_NAME, SLUG)
        assert len(site.requests) == 1

    def test_an_error_of_the_server_is_asked_again_but_one_of_the_client_is_not(self):
        server = Site({GAME: [urllib.error.HTTPError("u", 503, "Unavailable", {}, None), html_of(flight("125809"))]})
        assert client(server)[0].game(EVENT_NAME, SLUG)["game_id"] == 125809
        forbidden = Site({GAME: urllib.error.HTTPError("u", 403, "Forbidden", {}, None)})
        with pytest.raises(FibaFetchError, match="403"):
            client(forbidden)[0].game(EVENT_NAME, SLUG)
        assert len(forbidden.requests) == 1

    def test_a_page_whose_format_the_reader_does_not_know_is_not_asked_again_it_has_to_be_seen(self):
        odd = flight("125809").replace('"gameDetails":{"c":', '"gameDetails":{"d":', 1)
        site = Site({GAME: html_of(odd)})
        with pytest.raises(FibaPageError):
            client(site)[0].game(EVENT_NAME, SLUG)
        assert len(site.requests) == 1


class TestAnEvent:
    def test_it_lists_the_games_of_the_event(self):
        site = Site({EVENT: html_of(flight("fiba-u18-eurobasket-2025"))})
        games = client(site)[0].event_games(EVENT_NAME)
        assert len(games) == 56 and games == parse_event_games(flight("fiba-u18-eurobasket-2025")) and games[0]["slug"] == "125812-SWE-FRA"

    def test_a_generic_page_is_asked_again_for_an_event_too(self):
        site = Site({EVENT: [html_of('{"nothing": 1}'), html_of(flight("fiba-u18-eurobasket-2025"))]})
        assert len(client(site)[0].event_games(EVENT_NAME)) == 56 and len(site.requests) == 2

    def test_an_event_that_does_not_exist_says_so(self):
        site = Site({"/en/events/fiba-nothing-2030": urllib.error.HTTPError("u", 404, "Not Found", {}, None)})
        with pytest.raises(FibaNotFound):
            client(site)[0].event_games("fiba-nothing-2030")


class TestPoliteness:
    def test_two_requests_are_never_closer_than_the_pause(self):
        site = Site({GAME: html_of(flight("125809")), EVENT: html_of(flight("fiba-u18-eurobasket-2025"))})
        cli, clock = client(site)
        times, original = [], site.fetch
        site.fetch = lambda url, agent: (times.append(clock.time()), original(url, agent))[1]
        cli.fetch = site.fetch
        cli.event_games(EVENT_NAME)
        cli.game(EVENT_NAME, SLUG)
        cli.game(EVENT_NAME, SLUG)
        assert len(times) == 3 and all(b - a >= 2 for a, b in zip(times, times[1:]))

    def test_the_pause_and_the_attempts_are_the_ones_agreed(self):
        cli, _ = client(Site({}))
        assert (cli.pause, cli.attempts) == (2.0, 4)

    def test_a_longer_pause_can_be_asked_for(self):
        site = Site({GAME: html_of(flight("125809"))})
        cli, clock = client(site, pause=5.0)
        cli.game(EVENT_NAME, SLUG)
        cli.game(EVENT_NAME, SLUG)
        assert sum(clock.slept) >= 5.0
