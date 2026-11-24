"""The client of the public API of the Euroleague (#1038, D6a): polite, patient and honest, like the ones of FIBA, ACB and ESPN, with what the API asked of it.

Measured on 23/11/2026: the API answers 429 (Cloudflare, error 1015) from about 8 requests a second and recovers in about 2 minutes; three a second ran for hundreds of requests with no block. So the pause
is half a second at least and a 429 is waited out for much longer than a server error.
"""
from http.client import IncompleteRead
import urllib.error

import pytest

from euroleague_helpers import Clock, Site, listed, text

from src.external.euroleague_client import EuroleagueBudgetExhausted, EuroleagueClient, EuroleagueFetchError, EuroleagueNotFound
from src.external.euroleague_page import EuroleaguePageError

SEASONS = "/competitions/J/seasons?"
GAMES = "/competitions/E/seasons/E2025/games?"
GAME = {"stats": "/games/1/stats", "pbp": "/PlayByPlay?", "points": "/Points?"}


def client(site, clock=None, **options):
    clock = clock or Clock()
    return EuroleagueClient(fetch=site.fetch, sleep=clock.sleep, clock=clock.time, **options), clock


def http(code):
    return urllib.error.HTTPError("u", code, "x", {}, None)


def game_site():
    return Site({GAME["stats"]: text("E2025_1.stats"), GAME["pbp"]: text("E2025_1.pbp"), GAME["points"]: text("E2025_1.points")})


def test_it_reads_the_seasons_of_a_competition_and_the_games_of_a_season():
    site = Site({SEASONS: text("seasons_J"), GAMES: text("games_E2025")})
    c = client(site)[0]
    assert any(s["code"] == "JTA25" for s in c.seasons("J"))
    assert [g["game_code"] for g in c.games("E", "E2025")] == [406, 397, 1]
    assert site.requests[0][0].startswith("https://api-live.euroleague.net/v2/competitions/J/seasons")


def test_a_game_is_three_requests_to_the_two_servers_and_comes_whole():
    site = game_site()
    c = client(site)[0]
    game = c.game("E", listed("games_E2025", 1))
    assert len(site.requests) == 3 and len(game["plays"]) > 500 and len(game["shots"]) == 131
    urls = [u for u, _ in site.requests]
    assert any(u.startswith("https://api-live.euroleague.net/v2/competitions/E/seasons/E2025/games/1/stats") for u in urls)
    assert any(u == "https://live.euroleague.net/api/PlayByPlay?gamecode=1&seasoncode=E2025" for u in urls)
    assert any(u == "https://live.euroleague.net/api/Points?gamecode=1&seasoncode=E2025" for u in urls)


def test_the_user_agent_is_a_plain_browser_one_that_names_no_project_and_no_bot():
    site = Site({SEASONS: text("seasons_J")})
    client(site)[0].seasons("J")
    agent = site.requests[0][1]
    assert agent.startswith("Mozilla/5.0") and "basketlab" not in agent.lower() and "bot" not in agent.lower()


def test_two_requests_are_never_closer_than_half_a_second():
    site = Site({SEASONS: text("seasons_J")})
    c, clock = client(site)
    c.seasons("J")
    c.seasons("J")
    assert sum(clock.sleeps) >= 0.5 and min(clock.sleeps) > 0


def test_a_429_is_waited_out_for_much_longer_than_a_server_error_and_then_asked_again():
    site = Site({SEASONS: [http(429), text("seasons_J")]})
    c, clock = client(site)
    assert c.seasons("J") and len(site.requests) == 2 and max(clock.sleeps) >= 30


def test_a_server_error_is_asked_again_after_a_short_wait_that_doubles():
    site = Site({SEASONS: [http(503), OSError("reset"), text("seasons_J")]})
    c, clock = client(site)
    assert c.seasons("J") and len(site.requests) == 3 and max(clock.sleeps) < 30


def test_a_response_cut_short_is_asked_again_like_any_network_failure_regression():
    """#1088: ``IncompleteRead`` is not an ``OSError`` and used to skip the retries (found in the NCAA client)."""
    site = Site({SEASONS: [IncompleteRead(b"x"), text("seasons_J")]})
    assert client(site)[0].seasons("J") and len(site.requests) == 2


def test_a_page_that_is_not_there_is_not_found_and_a_refusal_is_a_fetch_error_neither_asked_again():
    for code, error in ((404, EuroleagueNotFound), (403, EuroleagueFetchError)):
        site = Site({SEASONS: http(code)})
        with pytest.raises(error):
            client(site)[0].seasons("J")
        assert len(site.requests) == 1


def test_after_every_attempt_it_fails_saying_so():
    site = Site({SEASONS: http(500)})
    with pytest.raises(EuroleagueFetchError, match="4 attempts"):
        client(site)[0].seasons("J")
    assert len(site.requests) == 4


def test_a_format_it_does_not_know_is_raised_as_it_is_and_not_asked_again():
    site = Site({SEASONS: '{"data": []}'})
    with pytest.raises(EuroleaguePageError):
        client(site)[0].seasons("J")
    assert len(site.requests) == 1


def test_the_budget_of_the_run_counts_every_request_retries_included_and_then_stops():
    site = Site({SEASONS: [http(500), text("seasons_J")]})
    c = client(site, max_requests=2)[0]
    c.seasons("J")
    with pytest.raises(EuroleagueBudgetExhausted):
        c.seasons("J")
    assert c.requests == 2 and len(site.requests) == 2
