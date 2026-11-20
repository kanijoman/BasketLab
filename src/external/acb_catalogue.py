"""The ACB editions of the catalogue (#886, D2c): which ones exist on the site, as paused entries of ``config/competitions.json``.

Scope decided on 12/11/2026: the Liga Endesa since 2019/20. ``new_entries`` asks the API for the editions (the id of an edition is the one of the site: it is read, not computed), then for the clubs of each
one, and returns an entry, ``active: false``, for every edition that exists and lists clubs, leaving alone what the catalogue already has. The Copa del Rey, the Supercopa and the Minicopa are other
competitions of the site (other ``competition_id``) and are not here yet. Nothing here turns anything on.
"""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

from src.external.acb_client import AcbFetchError, AcbNotFound

LIGA_ENDESA = 1
FIRST_YEAR = 2019                      # 2019/20: from when the site has the play by play and the shots of every game (spike #886)


def _entry(year: int, edition_id: int, clubs: int, today: str) -> Dict[str, Any]:
    season = f"{year}/{year + 1}"
    return {"competition": "Liga Endesa", "season_label": season, "season_value": str(year), "league": "acb", "division": "Liga Endesa", "gender": "M", "active": False,
            "acb": {"competition_id": LIGA_ENDESA, "edition_id": edition_id}, "label": "ACB Liga Endesa",
            "note": f"ACB Liga Endesa {season}: {clubs} clubs listed on {today}; paused until it is turned on"}


def new_entries(client: Any, existing: List[Dict[str, Any]], today: str) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """The paused entries to add and what happened to the rest: ``{already, empty, missing, failed}`` (the editions already in ``existing``, those that list no clubs, those the site does not answer for and
    those that failed, with the reason). The editions already in the catalogue are not even asked about."""
    have = {e["acb"]["edition_id"] for e in existing if isinstance(e.get("acb"), dict) and e["acb"].get("competition_id") == LIGA_ENDESA}
    report: Dict[str, Any] = {"already": [], "empty": [], "missing": [], "failed": {}}
    entries: List[Dict[str, Any]] = []
    for year, edition_id in sorted(client.editions(LIGA_ENDESA).items()):
        if year < FIRST_YEAR:
            continue
        if edition_id in have:
            report["already"].append(edition_id)
            continue
        try:
            clubs = client.teams(edition_id, LIGA_ENDESA)
        except AcbNotFound:
            report["missing"].append(edition_id)
            continue
        except AcbFetchError as error:
            report["failed"][edition_id] = str(error)
            continue
        if not clubs:
            report["empty"].append(edition_id)
            continue
        entries.append(_entry(year, edition_id, len(clubs), today))
    return entries, report
