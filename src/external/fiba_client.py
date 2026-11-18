"""The client of the public site of FIBA (#887, D3b of epic #872): polite, patient and honest about what went wrong.

* **Polite**: at most one request every ``pause`` seconds (2 by default) whatever the caller does, a generic user agent that names no project and no key: the site is public and is asked as a person would, slowly.
* **Patient**: a page that comes back generic (the version of the site with no data of the game, seen 2 times in ~10 requests by the spike #915), cut in the middle, with a server error or lost to the network is asked
  again after a wait that doubles each time (``pause`` x 2, x 4, x 8), up to ``attempts`` times.
* **Honest**: a page that is not there (404) is ``FibaNotFound`` and a request the site refuses (403 and the like) is ``FibaFetchError``, neither is asked again; a page whose FORMAT the reader does not know
  (``FibaPageError``) is raised as it is, because asking again would not change it and it has to be seen; and a page that stays generic ends in ``FibaFetchError``, never in half a game.

The network is injected (``fetch``, ``sleep``, ``clock``) so the tests serve the real pages of ``tests/fixtures/fiba`` and see the pauses without waiting.
"""
from __future__ import annotations

import time
import urllib.error
import urllib.request
from typing import Any, Callable, Dict, List, TypeVar

from src.external.fiba_page import CutPage, FibaPageError, GenericPage, extract_flight, parse_event_games, parse_game

BASE = "https://www.fiba.basketball/en/events"
USER_AGENT = "Mozilla/5.0 (compatible; basketball-research-bot/1.0)"          # generic on purpose: no name of the project goes to an outside service
PAUSE_S = 2.0
ATTEMPTS = 4
TIMEOUT_S = 40
T = TypeVar("T")


class FibaFetchError(OSError):
    """A page could not be had: refused, lost to the network or generic after every attempt."""


class FibaNotFound(FibaFetchError):
    """The page does not exist (an event or a game that is not there)."""


def _fetch(url: str, user_agent: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": user_agent, "Accept-Language": "en"})
    with urllib.request.urlopen(request, timeout=TIMEOUT_S) as response:                 # a redirect to the page with the slug is followed
        return response.read().decode("utf-8", "replace")


class FibaClient:
    def __init__(self, fetch: Callable[[str, str], str] = _fetch, sleep: Callable[[float], None] = time.sleep, clock: Callable[[], float] = time.monotonic,
                 pause: float = PAUSE_S, attempts: int = ATTEMPTS, user_agent: str = USER_AGENT) -> None:
        self.fetch, self.sleep, self.clock = fetch, sleep, clock
        self.pause, self.attempts, self.user_agent = pause, attempts, user_agent
        self._last: Any = None

    def _throttle(self) -> None:
        """Never two requests closer than ``pause``, whoever asks."""
        if self._last is not None:
            wait = self.pause - (self.clock() - self._last)
            if wait > 0:
                self.sleep(wait)
        self._last = self.clock()

    def _ask(self, url: str, read: Callable[[str], T]) -> T:
        last: Exception = FibaFetchError(url)
        for attempt in range(1, self.attempts + 1):
            self._throttle()
            try:
                return read(self.fetch(url, self.user_agent))
            except (GenericPage, CutPage) as error:
                last = error                                                   # the version with no data, or a page that ended early: ask again
            except FibaPageError:
                raise                                                          # a format the reader does not know: asking again would not change it
            except urllib.error.HTTPError as error:
                if error.code == 404:
                    raise FibaNotFound(f"{url} does not exist") from error
                if error.code < 500 and error.code != 429:
                    raise FibaFetchError(f"HTTP {error.code} for {url}") from error
                last = error
            except OSError as error:                                           # URLError, time out, connection reset
                last = error
            if attempt < self.attempts:
                self.sleep(self.pause * 2 ** attempt)
        raise FibaFetchError(f"{url}: {self.attempts} attempts, the last one: {type(last).__name__}: {last}") from last

    def event_games(self, event: str) -> List[Dict[str, Any]]:
        """The games an event lists (``fiba_page.parse_event_games``)."""
        return self._ask(f"{BASE}/{event}", lambda html: parse_event_games(extract_flight(html)))

    def game(self, event: str, slug: str) -> Dict[str, Any]:
        """A finished game as ``fiba_page.parse_game`` reads it."""
        return self._ask(f"{BASE}/{event}/games/{slug}", lambda html: parse_game(extract_flight(html)))
