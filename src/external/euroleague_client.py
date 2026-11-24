"""The client of the public API of the Euroleague (#1038, D6a of epic #872): polite, patient and honest, like the ones of FIBA, ACB and ESPN.

* **Polite**: at most one request every ``PAUSE_S`` (half a second: the API answers 429, Cloudflare error 1015, from about 8 requests a second, and three a second ran for hundreds with no block) whatever the
  caller does, and a **budget of requests per run** (``max_requests``, retries included): when it is spent ``EuroleagueBudgetExhausted`` is raised and the next run goes on where this one stopped. The user
  agent is a plain browser one: it names no project and the API has no key.
* **Patient**: an answer with a server error, lost to the network or that is not JSON is asked again after a wait that doubles; a 429 is waited out for much longer (``BLOCKED_WAIT_S``: the block lasts about
  two minutes), up to ``attempts`` times.
* **Honest**: a page that is not there (404) is ``EuroleagueNotFound`` and a request the API refuses (403 and the like) is ``EuroleagueFetchError``, neither asked again; an answer whose FORMAT the reader does
  not know (``EuroleaguePageError``) is raised as it is, because asking again would not change it and it has to be seen.

A game is three requests (the box with the bio of its players, the play by play and the shots). The network is injected (``fetch``, ``sleep``, ``clock``) so the tests serve the real answers of
``tests/fixtures/euroleague`` and see the pauses without waiting.
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Any, Callable, Dict, List, Optional, TypeVar

from src.external.euroleague_page import EuroleaguePageError, parse_game, parse_games, parse_play_by_play, parse_points, parse_seasons, parse_stats

V2 = "https://api-live.euroleague.net/v2/competitions"
LIVE = "https://live.euroleague.net/api"
USER_AGENT = "Mozilla/5.0"                     # plain on purpose: it names no project and no bot
PAUSE_S = 0.5
BLOCKED_WAIT_S = 60.0
ATTEMPTS = 4
TIMEOUT_S = 40
T = TypeVar("T")


class EuroleagueFetchError(OSError):
    """An answer could not be had: refused, lost to the network or not JSON after every attempt."""


class EuroleagueNotFound(EuroleagueFetchError):
    """The page does not exist."""


class EuroleagueBudgetExhausted(EuroleagueFetchError):
    """The requests of the run are spent: the rest waits for the next one."""


def _fetch(url: str, user_agent: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": user_agent})
    with urllib.request.urlopen(request, timeout=TIMEOUT_S) as response:
        return response.read().decode("utf-8", "replace")


class EuroleagueClient:
    def __init__(self, fetch: Callable[[str, str], str] = _fetch, sleep: Callable[[float], None] = time.sleep, clock: Callable[[], float] = time.monotonic,
                 pause: float = PAUSE_S, attempts: int = ATTEMPTS, max_requests: Optional[int] = None) -> None:
        self.fetch, self.sleep, self.clock = fetch, sleep, clock
        self.pause, self.attempts, self.max_requests = pause, attempts, max_requests
        self.requests = 0
        self._last: Any = None

    def __repr__(self) -> str:
        return f"EuroleagueClient(requests={self.requests}, max_requests={self.max_requests})"

    def _throttle(self) -> None:
        """Never two requests closer than ``pause``, whoever asks."""
        if self._last is not None:
            wait = self.pause - (self.clock() - self._last)
            if wait > 0:
                self.sleep(wait)
        self._last = self.clock()

    def _ask(self, url: str, read: Callable[[Any], T]) -> T:
        last: Exception = EuroleagueFetchError(url)
        for attempt in range(1, self.attempts + 1):
            if self.max_requests is not None and self.requests >= self.max_requests:
                raise EuroleagueBudgetExhausted(f"{self.requests} requests: the budget of the run is spent")
            self._throttle()
            self.requests += 1
            wait = self.pause * 2 ** attempt
            try:
                return read(json.loads(self.fetch(url, USER_AGENT)))
            except EuroleaguePageError:
                raise                                                          # a format the reader does not know: asking again would not change it
            except urllib.error.HTTPError as error:
                if error.code == 404:
                    raise EuroleagueNotFound(f"{url} does not exist") from error
                if error.code < 500 and error.code != 429:
                    raise EuroleagueFetchError(f"HTTP {error.code} for {url}") from error
                last, wait = error, BLOCKED_WAIT_S * attempt if error.code == 429 else wait
            except (OSError, ValueError) as error:                             # URLError, time out, connection reset, a JSON cut in the middle
                last = error
            if attempt < self.attempts:
                self.sleep(wait)
        raise EuroleagueFetchError(f"{url}: {self.attempts} attempts, the last one: {type(last).__name__}: {last}") from last

    def seasons(self, competition: str) -> List[Dict[str, Any]]:
        """The seasons of a competition (``E``, ``U`` or ``J``), ``euroleague_page.parse_seasons``."""
        return self._ask(f"{V2}/{competition}/seasons?limit=200", parse_seasons)

    def games(self, competition: str, season: str) -> List[Dict[str, Any]]:
        """The calendar of a season (``E2025``), ``euroleague_page.parse_games``: the games played and the ones to come."""
        return self._ask(f"{V2}/{competition}/seasons/{season}/games?limit=1000", parse_games)

    def game(self, competition: str, line: Dict[str, Any]) -> Dict[str, Any]:
        """A played game whole (``euroleague_page.parse_game``): ``line`` is its line of the calendar. Three requests."""
        season, code = line["season_code"], line["game_code"]
        stats = self._ask(f"{V2}/{competition}/seasons/{season}/games/{code}/stats", lambda d: (parse_stats(d), d)[1])
        played = self._ask(f"{LIVE}/PlayByPlay?gamecode={code}&seasoncode={season}", lambda d: (parse_play_by_play(d), d)[1])
        shots = self._ask(f"{LIVE}/Points?gamecode={code}&seasoncode={season}", lambda d: (parse_points(d), d)[1])
        return parse_game(line, stats, played, shots)
