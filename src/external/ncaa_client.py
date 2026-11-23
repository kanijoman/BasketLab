"""The client of ESPN for the NCAA (#888, D4 of epic #872): polite, patient and honest about what went wrong, like the ones of FIBA and ACB.

* **Polite**: at most one request every ``PAUSE_S`` whatever the caller does and a **budget of requests per run** (``max_requests``, retries included): when it is spent ``NcaaBudgetExhausted`` is
  raised and the next day's run goes on where this one stopped. The user agent is a plain browser one: ESPN answers 403 to one that names a bot (measured on 23/11/2026, the one of FIBA's client)
  and the site is public; it names no project and carries no key.
* **Patient**: an answer with a server error, a 429, lost to the network or that is not JSON (cut in the middle) is asked again after a wait that doubles (``pause`` x 2, x 4, x 8), up to ``attempts`` times.
* **Honest**: a page that is not there (404) is ``NcaaNotFound`` and a request ESPN refuses (403 and the like) is ``NcaaFetchError``, neither asked again; an answer whose FORMAT the reader does not know
  (``NcaaPageError``) is raised as it is, because asking again would not change it and it has to be seen.

The season of ESPN is the year it ENDS in (2026 is 2025/26); the client takes the year it STARTS in, as the catalogue does, and converts. The network is injected (``fetch``, ``sleep``, ``clock``) so the
tests serve the real answers of ``tests/fixtures/ncaa`` and see the pauses without waiting.
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Any, Callable, Dict, List, Optional, TypeVar

from src.external.ncaa_page import NcaaPageError, parse_conferences, parse_scoreboard, parse_standings, parse_summary

SITE = "https://site.api.espn.com/apis/site/v2/sports/basketball/{sex}-college-basketball"
SITE_V2 = "https://site.api.espn.com/apis/v2/sports/basketball/{sex}-college-basketball"
USER_AGENT = "Mozilla/5.0"                     # plain on purpose: ESPN refuses the ones that name a bot, and no name of the project goes to an outside service
PAUSE_S = 1.0
ATTEMPTS = 4
TIMEOUT_S = 40
SEXES = {"M": "mens", "F": "womens"}
T = TypeVar("T")


class NcaaFetchError(OSError):
    """An answer could not be had: refused, lost to the network or not JSON after every attempt."""


class NcaaNotFound(NcaaFetchError):
    """The page does not exist."""


class NcaaBudgetExhausted(NcaaFetchError):
    """The requests of the run are spent: the rest waits for the next one."""


def _fetch(url: str, user_agent: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": user_agent})
    with urllib.request.urlopen(request, timeout=TIMEOUT_S) as response:
        return response.read().decode("utf-8", "replace")


class NcaaClient:
    def __init__(self, fetch: Callable[[str, str], str] = _fetch, sleep: Callable[[float], None] = time.sleep, clock: Callable[[], float] = time.monotonic,
                 pause: float = PAUSE_S, attempts: int = ATTEMPTS, max_requests: Optional[int] = None) -> None:
        self.fetch, self.sleep, self.clock = fetch, sleep, clock
        self.pause, self.attempts, self.max_requests = pause, attempts, max_requests
        self.requests = 0
        self._last: Any = None

    def __repr__(self) -> str:
        return f"NcaaClient(requests={self.requests}, max_requests={self.max_requests})"

    def _throttle(self) -> None:
        """Never two requests closer than ``pause``, whoever asks."""
        if self._last is not None:
            wait = self.pause - (self.clock() - self._last)
            if wait > 0:
                self.sleep(wait)
        self._last = self.clock()

    def _ask(self, url: str, read: Callable[[Any], T]) -> T:
        last: Exception = NcaaFetchError(url)
        for attempt in range(1, self.attempts + 1):
            if self.max_requests is not None and self.requests >= self.max_requests:
                raise NcaaBudgetExhausted(f"{self.requests} requests: the budget of the run is spent")
            self._throttle()
            self.requests += 1
            try:
                return read(json.loads(self.fetch(url, USER_AGENT)))
            except NcaaPageError:
                raise                                                          # a format the reader does not know: asking again would not change it
            except urllib.error.HTTPError as error:
                if error.code == 404:
                    raise NcaaNotFound(f"{url} does not exist") from error
                if error.code < 500 and error.code != 429:
                    raise NcaaFetchError(f"HTTP {error.code} for {url}") from error
                last = error
            except (OSError, ValueError) as error:                             # URLError, time out, connection reset, a JSON cut in the middle
                last = error
            if attempt < self.attempts:
                self.sleep(self.pause * 2 ** attempt)
        raise NcaaFetchError(f"{url}: {self.attempts} attempts, the last one: {type(last).__name__}: {last}") from last

    @staticmethod
    def _season(start_year: int) -> int:
        return start_year + 1                                                  # ESPN names a season by the year it ends in

    def conferences(self, sex: str, start_year: int) -> List[Dict[str, str]]:
        """The conferences of a season (``ncaa_page.parse_conferences``): ``sex`` is ``M`` or ``F``, ``start_year`` the year the season starts in."""
        url = f"{SITE.format(sex=SEXES[sex])}/scoreboard/conferences?season={self._season(start_year)}"
        return self._ask(url, parse_conferences)

    def standings(self, sex: str, start_year: int) -> Dict[str, Dict[str, str]]:
        """The conference each team played in that season (``ncaa_page.parse_standings``)."""
        url = f"{SITE_V2.format(sex=SEXES[sex])}/standings?group=50&level=2&season={self._season(start_year)}"
        return self._ask(url, parse_standings)

    def scoreboard(self, sex: str, day: str) -> List[Dict[str, Any]]:
        """The games of a day, ``YYYY-MM-DD`` (``ncaa_page.parse_scoreboard``): the Division I ones of that sex."""
        url = f"{SITE.format(sex=SEXES[sex])}/scoreboard?dates={day.replace('-', '')}&groups=50&limit=400"
        return self._ask(url, parse_scoreboard)

    def game(self, sex: str, game_id: str) -> Dict[str, Any]:
        """A game as ESPN's ``summary`` gives it (``ncaa_page.parse_summary``)."""
        return self._ask(f"{SITE.format(sex=SEXES[sex])}/summary?event={game_id}", parse_summary)
