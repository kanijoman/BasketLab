"""Upcoming and live matches of a team, from the FEB calendar (issue #119).

The calendar page lists every match of a competition: results of played ones, kick-off time of
the rest. A match that is being played shows a score like a finished one, so a result row that is
NOT yet in our database is asked to FEB's live API for its status (404 = not started, ``2`` =
live, ``3`` = finished); only a few such rows are checked per request.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import parse_qs, urlparse

from src.scraper.calendar_parser import CalendarMatch
from src.scraper.schedule_client import (  # noqa: F401  (re-exported for callers and tests)
    CALENDAR_URL,
    feb_competitions,
    feb_status,
    http_calendar,
    madrid_now as _madrid_now,
    normalize_name,
)
from src.utils.collection_utils import is_fbcyl

STALE_AFTER = timedelta(hours=3)   # a dated match older than this has surely been played
MAX_STATUS_CHECKS = 3


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
