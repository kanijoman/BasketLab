"""The «Trayectoria» table of a FEB player page (``baloncestoenvivo.feb.es/jugador/<team>/<player>``): one line per season and team with the dates of alta and baja (#1082).

A baja filled for the team of the current season means the player is no longer there: the individual lists of that team and the DOCX of the individual scouting leave him out. The line is tied
to the team by the id of its link (``Equipo.aspx?i=``), the same id the boxes carry, never by name. A page that has no table is a ``TrajectoryError`` (a change of format is visible, it is never «no bajas»).
"""
from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup

_TEAM = re.compile(r"[?&]i=(\d+)")
_TABLE_ID = "trayectoriaDataGrid"


class TrajectoryError(ValueError):
    """The page does not have the table, or a line of it is not what we know how to read."""


def _date(text: str) -> Optional[str]:
    """``dd/mm/yyyy`` -> ``yyyy-mm-dd``; blank -> ``None``; anything else is an error."""
    if not text:
        return None
    try:
        return datetime.strptime(text, "%d/%m/%Y").strftime("%Y-%m-%d")
    except ValueError as error:
        raise TrajectoryError(f"date {text!r} is not dd/mm/yyyy") from error


def parse_trajectory(html: Any) -> List[Dict[str, Optional[str]]]:
    """``[{season, category, team_id, alta, baja}]`` in the order of the page; dates ``yyyy-mm-dd`` or ``None``."""
    table = BeautifulSoup(html, "html.parser").find("table", id=lambda i: bool(i) and i.endswith(_TABLE_ID))
    if table is None:
        raise TrajectoryError("the player page has no trajectory table")
    lines: List[Dict[str, Optional[str]]] = []
    for row in table.find_all("tr"):
        cells = row.find_all("td")
        if not cells:
            continue                                                    # the header
        link = cells[2].find("a") if len(cells) >= 6 else None
        found = _TEAM.search(link.get("href", "")) if link else None
        if not found:
            raise TrajectoryError("a line of the trajectory has no team id")
        text = [c.get_text(strip=True) for c in cells]
        lines.append({"season": text[0], "category": text[1], "team_id": found.group(1), "alta": _date(text[4]), "baja": _date(text[5])})
    return lines


def left_team(lines: List[Dict[str, Optional[str]]], team_id: str, today: str) -> bool:
    """``True`` when the line of ``team_id`` has a baja already reached by ``today`` (``yyyy-mm-dd``). No line for the team, no baja or a baja still to come: he stays."""
    return any(l["team_id"] == str(team_id) and l["baja"] is not None and l["baja"] <= today for l in lines)


def fetch_trajectory(team_id: str, player_id: str) -> Optional[List[Dict[str, Optional[str]]]]:
    """The lines of the player page of the FEB, or ``None`` when it cannot be had or read: a player is never hidden for not knowing."""
    import requests

    try:
        response = requests.get(f"https://baloncestoenvivo.feb.es/jugador/{team_id}/{player_id}", headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        response.raise_for_status()
        return parse_trajectory(response.content)
    except (requests.RequestException, TrajectoryError):
        return None


def today_iso() -> str:
    return date.today().isoformat()
