"""The FEB team roster: who is a "formación" player (issue #271).

``https://baloncestoenvivo.feb.es/equipo/<team id>`` (same id as in the matches) has a table with Nombre, Puesto,
Dorsal, Nacimiento, Nacionalidad, Formación (SI/NO), Altura and Peso. Each player links to
``Jugador.aspx?i=<team>&c=<player>`` and ``c`` is the ``idPlayer`` of the play-by-play, so the roster keys match the
live engine. The player's own page does not carry Formación. The HTML has no contract: columns are found by their
class or header text, not by position, and anything unreadable is "unknown" (None), never a guess. Public page, light
use: one request per team when a package is built. The roster is stored in the package as ``tables.roster``.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from datetime import date
from typing import Any, Callable, Dict, Iterable, List, Optional, Union

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

ROSTER_URL = "https://baloncestoenvivo.feb.es/equipo/{team_id}"
TIMEOUT_S = 15
_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
_PLAYER_ID = re.compile(r"[?&]c=(\d+)")
_DATE = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
_FIELDS = ("nombre", "puesto", "dorsal", "nacimiento", "nacionalidad", "formacion", "altura")
_FIELD_NAME = {"nombre": "name", "puesto": "position", "dorsal": "dorsal", "nacimiento": "birth",
               "nacionalidad": "nationality", "formacion": "formacion", "altura": "height"}


def _norm(text: str) -> str:
    """Lower case without accents: "Formación" -> "formacion"."""
    return "".join(c for c in unicodedata.normalize("NFKD", text.lower()) if not unicodedata.combining(c)).strip()


def _field(tokens: Iterable[str]) -> Optional[str]:
    """Which roster field a class list or header text names."""
    words = " ".join(_norm(t) for t in tokens)
    return next((f for f in _FIELDS if f in words), None)


def _clean(text: str) -> Optional[str]:
    value = " ".join(text.split())
    return None if value in ("", "-", "—") else value


def _birth(text: Optional[str]) -> Optional[str]:
    match = _DATE.search(text or "")
    if not match:
        return None
    day, month, year = (int(g) for g in match.groups())
    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return None


def _number(text: Optional[str]) -> Optional[int]:
    match = re.search(r"\d+", text or "")
    return int(match.group()) if match else None


def _formacion(text: Optional[str]) -> Optional[bool]:
    answer = _norm(text or "")
    return True if answer == "si" else False if answer == "no" else None


def _roster_table(soup: BeautifulSoup) -> Any:
    return next((t for t in soup.find_all("table") if t.find("a", href=_PLAYER_ID)), None)


def _columns(table: Any) -> List[Optional[str]]:
    """The field of each header cell, in order (used when a body cell has no class of its own)."""
    head = next((r for r in table.find_all("tr") if r.find("th")), None)
    return [_field((*th.get("class", []), th.get_text())) for th in head.find_all("th")] if head else []


def parse_roster(html: Union[str, bytes], team_id: str) -> Dict[str, Dict[str, Any]]:
    """``{player id: {team_id, name, formacion, birth, nationality, position, dorsal, height}}`` of a roster page."""
    if not html:
        return {}
    table = _roster_table(BeautifulSoup(html, "html.parser"))
    if table is None:
        return {}
    columns = _columns(table)
    roster: Dict[str, Dict[str, Any]] = {}
    for row in table.find_all("tr"):
        link = row.find("a", href=_PLAYER_ID)
        cells = row.find_all("td")
        if link is None or not cells:
            continue
        values: Dict[str, Optional[str]] = {}
        for i, cell in enumerate(cells):
            field = _field(cell.get("class", [])) or (columns[i] if len(columns) == len(cells) else None)
            if field and field not in values:
                values[field] = _clean(cell.get_text())
        roster[_PLAYER_ID.search(link["href"]).group(1)] = {
            "team_id": str(team_id), "name": values.get("nombre"), "formacion": _formacion(values.get("formacion")),
            "birth": _birth(values.get("nacimiento")), "nationality": values.get("nacionalidad"),
            "position": values.get("puesto"), "dorsal": _number(values.get("dorsal")), "height": _number(values.get("altura")),
        }
    return roster


def fetch_team_roster(team_id: Any, get: Optional[Callable[..., Any]] = None, timeout: float = TIMEOUT_S) -> Optional[Dict[str, Dict[str, Any]]]:
    """The roster of a team, or None when the page cannot be read (network, HTTP error, no roster in it)."""
    if get is None:
        import requests

        get = requests.get
    try:
        response = get(ROSTER_URL.format(team_id=team_id), headers=_HEADERS, timeout=timeout)
        response.raise_for_status()
        return parse_roster(response.content, str(team_id)) or None
    except Exception as exc:  # noqa: BLE001 - FEB is down or changed: the package is built without roster
        logger.warning("Roster of team %s not available: %s", team_id, exc)
        return None


def fetch_rosters(team_ids: Iterable[Any], get: Optional[Callable[..., Any]] = None) -> Optional[Dict[str, Dict[str, Any]]]:
    """The rosters of several teams merged into one table; a team that fails is asked once more (a hiccup of FEB's website
    must not leave the rival out of the package, #322) and, if it still fails, is left out; none at all is None."""
    merged: Dict[str, Dict[str, Any]] = {}
    for team_id in dict.fromkeys(str(t) for t in team_ids):
        merged.update(fetch_team_roster(team_id, get=get) or fetch_team_roster(team_id, get=get) or {})
    return merged or None
