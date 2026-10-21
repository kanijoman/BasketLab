"""FEB calendar / live-status client (network helpers shared by the live match list and the recorder).

Kept in ``src.scraper`` so command-line jobs need only the scraper dependencies (requests,
beautifulsoup4, cachetools, tenacity): importing ``src.services`` would pull the whole database layer.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from cachetools import TTLCache

from .calendar_parser import CalendarMatch, parse_calendar, parse_series

CALENDAR_URL = "https://baloncestoenvivo.feb.es/calendario.aspx?g={g}&t={season}&nm={nm}"
_CALENDAR_CACHE: TTLCache = TTLCache(maxsize=16, ttl=60)
_COMPETITIONS_CACHE: TTLCache = TTLCache(maxsize=1, ttl=3600)


def normalize_name(name: str) -> str:
    """"LF Challenge" / "lf  CHALLENGE" -> "lfchallenge" (accents and non-alphanumerics removed)."""
    text = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", text.lower())


def feb_competitions() -> List[Dict[str, str]]:
    """FEB's competition list (``name``, ``results_url`` with ``g=<competition id>&nm=<slug>``), cached 1 h."""
    if "all" not in _COMPETITIONS_CACHE:
        from . import FEBWebScraper

        _COMPETITIONS_CACHE["all"] = FEBWebScraper().get_feb_competitions()
    return _COMPETITIONS_CACHE["all"]


def http_calendar(url: str) -> List[CalendarMatch]:
    """Download and parse the calendar page (cached for a minute)."""
    if url in _CALENDAR_CACHE:
        return _CALENDAR_CACHE[url]
    import requests

    from .constants import EXTENDED_TIMEOUT, HTML_HEADERS

    response = requests.get(url, headers=HTML_HEADERS, timeout=EXTENDED_TIMEOUT)
    response.raise_for_status()
    matches = parse_calendar(response.content)
    _CALENDAR_CACHE[url] = matches
    return matches


def http_group_calendar(url: str, season_value: str, group_value: str) -> List[CalendarMatch]:
    """Calendar of ONE group of the competition page ``url`` (cached for a minute per group, issue #449).

    The page of a competition (``calendario.aspx?g=2&t=2026&nm=segundafeb``) shows a single group, the same URL for every group of it, so the group
    is selected with the scraper's own navigation (``FEBWebScraper.group_page``, the one ``get_matches`` uses: the page that already shows the group
    is read as it is, another group by ASP.NET postback), then the usual parser.
    """
    key = (url, season_value, group_value)
    if key in _CALENDAR_CACHE:
        return _CALENDAR_CACHE[key]
    from . import FEBWebScraper

    scraper = FEBWebScraper()
    found = scraper.group_page(season_value, group_value, scraper.web_client.get_session(), url, single_group_ok=True)
    if found is None:
        raise ConnectionError(f"No response from {url}")
    matches = parse_calendar(str(found.soup)) or _series_calendar(scraper, found, season_value, group_value)
    _CALENDAR_CACHE[key] = matches
    return matches


def _phase_of_group(scraper, soup, group_value: str) -> str:
    return next((label for label, value in scraper.get_groups(soup) if value == group_value), "")


def _series_calendar(scraper, found, season_value: str, group_value: str) -> List[CalendarMatch]:
    """Knockout groups have no calendar table: their ties are on ``Series.aspx`` (issue #456).

    One series page can hold several phases (Copa de España: one page, groups ``Play-offs 1/16 Final``, ``Play-offs 1/8 Final``...): the ties whose
    phase is named in the group label are kept; when none is (a group named after its series, ``2ºA-1ºB Final``) every tie of the pages is.
    """
    hrefs = scraper.series_hrefs(found.calendar_url, group_value, season_value)
    matches = [m for _, soup in scraper.series_pages(hrefs) for m in parse_series(str(soup))]
    label = _phase_of_group(scraper, found.soup, group_value).lower()
    named = {m.phase.lower() for m in matches if m.phase and m.phase.lower() in label}
    specific = {p for p in named if not any(p != q and p in q for q in named)}   # "Final" is inside "1/16 Final"
    return [m for m in matches if m.phase and m.phase.lower() in specific] or matches


def calendar_ref(url: str, season_value: str, group_value: str) -> str:
    """``url#t=<season>&g=<group>``: a calendar URL plus the group to read (``g=all``: every group of the season)."""
    return f"{url}#t={season_value}&g={group_value}"


def split_calendar_ref(ref: str) -> Tuple[str, Optional[str], Optional[str]]:
    """``(url, season_value, group_value)`` of a reference; a plain URL has no group (``None``)."""
    url, _, fragment = ref.partition("#")
    if not fragment:
        return url, None, None
    params = dict(part.partition("=")[::2] for part in fragment.split("&"))
    if not (params.get("t") and params.get("g")):
        raise ValueError(f"calendar reference {ref!r} needs '#t=<season>&g=<group>'")
    return url, params["t"], params["g"]


def fetch_calendar_ref(ref: str) -> List[CalendarMatch]:
    """Calendar of a reference (see ``calendar_ref``): the page as it is, one group, or all the groups of the season."""
    url, season, group = split_calendar_ref(ref)
    if group is None:
        return http_calendar(url)
    if group != "all":
        return http_group_calendar(url, season, group)
    from . import FEBWebScraper

    seen, out = set(), []
    for _, value in FEBWebScraper().get_groups_for_season(url, season):
        try:
            found = http_group_calendar(url, season, value)
        except Exception:  # noqa: BLE001 - one unreachable group must not hide the others
            continue
        out.extend(m for m in found if m.code not in seen and not seen.add(m.code))
    return out


def feb_status(code: str) -> str:
    """``scheduled`` | ``live`` | ``finished`` | ``unknown`` from FEB's live API."""
    import requests

    from .constants import BOXSCORE_API_URL, DEFAULT_TIMEOUT
    from .token_manager import TokenManager

    session = requests.Session()
    token = TokenManager().get_token(code, session)
    if not token:
        return "unknown"
    response = session.get(BOXSCORE_API_URL.format(match_code=code), timeout=DEFAULT_TIMEOUT,
                           headers={"Authorization": f"Bearer {token}"})
    if response.status_code == 404:
        return "scheduled"
    response.raise_for_status()
    status = str((response.json().get("HEADER") or {}).get("status"))
    return {"3": "finished", "2": "live", "1": "live"}.get(status, "unknown")


def madrid_now() -> datetime:
    from zoneinfo import ZoneInfo

    return datetime.now(ZoneInfo("Europe/Madrid")).replace(tzinfo=None)
