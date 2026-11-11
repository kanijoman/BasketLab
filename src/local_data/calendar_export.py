"""The calendar of a competition for the web (#842): every match with its round, kick-off and, once played, its score.

The browser needs the matches still to play (the preview of a match picks one, the simulation of the league plays them) and the results the archive does not have yet. The publisher reads
them from the FEB calendar page of the group or the ESB API of FBCYL (``CalendarSource``, replaced by a fake in the tests), once per publication: a calendar changes without a new game, so
the section is not cached (``web_data.UNCACHED``). A calendar that cannot be had is ``None`` (logged), never an exception: the publication goes on and keeps the previous calendar.

A match is identified by what the games use as ``_id`` (the FEB match code, the FBCYL ``universallyid``: ``match_id``), so the browser can tell which results it already has in its rows.
A FEB result row that is not in the archive may be a match being played (the page shows a score like a finished one): a few are asked to the live API and marked ``live``.
"""
from __future__ import annotations

import logging
from typing import Any, Callable, Dict, Iterable, List, Optional, Set

from src.local_data.export import FORMAT
from src.local_data.images_export import current_season_collections
from src.utils.collection_utils import is_fbcyl

log = logging.getLogger(__name__)

MAX_STATUS_CHECKS = 8      # per competition: each one is a call to the live API of the FEB


class CalendarSource:
    """What the federations answer. The defaults reach the network; the tests replace the methods (or the functions given here)."""

    def __init__(self, fetch_calendar: Optional[Callable[[str], List[Any]]] = None, fetch_group: Optional[Callable[[str, str, str], List[Any]]] = None) -> None:
        self._fetch_calendar, self._fetch_group = fetch_calendar, fetch_group

    def feb(self, handler: Any, collection: str) -> List[Any]:
        """The ``CalendarMatch`` of the group of ``collection`` (the page of its competition, or of its group when the scrape stored one)."""
        from src.services.match_schedule_service import MatchScheduleService

        extra = {k: v for k, v in (("fetch_calendar", self._fetch_calendar), ("fetch_group_calendar", self._fetch_group)) if v}
        service = MatchScheduleService(handler, **extra)
        url = service.calendar_url(collection)
        if not url:
            raise LookupError("the calendar of the competition is not known")
        return service.calendar(collection, url)

    def fbcyl_rows(self, group_id: str) -> List[Dict[str, Any]]:
        from src.scraper.fbcyl_calendar import http_rows

        return http_rows(group_id)

    def status(self, code: str) -> str:
        from src.scraper.schedule_client import feb_status

        return feb_status(code)


def calendar_collections(names: Iterable[str], groups: Dict[str, str]) -> Set[str]:
    """The competitions that get a calendar: those of the newest season, without the knockouts (their ties are not a calendar of a league) and, in FBCYL, only the groups the catalogue knows (``groups``)."""
    from src.live_prep.game_sources import is_knockout

    return {n for n in current_season_collections(names) if not is_knockout(n) and (n in groups if is_fbcyl(n) else True)}


def _score(value: Optional[str]) -> Optional[List[int]]:
    return [int(part) for part in str(value).split("-")] if value else None


def _entry(match: Any, match_id: str, kind: str, start: Optional[str]) -> Dict[str, Any]:
    return {"code": match.code, "match_id": match_id, "round": match.round_index, "kind": kind, "start": start,
            "home": {"id": match.home_id, "name": match.home_name}, "away": {"id": match.away_id, "name": match.away_name}, "score": _score(match.score)}


def _live_codes(source: CalendarSource, results: List[Any], archived: Set[str]) -> Set[str]:
    """The result rows missing from the archive that the live API says are being played (at most ``MAX_STATUS_CHECKS`` are asked; a failure leaves the row a result)."""
    live: Set[str] = set()
    for match in [m for m in results if str(m.code) not in archived][:MAX_STATUS_CHECKS]:
        try:
            if source.status(match.code) == "live":
                live.add(match.code)
        except Exception as exc:  # noqa: BLE001 - the feed is down: the row stays a result, the calendar still goes out
            log.warning("%s: status of match %s unavailable: %s", match.code, match.code, exc)
    return live


def _feb_matches(source: CalendarSource, handler: Any, collection: str) -> List[Dict[str, Any]]:
    calendar = source.feb(handler, collection)
    archived = {str(i) for i in handler.connection.client["BASKETBALL"][collection].distinct("_id")}
    live = _live_codes(source, [m for m in calendar if m.kind == "result"], archived)
    return [_entry(m, str(m.code), "live" if m.code in live else m.kind, m.start) for m in calendar]


def _fbcyl_matches(source: CalendarSource, group_id: str) -> Any:
    """``(matches, ties_allowed)``: the id of a match is its ``universallyid`` (the ``_id`` of the game) and a played one keeps its kick-off, which the rows have for every match."""
    from src.scraper.fbcyl_calendar import calendar_matches

    rows = source.fbcyl_rows(group_id)
    matches = [_entry(m, str(row["universallyid"]), m.kind, str(row.get("matchDay") or "")[:16].replace(" ", "T") or None) for m, row in zip(calendar_matches(rows), rows)]
    return matches, any(str(row.get("tiedAllowed")) == "1" for row in rows)


def export_calendar(source: CalendarSource, handler: Any, collection: str, group_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """The calendar payload of ``collection``, or ``None`` when it cannot be had (logged) or is empty. ``group_id`` is the ESB group of a FBCYL competition (``competition_catalogue.fbcyl_groups``)."""
    try:
        if is_fbcyl(collection):
            if not group_id:
                return None
            matches, ties = _fbcyl_matches(source, group_id)
        else:
            matches, ties = _feb_matches(source, handler, collection), False
    except Exception as exc:  # noqa: BLE001 - FEB down or its layout changed: the publication goes on without this calendar
        log.warning("%s: calendar unavailable: %s", collection, exc)
        return None
    if not matches:
        return None
    matches.sort(key=lambda m: (m["round"], m["start"] or "", m["code"]))
    return {"format": FORMAT, "collection": collection, "league": "fbcyl" if is_fbcyl(collection) else "feb", "games": len(matches), "ties_allowed": ties, "matches": matches}
