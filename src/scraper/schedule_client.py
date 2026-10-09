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
