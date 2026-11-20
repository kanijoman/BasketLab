"""The public pages of ACB as data (#886, D2a of epic #872): the match centre (``live.acb.com/partidos/<local>-vs-<visitante>-<id>/<tab>``) and the page of a player (``acb.com/es/liga/jugadores/<nombre>-<id>/<tab>``).

Both are Next applications whose data travels in the ``self.__next_f.push([1, "…"])`` chunks of their HTML, as FIBA's: ``extract_flight`` joins them (the same reader as FIBA's). Only the calendar needs the
API of the site (``acb_client``); everything here is public HTML. Pure functions, no I/O.

A page can come back without its data (a version of the site with the shell only) or cut in the middle: ``check_page`` raises ``GenericPage`` or ``CutPage`` so the client asks again, and ``AcbPageError``
for a page whose format is not the one this reader knows (the site changed: it has to be seen, not asked again).
"""
from __future__ import annotations

from src.external import fiba_page

PAGE_MARKERS = {
    "jugadas": '"plays":[',               # the play by play of a game
    "estadisticas": '"statsByPeriods"',   # the box score of a game
    "temporada": '"birthDate"',           # the bio of a player (and his season)
    "zonas-de-tiro": '"seasonShots"',     # the shots of a player with their coordinates
}


class AcbPageError(ValueError):
    """The page is not the page of ACB this reader knows."""


class GenericPage(AcbPageError):
    """The page has no data (the shell of the site): ask again."""


class CutPage(AcbPageError):
    """The page has its data cut in the middle: ask again."""


def extract_flight(html: str) -> str:
    """The text of the data chunks of a Next page, joined and unescaped (``GenericPage`` when it has none)."""
    try:
        return fiba_page.extract_flight(html)
    except fiba_page.GenericPage as error:
        raise GenericPage(str(error)) from error


def check_page(kind: str, flight: str) -> None:
    """Raise ``CutPage`` when the flight of a page of ``kind`` (a key of ``PAGE_MARKERS``) does not hold the data of that kind: the response ended early, or it is the shell of the site (ask again)."""
    if PAGE_MARKERS[kind] not in flight:
        raise CutPage(f"the page has no {kind} data")
