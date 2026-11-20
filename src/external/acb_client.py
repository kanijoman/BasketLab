"""The client of the public pages and the calendar API of ACB (#886, D2b of epic #872): polite, patient and honest about what went wrong, like the one of FIBA.

* **Polite**: at most one request every ``PAUSE_S`` (1 s: the rhythm measured by the spike) whatever the caller does, a generic user agent that names no project, and a **budget of requests per run**
  (``max_requests``, retries included): when it is spent ``AcbBudgetExhausted`` is raised and the next day's run goes on where this one stopped.
* **Patient**: a page that comes back without its data, cut, with a server error, a 429 or lost to the network is asked again after a wait that doubles (``pause`` x 2, x 4, x 8), up to ``attempts`` times.
* **Honest**: a page that is not there (404) is ``AcbNotFound``, a request the site refuses (403 and the like) is ``AcbFetchError`` and neither is asked again; one that never comes with its data ends in
  ``AcbFetchError``, never in half a game.
* **The key of the API** (only the calendar needs it) is the one the public JavaScript of acb.com ships to every browser: ``fetch_api_key`` reads it from there on each run, as a browser does, keeps it only in
  memory and never writes it, logs it or puts it in an error. If the site stops shipping it, that is said (``AcbFetchError``); the client does not carry one of its own. The legal risk of using ACB is
  open (docs/evaluaciones/2026-11-20_acb-spike-886.md).

The network is injected (``fetch``, ``sleep``, ``clock``) so the tests serve the real pages of ``tests/fixtures/acb`` and see the pauses without waiting.
"""
from __future__ import annotations

import json
import re
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Callable, Dict, List, Optional, TypeVar

from src.external.acb_page import AcbPageError, check_page, extract_flight

LIVE_BASE = "https://live.acb.com/partidos"
SITE_BASE = "https://acb.com"
API_BASE = "https://api2.acb.com"
USER_AGENT = "Mozilla/5.0 (compatible; basketball-research-bot/1.0)"          # generic on purpose: no name of the project goes to an outside service
PAUSE_S = 1.0
ATTEMPTS = 4
TIMEOUT_S = 40
KEY_PAGE = f"{SITE_BASE}/es/liga/equipos/real-madrid-9/partidos?editionId=91"          # any page of the site that loads the JavaScript with the key
T = TypeVar("T")


class AcbFetchError(OSError):
    """A page could not be had: refused, lost to the network or without its data after every attempt."""


class AcbNotFound(AcbFetchError):
    """The page does not exist (a game or a player that is not there)."""


class AcbBudgetExhausted(AcbFetchError):
    """The run has used its budget of requests: stop and let the next run go on."""


def slugify(name: str) -> str:
    """``Leyma Coruña`` -> ``leyma-coruna``: how the site writes a team or a player in its addresses."""
    plain = "".join(c for c in unicodedata.normalize("NFKD", name.lower()) if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "-", plain).strip("-")


def match_url(home: str, away: str, match_id: int, tab: str) -> str:
    return f"{LIVE_BASE}/{slugify(home)}-vs-{slugify(away)}-{match_id}/{tab}"


def player_url(first_name: str, last_name: str, player_id: int, tab: str, edition_id: Optional[int] = None) -> str:
    """The page of a player; ``edition_id`` asks for the season of that edition (his shots are those of a season: without it, the current one)."""
    return f"{SITE_BASE}/es/liga/jugadores/{slugify(first_name + ' ' + last_name)}-{player_id}/{tab}" + (f"?editionId={edition_id}" if edition_id else "")


def _fetch(url: str, headers: Dict[str, str]) -> str:
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=TIMEOUT_S) as response:
        return response.read().decode("utf-8", "replace")


def fetch_api_key(fetch: Callable[[str, Dict[str, str]], str] = _fetch, sleep: Callable[[float], None] = time.sleep) -> str:
    """The key of the API as the public JavaScript of the site ships it (one request per script, at the pause); ``AcbFetchError`` if it is not there any more."""
    headers = {"User-Agent": USER_AGENT}
    html = fetch(KEY_PAGE, headers)
    for path in sorted(set(re.findall(r"/_next/static/chunks/[A-Za-z0-9_\-\.]+\.js", html))):
        sleep(PAUSE_S)
        found = re.search(r'apiKey:"([0-9a-f\-]{36})"', fetch(SITE_BASE + path, headers))
        if found:
            return found.group(1)
    raise AcbFetchError("the JavaScript of the site has no API key any more: the calendar cannot be asked for")


def editions_of(answer: Dict[str, Any]) -> Dict[int, int]:
    """``{year the season starts: edition id}`` of the answer of the teams API: the id of an edition is the site's, not a formula (an edition without its year is left out, never guessed)."""
    return {s["seasonStartYear"]: s["id"] for s in answer.get("availableFilters", {}).get("seasons", []) if isinstance(s.get("seasonStartYear"), int) and isinstance(s.get("id"), int)}


class AcbClient:
    def __init__(self, fetch: Callable[[str, Dict[str, str]], str] = _fetch, sleep: Callable[[float], None] = time.sleep, clock: Callable[[], float] = time.monotonic,
                 pause: float = PAUSE_S, attempts: int = ATTEMPTS, user_agent: str = USER_AGENT, api_key: Optional[Callable[[], str]] = None, max_requests: Optional[int] = None) -> None:
        self.fetch, self.sleep, self.clock = fetch, sleep, clock
        self.pause, self.attempts, self.user_agent, self.max_requests = pause, attempts, user_agent, max_requests
        self.requests = 0
        self._last: Any = None
        self._api_key_source = api_key or (lambda: fetch_api_key(fetch, sleep))
        self._api_key: Optional[str] = None

    def __repr__(self) -> str:
        return f"AcbClient(requests={self.requests}, max_requests={self.max_requests})"          # no key: a repr goes to logs

    def _throttle(self) -> None:
        """Never two requests closer than ``pause``, whoever asks."""
        if self._last is not None:
            wait = self.pause - (self.clock() - self._last)
            if wait > 0:
                self.sleep(wait)
        self._last = self.clock()

    def _ask(self, url: str, read: Callable[[str], T], headers: Optional[Dict[str, str]] = None) -> T:
        last: Exception = AcbFetchError(url)
        for attempt in range(1, self.attempts + 1):
            if self.max_requests is not None and self.requests >= self.max_requests:
                raise AcbBudgetExhausted(f"{self.requests} requests: the budget of the run is spent")
            self._throttle()
            self.requests += 1
            try:
                return read(self.fetch(url, {"User-Agent": self.user_agent, "Accept-Language": "es", **(headers or {})}))
            except AcbPageError as error:
                last = error                                                   # no data or cut in the middle: ask again
            except urllib.error.HTTPError as error:
                if error.code == 404:
                    raise AcbNotFound(f"{url} does not exist") from error
                if error.code < 500 and error.code != 429:
                    raise AcbFetchError(f"HTTP {error.code} for {url}") from error
                last = error
            except (OSError, ValueError) as error:                             # URLError, time out, connection reset, a JSON cut in the middle
                last = error
            if attempt < self.attempts:
                self.sleep(self.pause * 2 ** attempt)
        raise AcbFetchError(f"{url}: {self.attempts} attempts, the last one: {type(last).__name__}: {last}") from last

    def _page(self, url: str, kind: str) -> str:
        def read(html: str) -> str:
            text = extract_flight(html)
            check_page(kind, text)
            return text

        return self._ask(url, read)

    def match_page(self, home: str, away: str, match_id: int, tab: str) -> str:
        """The data of a tab of a game (``jugadas``, ``estadisticas``) as the text of the page's chunks; ``acb_page`` reads it."""
        return self._page(match_url(home, away, match_id, tab), tab)

    def player_page(self, first_name: str, last_name: str, player_id: int, tab: str, edition_id: Optional[int] = None) -> str:
        """The data of a tab of a player (``temporada``: his bio; ``zonas-de-tiro``: his shots with their coordinates) in the season of ``edition_id`` (the current one if none)."""
        return self._page(player_url(first_name, last_name, player_id, tab, edition_id), tab)

    def _api(self, path: str, **params: Any) -> Dict[str, Any]:
        if self._api_key is None:
            self._api_key = self._api_key_source()
        url = f"{API_BASE}{path}?{urllib.parse.urlencode(params)}"
        return self._ask(url, json.loads, {"X-APIKEY": self._api_key, "Accept": "application/json"})

    def team_matches(self, club_id: int, edition_id: int, competition_id: int = 1) -> List[Dict[str, Any]]:
        """Every game of a club in an edition (its calendar and results)."""
        return self._api("/api/seasondata/TeamProfile/team-matches", clubId=club_id, competitionId=competition_id, editionId=edition_id)["matches"]

    def editions(self, competition_id: int = 1) -> Dict[int, int]:
        """``{year: edition id}`` of every edition the site has of a competition."""
        return editions_of(self._api("/api/seasondata/TeamProfile/teams", competitionId=competition_id))

    def teams(self, edition_id: int, competition_id: int = 1) -> List[Dict[str, Any]]:
        """The clubs of an edition (``clubId``, ``fullName``…), as they were in it."""
        return [t["latest"] for t in self._api("/api/seasondata/TeamProfile/teams", competitionId=competition_id, editionId=edition_id)["teams"]]
