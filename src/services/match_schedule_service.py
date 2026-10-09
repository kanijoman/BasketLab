"""Upcoming and live matches of a team, from the FEB calendar (issue #119).

The calendar page lists every match of a competition: results of played ones, kick-off time of
the rest. A match that is being played shows a score like a finished one, so a result row that is
NOT yet in our database is asked to FEB's live API for its status (404 = not started, ``2`` =
live, ``3`` = finished); only a few such rows are checked per request.
"""

from __future__ import annotations

import re
import sys
import unicodedata
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import parse_qs, urlparse

from cachetools import TTLCache

from src.scraper.calendar_parser import CalendarMatch, parse_calendar
from src.utils.collection_utils import is_fbcyl

CALENDAR_URL = "https://baloncestoenvivo.feb.es/calendario.aspx?g={g}&t={season}&nm={nm}"
STALE_AFTER = timedelta(hours=3)   # a dated match older than this has surely been played
MAX_STATUS_CHECKS = 3
_CALENDAR_CACHE: TTLCache = TTLCache(maxsize=16, ttl=60)
_COMPETITIONS_CACHE: TTLCache = TTLCache(maxsize=1, ttl=3600)


def normalize_name(name: str) -> str:
    """"LF Challenge" / "lf  CHALLENGE" -> "lfchallenge" (accents and non-alphanumerics removed)."""
    text = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", text.lower())


def feb_competitions() -> List[Dict[str, str]]:
    """FEB's competition list (``name``, ``results_url`` with ``g=<competition id>&nm=<slug>``), cached 1 h."""
    if "all" not in _COMPETITIONS_CACHE:
        _legacy_path()
        from src.scraper import FEBWebScraper

        _COMPETITIONS_CACHE["all"] = FEBWebScraper().get_feb_competitions()
    return _COMPETITIONS_CACHE["all"]


def _legacy_path() -> None:
    """The scraper still imports some helpers un-prefixed (``utils...``): put ``src`` on the path."""
    src = str(Path(__file__).resolve().parents[1])
    if src not in sys.path:
        sys.path.insert(0, src)


def http_calendar(url: str) -> List[CalendarMatch]:
    """Download and parse the calendar page (cached for a minute)."""
    if url in _CALENDAR_CACHE:
        return _CALENDAR_CACHE[url]
    import requests

    from src.scraper.constants import EXTENDED_TIMEOUT, HTML_HEADERS

    response = requests.get(url, headers=HTML_HEADERS, timeout=EXTENDED_TIMEOUT)
    response.raise_for_status()
    matches = parse_calendar(response.content)
    _CALENDAR_CACHE[url] = matches
    return matches


def feb_status(code: str) -> str:
    """``scheduled`` | ``live`` | ``finished`` | ``unknown`` from FEB's live API."""
    import requests

    _legacy_path()
    from src.scraper.constants import BOXSCORE_API_URL, DEFAULT_TIMEOUT
    from src.scraper.token_manager import TokenManager

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


def _madrid_now() -> datetime:
    from zoneinfo import ZoneInfo

    return datetime.now(ZoneInfo("Europe/Madrid")).replace(tzinfo=None)


class MatchScheduleService:
    def __init__(self, db: Any, fetch_calendar: Callable[[str], List[CalendarMatch]] = http_calendar,
                 match_status: Callable[[str], str] = feb_status,
                 now: Callable[[], datetime] = _madrid_now,
                 competitions: Callable[[], List[Dict[str, str]]] = feb_competitions) -> None:
        self._db, self._fetch, self._status, self._now = db, fetch_calendar, match_status, now
        self._competitions = competitions

    # -- collection metadata -------------------------------------------------------------

    def _collection(self, name: str):
        return self._db.repository.connection.get_collection(name)

    def calendar_url(self, collection: str) -> Optional[str]:
        """Stored ``COLLECTION_META.competition_url`` or looked up in FEB's competition list.

        The calendar address needs FEB's internal competition id (``g``), which is not in our games, so
        the competition is found by name in the list the scraper uses (``calendario.aspx?g=..&t=..&nm=..``).
        """
        meta = self._collection("COLLECTION_META").find_one({"_id": collection})
        if meta and meta.get("competition_url"):
            return meta["competition_url"]
        game = self._collection(collection).find_one({"_competition": {"$exists": True}}, {"_competition": 1, "_season": 1})
        if not game or not game.get("_competition") or not game.get("_season"):
            return None
        wanted = normalize_name(game["_competition"])
        try:
            found = next((c for c in self._competitions() if normalize_name(c["name"]) == wanted), None)
        except Exception:  # noqa: BLE001 - FEB list unavailable: no calendar for now
            return None
        if not found:
            return None
        query = parse_qs(urlparse(found["results_url"]).query)
        if not query.get("g") or not query.get("nm"):
            return None
        return CALENDAR_URL.format(g=query["g"][0], season=game["_season"], nm=query["nm"][0])

    def _known_codes(self, collection: str) -> set:
        return {str(c) for c in self._collection(collection).distinct("_id")}

    # -- listing -------------------------------------------------------------------------

    def upcoming(self, collection: str, team_id: str, limit: int = 5) -> Dict[str, Any]:
        """``{"matches": [...], "calendar_url": str|None, "warning": str|None}`` (never raises)."""
        if is_fbcyl(collection):
            return self._result([], None, "Los partidos en directo solo están disponibles para competiciones FEB")
        url = self.calendar_url(collection)
        if not url:
            return self._result([], None, "No se conoce el calendario de la competición (sin partidos ni metadatos)")
        try:
            calendar = self._fetch(url)
        except Exception as exc:  # noqa: BLE001 - FEB down / layout change: report, do not fail the page
            return self._result([], url, f"No se pudo leer el calendario de FEB: {exc}")
        mine = [m for m in calendar if m.involves(team_id)]
        if not mine:
            return self._result([], url, "El equipo no aparece en el calendario de la competición")

        now = self._now()
        entries = [self._entry(m, team_id, "scheduled", now) for m in mine
                   if m.kind == "scheduled" and m.start and datetime.fromisoformat(m.start) >= now - STALE_AFTER]
        entries = self._live_entries(mine, team_id, collection, now) + entries
        entries.sort(key=lambda e: (e["status"] != "live", e["start"] or ""))
        return self._result(entries[:limit], url, None)

    def _live_entries(self, mine: List[CalendarMatch], team_id: str, collection: str, now: datetime) -> List[Dict[str, Any]]:
        known = self._known_codes(collection)
        candidates = [m for m in mine if m.kind == "result" and m.code not in known][:MAX_STATUS_CHECKS]
        live = []
        for m in candidates:
            try:
                status = self._status(m.code)
            except Exception:  # noqa: BLE001 - one failing lookup must not hide the others
                continue
            if status == "live":
                live.append(self._entry(m, team_id, "live", now))
        return live

    @staticmethod
    def _entry(m: CalendarMatch, team_id: str, status: str, now: datetime) -> Dict[str, Any]:
        opp = m.opponent_of(team_id)
        starts_in = int((datetime.fromisoformat(m.start) - now).total_seconds() // 60) if m.start else None
        return {
            **m.to_dict(), "status": status, "is_home": m.home_id == str(team_id),
            "opponent": {"id": opp[0], "name": opp[1]} if opp else None, "starts_in_min": starts_in,
        }

    @staticmethod
    def _result(matches: List[Dict[str, Any]], url: Optional[str], warning: Optional[str]) -> Dict[str, Any]:
        return {"matches": matches, "calendar_url": url, "warning": warning}
