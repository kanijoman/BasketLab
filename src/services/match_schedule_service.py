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
    http_group_calendar,
    madrid_now as _madrid_now,
    normalize_name,
)
from src.utils.collection_utils import is_fbcyl

STALE_AFTER = timedelta(hours=3)   # a dated match older than this has surely been played
MAX_STATUS_CHECKS = 3
ROUND_GAP_DAYS = 3                 # pending matches of a round further apart than this are not the same block (postponed to weeks later)
ROUND_START_WINDOW = timedelta(days=5)   # rounds that start within this of the next kick-off are next; the weekly cycle is 7 days


def _round_blocks(pending: List[CalendarMatch]) -> List[tuple]:
    """``[(round, start of the block, matches)]``: the pending matches of each round split where two consecutive ones are more than
    ``ROUND_GAP_DAYS`` apart."""
    by_round: Dict[int, List[CalendarMatch]] = {}
    for m in pending:
        by_round.setdefault(m.round_index, []).append(m)
    blocks = []
    for rnd, matches in by_round.items():
        ordered = sorted(matches, key=lambda m: m.start)
        block = [ordered[0]]
        for m in ordered[1:]:
            if datetime.fromisoformat(m.start) - datetime.fromisoformat(block[-1].start) > timedelta(days=ROUND_GAP_DAYS):
                blocks.append((rnd, datetime.fromisoformat(block[0].start), block))
                block = []
            block.append(m)
        blocks.append((rnd, datetime.fromisoformat(block[0].start), block))
    return blocks


class MatchScheduleService:
    def __init__(self, db: Any, fetch_calendar: Callable[[str], List[CalendarMatch]] = http_calendar,
                 match_status: Callable[[str], str] = feb_status,
                 now: Callable[[], datetime] = _madrid_now,
                 competitions: Callable[[], List[Dict[str, str]]] = feb_competitions,
                 fetch_group_calendar: Callable[[str, str, str], List[CalendarMatch]] = http_group_calendar) -> None:
        self._db, self._fetch, self._status, self._now = db, fetch_calendar, match_status, now
        self._competitions = competitions
        self._fetch_group = fetch_group_calendar

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

    def calendar(self, collection: str, url: str) -> List[CalendarMatch]:
        """The calendar of the collection: of its GROUP when the scrape stored one (the page of a competition shows a single group, #449),
        else the page as it is. A group that cannot be read raises (the caller says so): never the calendar of another group."""
        meta = self._collection("COLLECTION_META").find_one({"_id": collection}) or {}
        if meta.get("group_value") and meta.get("season_value"):
            return self._fetch_group(url, str(meta["season_value"]), str(meta["group_value"]))
        return self._fetch(url)

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
            calendar = self.calendar(collection, url)
        except Exception as exc:  # noqa: BLE001 - FEB down / layout change: report, do not fail the page
            return self._result([], url, f"No se pudo leer el calendario de FEB: {exc}")
        mine = [m for m in calendar if m.involves(team_id)]
        if not mine:
            return self._result([], url, "El equipo no aparece en el calendario de la competición")

        now = self._now()
        entries = [self._entry(m, team_id, "scheduled", now) for m in mine
                   if m.kind == "scheduled" and m.start and datetime.fromisoformat(m.start) >= now - STALE_AFTER]
        entries = self._live_entries(mine, team_id, collection, now) + self._resolve_started(entries)
        entries.sort(key=lambda e: (e["status"] != "live", e["start"] or ""))
        return self._result(entries[:limit], url, None)

    def next_rounds(self, collection: str) -> Dict[str, Any]:
        """``{"rounds": [{"round", "matches"}, ...], "calendar_url", "warning"}``: the matches still to play that come next, grouped by round
        (issues #286, #172, #450). A match is ``{code, start, round, home: {id, name}, away: {id, name}}``; one that kicked off long ago counts
        as played and one without a date is not listed.

        The round is not the unit, time is: postponed and ADVANCED matches are real next matches (teams that play two rounds in a weekend to save a
        trip). The pending matches of each round are split where two of them are more than ``ROUND_GAP_DAYS`` apart (a postponement to weeks later is
        a block of its own) and every block that STARTS within ``ROUND_START_DAYS`` of the next kick-off is listed, whole: the advanced round, the
        midweek round, the tournament that plays three rounds in a weekend; the round of the next weekend (6-7 days later) is not, not even partly.
        Rounds are listed by the kick-off of their first match.
        """
        empty = {"rounds": [], "calendar_url": None}
        if is_fbcyl(collection):
            return {**empty, "warning": "Los partidos en directo solo están disponibles para competiciones FEB"}
        url = self.calendar_url(collection)
        if not url:
            return {**empty, "warning": "No se conoce el calendario de la competición (sin partidos ni metadatos)"}
        try:
            calendar = self.calendar(collection, url)
        except Exception as exc:  # noqa: BLE001 - FEB down / layout change: report, do not fail
            return {**empty, "calendar_url": url, "warning": f"No se pudo leer el calendario de FEB: {exc}"}
        limit = self._now() - STALE_AFTER
        pending = [m for m in calendar if m.kind == "scheduled" and m.start and datetime.fromisoformat(m.start) >= limit]
        if not pending:
            return {**empty, "calendar_url": url, "warning": "No quedan partidos por jugar en el calendario"}
        first = min(datetime.fromisoformat(m.start) for m in pending)
        chosen: Dict[int, List[CalendarMatch]] = {}
        for rnd, block_start, block in _round_blocks(pending):
            if block_start <= first + ROUND_START_WINDOW:
                chosen.setdefault(rnd, []).extend(block)
        rounds = sorted(chosen.items(), key=lambda item: min(m.start for m in item[1]))
        listed = [{"round": rnd, "matches": [self._next_match(m) for m in pending if m in set(ms)]} for rnd, ms in rounds]
        return {"rounds": listed, "calendar_url": url, "warning": None}

    @staticmethod
    def _next_match(m: CalendarMatch) -> Dict[str, Any]:
        return {"code": m.code, "start": m.start, "round": m.round_index,
                "home": {"id": m.home_id, "name": m.home_name}, "away": {"id": m.away_id, "name": m.away_name}}

    def next_round(self, collection: str) -> Dict[str, Any]:
        """``{"round", "matches", "calendar_url", "warning"}``: the biggest of the ``next_rounds`` (the earliest on a tie), for callers that want one."""
        found = self.next_rounds(collection)
        if not found["rounds"]:
            return {"round": None, "matches": [], "calendar_url": found["calendar_url"], "warning": found["warning"]}
        best = max(found["rounds"], key=lambda r: len(r["matches"]))
        return {"round": best["round"], "matches": best["matches"], "calendar_url": found["calendar_url"], "warning": None}

    def _resolve_started(self, entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """A calendar row that already kicked off still says "scheduled": FEB's page shows no score while the match is
        on and for a long time after it (seen in the first real recording, issue #118). Ask FEB's live API: a match
        in progress is ``live``, a finished one is dropped, a delayed one (404) or a failed lookup stays ``scheduled``."""
        resolved, checks = [], 0
        for entry in entries:
            started = entry["starts_in_min"] is not None and entry["starts_in_min"] <= 0
            if not started or checks >= MAX_STATUS_CHECKS:
                resolved.append(entry)
                continue
            checks += 1
            try:
                status = self._status(entry["code"])
            except Exception:  # noqa: BLE001 - one failing lookup must not hide the match
                status = "scheduled"
            if status == "finished":
                continue
            resolved.append({**entry, "status": "live"} if status == "live" else entry)
        return resolved

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
