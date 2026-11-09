"""The calendar of a FBCYL group (issue #446): the ESB API read ONCE for the recorder, the packages and whoever needs the matches of a group.

The answer is Base64 JSON with a row per match: ``round``, ``matchDay`` (kick-off, Madrid), ``state`` (0 to play, 1 played), the stable team ids (``idLocalTeam``/``idVisitorTeam``, the ones of the
games' ``teamIdExtern``), ``idMatch`` and, only when the match is about to start or was played, ``adGameId`` (the key of the live feed). ``calendar_matches`` turns the rows into the same
``CalendarMatch`` the FEB calendar gives, so everything that picks the next rounds works on both leagues. Kept in ``src.scraper`` as ``schedule_client``: command-line jobs need only ``requests``.
"""

from __future__ import annotations

import base64
import json
from typing import Any, Dict, List, Optional

from cachetools import TTLCache

from .calendar_parser import CalendarMatch

_ROWS_CACHE: TTLCache = TTLCache(maxsize=8, ttl=60)      # the packages ask a group twice (its next rounds and the competition of the index): once is enough

API = "https://esb.optimalwayconsulting.com/fbcyl/1/jR4rgA5K6Chhh5vyfrxo9wTScdg2NT7K/FCBQWeb/getAllGamesByGrupWithMatchRecords/{group}/0"
CODE_PREFIX = "fbcyl-"      # the code of a FBCYL match in the index: it never looks like a FEB code (digits only), and ``idMatch`` exists for every row (``adGameId`` does not for a pending one)


def calendar_rows(text: str) -> List[Dict[str, Any]]:
    """The matches of a group calendar answer (Base64 JSON), each with its ``round`` and ``round_date``; nothing when the answer is not a good one."""
    try:
        data = json.loads(base64.b64decode(text).decode("utf-8"))
        if data.get("result") != "OK":
            return []
        rounds = data["messageData"]["rounds"]
        return [with_round(m, number, r.get("date")) for number, r in rounds.items() for m in (r.get("matches") or {}).values()]
    except (ValueError, KeyError, TypeError, AttributeError):
        return []


def with_round(row: Dict[str, Any], number: str, date: Optional[str]) -> Dict[str, Any]:
    return {**row, "round": number, "round_date": date}


def http_rows(group_id: str) -> List[Dict[str, Any]]:
    """The rows of the calendar of a group, from the ESB API; raises when the answer is not a calendar (the caller says so: never an empty calendar passed off as a good one)."""
    if group_id in _ROWS_CACHE:
        return _ROWS_CACHE[group_id]
    import requests

    from .constants import DEFAULT_HEADERS

    response = requests.get(API.format(group=group_id), headers=DEFAULT_HEADERS, timeout=30)
    response.raise_for_status()
    rows = calendar_rows(response.text)
    if not rows:
        raise RuntimeError(f"the ESB calendar of the group {group_id} has no matches")
    _ROWS_CACHE[group_id] = rows
    return rows


def _start(row: Dict[str, Any]) -> Optional[str]:
    """``2026-11-25 20:30:00`` -> ``2026-11-25T20:30`` (Madrid local time, as the FEB calendar)."""
    day = str(row.get("matchDay") or "").strip()
    return day[:16].replace(" ", "T") if len(day) >= 16 else None


def calendar_matches(rows: List[Dict[str, Any]]) -> List[CalendarMatch]:
    """One ``CalendarMatch`` per row: a played one is a ``result`` with its score, any other a ``scheduled`` one with its kick-off."""
    out: List[CalendarMatch] = []
    for row in rows:
        played = str(row.get("state")) == "1"
        score = f"{row.get('localScore')}-{row.get('visitorScore')}" if played and row.get("localScore") is not None and row.get("visitorScore") is not None else None
        out.append(CalendarMatch(
            code=f"{CODE_PREFIX}{row['idMatch']}", kind="result" if played else "scheduled", round_index=int(row.get("round") or 0),
            home_id=str(row["idLocalTeam"]), home_name=str(row.get("nameLocalTeam") or "").strip(),
            away_id=str(row["idVisitorTeam"]), away_name=str(row.get("nameVisitorTeam") or "").strip(),
            score=score, start=None if played else _start(row)))
    return out


def http_matches(group_id: str) -> List[CalendarMatch]:
    """The calendar of a group as ``CalendarMatch`` (the default of ``MatchScheduleService``)."""
    return calendar_matches(http_rows(group_id))


def competition_of(rows: List[Dict[str, Any]]) -> Dict[str, str]:
    """What the index says of the competition of a group, from its rows: the category (``1ª DIVISION FEMENINA``), the phase and group (``1ª FASE · GRUPO A-1``) and the season."""
    row = rows[0] if rows else {}
    return {"competition": str(row.get("nameCategory") or "").strip(), "group": f"{str(row.get('nameCompetition') or '').strip()} {str(row.get('nameGroup') or '').strip()}".strip(),
            "season": str(row.get("season") or "")}
