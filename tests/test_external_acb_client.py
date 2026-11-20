"""The client of the public pages and the calendar API of ACB (#886, D2b of epic #872).

The pages served are the REAL ones of ``tests/fixtures/acb`` (captured by ``scripts/capture_acb_fixtures.py``: a game of 2026/27 and one of 2019/20, a player and the calendar answers); the network, the
sleep and the clock are injected, so the pauses are seen without waiting. The key of the API is a fake one in the shape of the real chunk of JavaScript: no test (and no fixture) has the real one.
"""
import gzip
import json
import urllib.error
from pathlib import Path

import pytest

from src.external.acb_client import (API_BASE, PAUSE_S, AcbBudgetExhausted, AcbClient, AcbFetchError, AcbNotFound, editions_of, fetch_api_key, match_url, player_url, slugify)
from src.external.acb_page import PAGE_MARKERS, CutPage, GenericPage, check_page, extract_flight

FIX = Path(__file__).parent / "fixtures" / "acb"
FAKE_KEY = "00000000-1111-2222-3333-444444444444"


def flight(name: str) -> str:
    return gzip.decompress((FIX / f"{name}.flight.gz").read_bytes()).decode("utf-8")


def html_of(flight_text: str) -> str:
    """A page whose Next data chunks hold ``flight_text`` (what the site serves, in one chunk)."""
    return f'<html><script>self.__next_f.push([1,{json.dumps(flight_text)}])</script></html>'


PAGES = {"105383.jugadas": "jugadas", "105383.estadisticas": "estadisticas", "18665.jugadas": "jugadas", "player.temporada": "temporada", "player.zonas-de-tiro": "zonas-de-tiro"}


class Net:
    """A fake network: answers by URL (a text, an exception, or a list of them to give in turn) and remembers every request and every pause."""

    def __init__(self, answers):
        self.answers, self.requests, self.sleeps, self.now = dict(answers), [], [], 0.0

    def fetch(self, url, headers):
        self.requests.append((url, dict(headers)))
        answer = self.answers[url]
        if isinstance(answer, list):
            answer = answer.pop(0) if len(answer) > 1 else answer[0]
        if isinstance(answer, Exception):
            raise answer
        return answer

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds

    def clock(self):
        return self.now

    def client(self, **kwargs):
        return AcbClient(fetch=self.fetch, sleep=self.sleep, clock=self.clock, api_key=lambda: FAKE_KEY, **kwargs)


def http_error(code):
    return urllib.error.HTTPError("https://example.invalid", code, "x", {}, None)


GAME = "real-madrid-vs-unicaja-105383"
GAME_URL = f"https://live.acb.com/partidos/{GAME}/jugadas"


@pytest.mark.parametrize("name, kind", list(PAGES.items()))
def test_every_real_page_has_the_marker_of_its_kind_and_a_page_without_it_is_cut(name, kind):
    text = flight(name)
    check_page(kind, text)                                                  # the real page passes
    assert PAGE_MARKERS[kind] in text
    with pytest.raises(CutPage):
        check_page(kind, text[: text.index(PAGE_MARKERS[kind])])           # the same page ended before its data


def test_a_page_with_no_data_chunks_is_generic():
    with pytest.raises(GenericPage):
        extract_flight("<html><body>maintenance</body></html>")


@pytest.mark.parametrize("name, expected", [("Real Madrid", "real-madrid"), ("Valencia Basket Club", "valencia-basket-club"), ("Leyma Coruña", "leyma-coruna"), ("Surne Bilbao Basket", "surne-bilbao-basket"),
                                            ("Hereda San Pablo Burgos", "hereda-san-pablo-burgos"), ("  Barça  ", "barca")])
def test_the_slug_of_a_team_is_its_name_without_accents_in_lowercase_with_hyphens(name, expected):
    assert slugify(name) == expected


def test_the_urls_are_the_ones_of_the_site():
    assert match_url("Real Madrid", "Unicaja", 105383, "jugadas") == GAME_URL
    assert player_url("Amine", "Noua", 30001137, "zonas-de-tiro") == "https://acb.com/es/liga/jugadores/amine-noua-30001137/zonas-de-tiro"


def test_it_returns_the_flight_of_a_real_game_and_asks_with_a_generic_user_agent_and_no_key():
    net = Net({GAME_URL: html_of(flight("105383.jugadas"))})
    text = net.client().match_page("Real Madrid", "Unicaja", 105383, "jugadas")
    assert text == flight("105383.jugadas")
    headers = net.requests[0][1]
    assert "X-APIKEY" not in headers and "basketlab" not in headers["User-Agent"].lower() and "Mozilla" in headers["User-Agent"]


def test_the_game_of_2019_20_has_its_plays_too():
    url = "https://live.acb.com/partidos/barca-vs-valencia-basket-club-18665/jugadas"
    assert "plays" in Net({url: html_of(flight("18665.jugadas"))}).client().match_page("Barça", "Valencia Basket Club", 18665, "jugadas")[:2_000_000]


def test_it_never_asks_twice_within_the_pause_whatever_the_caller_does():
    net = Net({GAME_URL: html_of(flight("105383.jugadas"))})
    client = net.client()
    client.match_page("Real Madrid", "Unicaja", 105383, "jugadas")
    client.match_page("Real Madrid", "Unicaja", 105383, "jugadas")
    assert PAUSE_S == 1.0 and net.sleeps == [PAUSE_S]                       # the first one does not wait; the second waits the whole pause


def test_a_page_that_comes_back_without_its_data_is_asked_again_after_a_wait_that_doubles():
    net = Net({GAME_URL: [html_of("{}"), html_of("{}"), html_of(flight("105383.jugadas"))]})
    assert net.client().match_page("Real Madrid", "Unicaja", 105383, "jugadas") == flight("105383.jugadas")
    assert len(net.requests) == 3
    assert net.sleeps == [PAUSE_S * 2, PAUSE_S * 4]                         # the waits double: x2, then x4 (the pause between requests is already spent)


def test_a_page_that_never_comes_with_its_data_ends_in_an_honest_error_after_the_attempts():
    net = Net({GAME_URL: html_of("{}")})
    with pytest.raises(AcbFetchError, match="4 attempts"):
        net.client().match_page("Real Madrid", "Unicaja", 105383, "jugadas")
    assert len(net.requests) == 4


@pytest.mark.parametrize("code, error, asked", [(404, AcbNotFound, 1), (403, AcbFetchError, 1), (500, AcbFetchError, 4), (429, AcbFetchError, 4)])
def test_what_the_site_answers_decides_whether_it_is_asked_again(code, error, asked):
    net = Net({GAME_URL: http_error(code)})
    with pytest.raises(error):
        net.client().match_page("Real Madrid", "Unicaja", 105383, "jugadas")
    assert len(net.requests) == asked


def test_a_network_failure_is_asked_again_and_then_reported():
    net = Net({GAME_URL: [urllib.error.URLError("reset"), html_of(flight("105383.jugadas"))]})
    assert net.client().match_page("Real Madrid", "Unicaja", 105383, "jugadas") == flight("105383.jugadas")


def test_the_budget_of_requests_is_a_limit_of_the_run_and_the_next_one_goes_on():
    net = Net({GAME_URL: html_of(flight("105383.jugadas"))})
    client = net.client(max_requests=2)
    client.match_page("Real Madrid", "Unicaja", 105383, "jugadas")
    client.match_page("Real Madrid", "Unicaja", 105383, "jugadas")
    with pytest.raises(AcbBudgetExhausted):
        client.match_page("Real Madrid", "Unicaja", 105383, "jugadas")
    assert len(net.requests) == 2 and client.requests == 2


def test_the_retries_count_in_the_budget_too():
    net = Net({GAME_URL: html_of("{}")})
    client = net.client(max_requests=3)
    with pytest.raises(AcbBudgetExhausted):
        client.match_page("Real Madrid", "Unicaja", 105383, "jugadas")
    assert len(net.requests) == 3


def test_the_player_pages_give_the_bio_and_the_shots_with_their_coordinates():
    net = Net({"https://acb.com/es/liga/jugadores/amine-noua-30001137/temporada": html_of(flight("player.temporada")),
               "https://acb.com/es/liga/jugadores/amine-noua-30001137/zonas-de-tiro": html_of(flight("player.zonas-de-tiro"))})
    client = net.client()
    assert '"birthDate":"07-02-1997"' in client.player_page("Amine", "Noua", 30001137, "temporada")
    assert '"posX"' in client.player_page("Amine", "Noua", 30001137, "zonas-de-tiro")


def test_the_calendar_comes_from_the_api_with_the_key_and_the_key_is_not_in_an_error():
    answer = (FIX / "team-matches.json").read_text(encoding="utf-8")
    url = f"{API_BASE}/api/seasondata/TeamProfile/team-matches?clubId=9&competitionId=1&editionId=91"
    net = Net({url: answer})
    matches = net.client().team_matches(9, 91)
    assert len(matches) == 34 and {"FINALIZED", "NOT_STARTED"} <= {m["matchStatus"] for m in matches} and all("id" in m for m in matches)
    assert net.requests[0][1]["X-APIKEY"] == FAKE_KEY
    failing = Net({url: http_error(403)})
    with pytest.raises(AcbFetchError) as caught:
        failing.client().team_matches(9, 91)
    assert FAKE_KEY not in str(caught.value) and FAKE_KEY not in repr(failing.client())


def test_the_teams_of_an_edition_say_their_club_ids():
    url = f"{API_BASE}/api/seasondata/TeamProfile/teams?competitionId=1&editionId=91"
    clubs = Net({url: (FIX / "teams.json").read_text(encoding="utf-8")}).client().teams(91)
    assert len(clubs) == 18 and all(isinstance(c["clubId"], int) and c["fullName"] for c in clubs)


def test_the_key_is_read_from_the_public_javascript_on_each_run_and_kept_only_in_memory():
    page = "https://acb.com/es/liga/equipos/real-madrid-9/partidos?editionId=91"
    html = '<script src="/_next/static/chunks/aaa.js"></script><script src="/_next/static/chunks/bbb.js"></script>'
    net = Net({page: html, "https://acb.com/_next/static/chunks/aaa.js": "var a=1;", "https://acb.com/_next/static/chunks/bbb.js": f'x={{baseUrl:"https://api2.acb.com",apiKey:"{FAKE_KEY}",options:{{}}}}'})
    assert fetch_api_key(net.fetch, net.sleep) == FAKE_KEY
    assert all("X-APIKEY" not in h for _, h in net.requests)


def test_a_site_whose_javascript_has_no_key_any_more_says_so_instead_of_asking_without_it():
    page = "https://acb.com/es/liga/equipos/real-madrid-9/partidos?editionId=91"
    net = Net({page: '<script src="/_next/static/chunks/aaa.js"></script>', "https://acb.com/_next/static/chunks/aaa.js": "var a=1;"})
    with pytest.raises(AcbFetchError, match="key"):
        fetch_api_key(net.fetch, net.sleep)


def test_the_editions_of_a_competition_are_read_from_the_real_answer_by_their_year_and_are_not_a_formula():
    answer = json.loads((FIX / "teams.json").read_text(encoding="utf-8"))
    editions = editions_of(answer)
    assert editions[2019] == 84 and editions[2026] == 91 and editions[1983] == 48
    assert editions_of({"availableFilters": {"seasons": [{"id": 5, "seasonStartYear": 2001}, {"id": 6}]}}) == {2001: 5}          # one without its year is left out, never guessed
    url = f"{API_BASE}/api/seasondata/TeamProfile/teams?competitionId=1"
    assert Net({url: (FIX / "teams.json").read_text(encoding="utf-8")}).client().editions()[2023] == 88
