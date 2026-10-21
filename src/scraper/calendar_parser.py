"""Parser of the FEB calendar page that KEEPS the matches that have not been played yet.

``FEBScraper`` only needs finished matches (it discards rows without a score). The live feature
needs the upcoming ones: team, rival, kick-off time and the match code that identifies the game
in FEB's live API.

Page structure (``/calendario/<competition>/9/<season>``): one ``<table>`` per round inside
``div.tableLayout de dos columnas``; each row is ``td.equipo.local`` | ``td.resultado`` (link
text ``71-64``) or ``td.fecha`` (``SÁBADO<br>17/04/2027<br>19:00``) | ``td.equipo.visitante``.
Teams are identified by ``Equipo.aspx?i=<id>`` (the same stable id stored in the games), the
match by ``Partido.aspx?p=<code>``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, Union

from bs4 import BeautifulSoup

_TEAM_ID = re.compile(r"Equipo\.aspx\?i=(\d+)", re.I)
_MATCH_CODE = re.compile(r"Partido\.aspx\?p=(\d+)", re.I)
_SCORE = re.compile(r"^\d+\s*-\s*\d+$")
_DATE = re.compile(r"(\d{2})/(\d{2})/(\d{4}).*?(\d{1,2}):(\d{2})", re.S)


@dataclass(frozen=True)
class CalendarMatch:
    code: str
    kind: str                      # "result" (score shown) | "scheduled" (date shown)
    round_index: int               # 1-based position of the round's table in the page
    home_id: str
    home_name: str
    away_id: str
    away_name: str
    score: Optional[str] = None    # "71-64" for results
    start: Optional[str] = None    # "YYYY-MM-DDTHH:MM", Europe/Madrid local time, for scheduled
    phase: Optional[str] = None    # knockout phase ("1/16 Final") of a match read from ``Series.aspx``; not serialised

    def involves(self, team_id: str) -> bool:
        return str(team_id) in (self.home_id, self.away_id)

    def opponent_of(self, team_id: str) -> Optional[Tuple[str, str]]:
        if str(team_id) == self.home_id:
            return self.away_id, self.away_name
        if str(team_id) == self.away_id:
            return self.home_id, self.home_name
        return None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "code": self.code, "kind": self.kind, "round": self.round_index, "score": self.score, "start": self.start,
            "home": {"id": self.home_id, "name": self.home_name},
            "away": {"id": self.away_id, "name": self.away_name},
        }


def _team(cell) -> Optional[Tuple[str, str]]:
    link = cell.find("a", href=_TEAM_ID) if cell else None
    if link is None:
        return None
    return _TEAM_ID.search(link["href"]).group(1), link.get_text(" ", strip=True)


def _parse_row(row, round_index: int) -> Optional[CalendarMatch]:
    local, visit = _team(row.find("td", class_="local")), _team(row.find("td", class_="visitante"))
    cell = row.find("td", class_="resultado") or row.find("td", class_="fecha")
    link = cell.find("a", href=_MATCH_CODE) if cell else None
    if not (local and visit and link):
        return None
    code = _MATCH_CODE.search(link["href"]).group(1)
    text = link.get_text(" ", strip=True)
    if cell.get("class") and "resultado" in cell["class"] and _SCORE.match(text):
        return CalendarMatch(code, "result", round_index, *local, *visit, score=text.replace(" ", ""))
    date = _DATE.search(link.get_text("\n", strip=True))
    start = f"{date.group(3)}-{date.group(2)}-{date.group(1)}T{int(date.group(4)):02d}:{date.group(5)}" if date else None
    return CalendarMatch(code, "scheduled", round_index, *local, *visit, start=start)


def parse_calendar(html: Union[str, bytes]) -> List[CalendarMatch]:
    """All matches of the page in page order (finished and not yet played)."""
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser", **({"from_encoding": "utf-8"} if isinstance(html, bytes) else {}))
    matches: List[CalendarMatch] = []
    for container in soup.find_all("div", class_="tableLayout de dos columnas"):
        for round_index, table in enumerate(container.find_all("table"), 1):
            for row in table.find_all("tr")[1:]:
                match = _parse_row(row, round_index)
                if match:
                    matches.append(match)
    return matches


def _series_match(row, round_index: int, phase: str) -> Optional[CalendarMatch]:
    """A row of a series table: ``td`` teams (two links) | ``td`` score link (``76 - 86`` or ``* - *``) | ``td`` date."""
    cells = row.find_all("td")
    if len(cells) < 3:
        return None
    teams = [(_TEAM_ID.search(a["href"]).group(1), a.get_text(" ", strip=True)) for a in cells[0].find_all("a", href=_TEAM_ID)]
    link = cells[1].find("a", href=_MATCH_CODE)
    if len(teams) != 2 or link is None:
        return None
    code, text = _MATCH_CODE.search(link["href"]).group(1), link.get_text(" ", strip=True)
    if _SCORE.match(text):
        return CalendarMatch(code, "result", round_index, *teams[0], *teams[1], score=text.replace(" ", ""), phase=phase)
    date = _DATE.search(cells[2].get_text("\n", strip=True))
    start = f"{date.group(3)}-{date.group(2)}-{date.group(1)}T{int(date.group(4)):02d}:{date.group(5)}" if date else None
    return CalendarMatch(code, "scheduled", round_index, *teams[0], *teams[1], start=start, phase=phase)


def parse_series(html: Union[str, bytes]) -> List[CalendarMatch]:
    """Matches of a ``Series.aspx`` page (knockout phases, which are not in the calendar), in page order.

    Each tie is an ``h1.titulo-modulo`` (``"1/16 Final. HOME - AWAY"``) followed by a table with one row per
    match of the tie; ``round_index`` is the match number inside its tie and ``phase`` the text before the first dot.
    """
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser", **({"from_encoding": "utf-8"} if isinstance(html, bytes) else {}))
    matches: List[CalendarMatch] = []
    for title in soup.find_all("h1", class_="titulo-modulo"):
        table = title.find_next_sibling("table")
        if table is None:
            continue
        phase = title.get_text(" ", strip=True).split(". ", 1)[0].strip()
        rows = (_series_match(row, n, phase) for n, row in enumerate(table.find_all("tr"), 1))
        matches.extend(m for m in rows if m)
    return matches


def phase_matches(matches: List[CalendarMatch], group_label: str, strict: bool = False) -> List[CalendarMatch]:
    """The matches of the phase a group label names (``Play-offs 1/16 Final`` -> the ``1/16 Final`` ties).

    One series page can hold every phase of a competition (Copa de España). The most specific phase named in the label counts (``Final`` is
    inside ``1/16 Final``); when the label names none (``2ºA-1ºB Final``, named after its series) every match is kept, unless ``strict``
    (the series is shared by several groups: a round not drawn yet has no matches, it does not take those of the others).
    """
    label = group_label.lower()
    named = {m.phase.lower() for m in matches if m.phase and m.phase.lower() in label}
    specific = {p for p in named if not any(p != q and p in q for q in named)}
    chosen = [m for m in matches if m.phase and m.phase.lower() in specific]
    return chosen if chosen or strict else matches
