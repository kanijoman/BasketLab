"""The CLUB of a FEB team: the stable text that links a team to the same team of other seasons (issue #862).

``https://baloncestoenvivo.feb.es/equipo/<team id>`` shows the sponsored name in its title (it changes with the sponsor) and the name of the club in the block ``div.box-club``
(``CLUB BALONCESTO FEMENINO LEON``). The team ids change every season and the ``teamCode`` only travels with the games, so before its first game of the season this is the
only public handle of a team. Public page, light use: one request per team that is asked about. Anything unreadable is None, never a guess.
"""

from __future__ import annotations

import logging
import unicodedata
from typing import Any, Callable, Optional

from bs4 import BeautifulSoup

from .roster_fetcher import ROSTER_URL, TIMEOUT_S, _HEADERS

logger = logging.getLogger(__name__)


def normalize_club(name: Optional[str]) -> str:
    """``" Peñas  Huesca "`` -> ``"PENAS HUESCA"``: a club name without case, accents or extra spaces."""
    plain = "".join(c for c in unicodedata.normalize("NFKD", name or "") if not unicodedata.combining(c))
    return " ".join(plain.upper().split())


def parse_club_name(html: Any) -> Optional[str]:
    """The club name of a team page, or None when the page has no club block."""
    node = BeautifulSoup(html, "html.parser").select_one("div.box-club div.nombre")
    return " ".join(node.get_text().split()) or None if node else None


def fetch_club_name(team_id: Any, get: Optional[Callable[..., Any]] = None, timeout: float = TIMEOUT_S) -> Optional[str]:
    """The club of a team, or None when the page cannot be read (network, HTTP error, no club in it)."""
    if get is None:
        import requests

        get = requests.get
    try:
        response = get(ROSTER_URL.format(team_id=team_id), headers=_HEADERS, timeout=timeout)
        response.raise_for_status()
        return parse_club_name(response.content)
    except Exception as exc:  # noqa: BLE001 - FEB is down or changed: the team just starts at 0 until its first game
        logger.warning("Club of team %s not available: %s", team_id, exc)
        return None
