"""Compares a collection with the FEB calendar: which played matches are missing from the database?

Used to monitor that production (Atlas) has every match scraped up to the current round: the calendar is
the source of truth for what has been played; the collection holds what we have stored.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from src.services.match_schedule_service import MatchScheduleService
from src.utils.collection_utils import is_fbcyl


def _parse_starttime(text: Any) -> Optional[datetime]:
    try:
        return datetime.strptime(str(text).strip(), "%d-%m-%Y - %H:%M")
    except ValueError:
        return None


class DataFreshnessService:
    def __init__(self, db: Any, schedule: Optional[MatchScheduleService] = None) -> None:
        self._db = db
        self._schedule = schedule or MatchScheduleService(db)

    @staticmethod
    def _result(collection: str, **fields: Any) -> Dict[str, Any]:
        base = {"collection": collection, "up_to_date": None, "games_in_db": 0, "calendar_results": 0,
                "missing_codes": [], "last_game": None, "calendar_url": None, "warning": None}
        return {**base, **fields}

    def check(self, collection: str) -> Dict[str, Any]:
        if is_fbcyl(collection):
            return self._result(collection, warning="La comprobación contra el calendario solo existe para colecciones FEB")
        games = self._db.repository.connection.get_collection(collection)
        stored = {str(g["_id"]): g for g in games.find({}, {"HEADER.starttime": 1})}
        dates = [d for d in (_parse_starttime((g.get("HEADER") or {}).get("starttime")) for g in stored.values()) if d]
        last = max(dates).strftime("%Y-%m-%dT%H:%M") if dates else None
        url = self._schedule.calendar_url(collection)
        if not url:
            return self._result(collection, games_in_db=len(stored), last_game=last,
                                warning="No se conoce el calendario de la competición")
        try:
            calendar = self._schedule._fetch(url)
        except Exception as exc:  # noqa: BLE001 - FEB unreachable: inconclusive, not stale
            return self._result(collection, games_in_db=len(stored), last_game=last, calendar_url=url,
                                warning=f"No se pudo leer el calendario de FEB: {exc}")
        played = [m.code for m in calendar if m.kind == "result"]
        missing = [c for c in played if c not in stored]
        return self._result(collection, up_to_date=not missing, games_in_db=len(stored), calendar_results=len(played),
                            missing_codes=missing, last_game=last, calendar_url=url)
