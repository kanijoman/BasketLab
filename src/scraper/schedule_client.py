"""FEB calendar / live-status client (network helpers shared by the live match list and the recorder).

Kept in ``src.scraper`` so command-line jobs need only the scraper dependencies (requests,
beautifulsoup4, cachetools, tenacity): importing ``src.services`` would pull the whole database layer.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime
from typing import Dict, List

from cachetools import TTLCache

from .calendar_parser import CalendarMatch, parse_calendar

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
    is selected the way the scraper does for the results: the ASP.NET postback of the group dropdown, then the usual parser.
    """
    key = (url, season_value, group_value)
    if key in _CALENDAR_CACHE:
        return _CALENDAR_CACHE[key]
    from bs4 import BeautifulSoup

    from . import FEBWebScraper
    from .constants import GROUP_DROPDOWN_ID

    scraper = FEBWebScraper()
    page = scraper.web_client.get(url)
    if page is None:
        raise ConnectionError(f"No response from {url}")
    soup = BeautifulSoup(page.content, "html.parser")
    dropdown = soup.find("select", {"id": GROUP_DROPDOWN_ID})
    shown = dropdown.find("option", selected=True) if dropdown else None
    if dropdown is None or (shown is not None and shown.get("value") == group_value):
        # the page already shows this group (or has no groups): the postback of the group that is already selected answers WITHOUT the calendar
        matches = parse_calendar(page.content)
    else:
        hidden = scraper.get_hidden_fields(soup)
        matches = parse_calendar(str(scraper.select_group(scraper.web_client.get_session(), url, season_value, group_value, hidden)))
    _CALENDAR_CACHE[key] = matches
    return matches


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
