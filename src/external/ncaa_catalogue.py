"""The NCAA D1 competitions of the catalogue (#888, D4; #966): which ones exist in a season, as paused entries of ``config/competitions.json``.

One competition per conference, season and sex (decided on 13/11/2026: published by conference, never a flat list of hundreds of teams). The competition is named by its sex («D1 Men», «D1 Women»)
because a collection name has no gender (``NCAA_D1_2025_SEC``) and the SEC of both sexes would be one. The season is the year it STARTS in, as FEB's (2025 is 2025/26); ESPN names it by the
year it ends in and the client converts. The conferences of a season are the ones ESPN lists FOR THAT SEASON, so a conference that did not exist yet (the new Pac-12 of 2026/27) has no entry in the
earlier one and a team that changed conference is not moved back in time (#966). Nothing here turns anything on: ``active: false`` until a batch is chosen.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Tuple

from src.external.ncaa_client import NcaaFetchError

SEXES = (("M", "Men"), ("F", "Women"))


def _entry(season: int, gender: str, name: str, conference: Dict[str, str], today: str) -> Dict[str, Any]:
    return {"competition": f"D1 {name}", "season_label": f"{season}/{season + 1}", "season_value": str(season), "league": "ncaa", "division": "D1", "gender": gender, "conference": conference["short"],
            "active": False, "ncaa": {"conference_id": conference["id"]}, "label": f"NCAA D1 {name} · {conference['name']}",
            "note": f"NCAA D1 {name} {season}/{season + 1}, {conference['name']}: listed by ESPN on {today}; paused until a batch turns it on"}


def _have(existing: Iterable[Dict[str, Any]]) -> set:
    return {(e["gender"], e["season_value"], (e.get("ncaa") or {}).get("conference_id")) for e in existing if e.get("league") == "ncaa"}


def new_entries(client: Any, existing: List[Dict[str, Any]], today: str, seasons: List[int]) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """The paused entries to add and what happened to the rest: ``{already, failed}`` (the entries the catalogue already has, and the sexes whose conferences could not be read, with the reason).
    What is already in the catalogue is left alone."""
    have = _have(existing)
    report: Dict[str, Any] = {"already": [], "failed": {}}
    entries: List[Dict[str, Any]] = []
    for season in seasons:
        for gender, name in SEXES:
            try:
                conferences = client.conferences(gender, season)
            except NcaaFetchError as error:
                reason = f"{season}: {error}"
                report["failed"][gender] = f"{report['failed'][gender]}; {reason}" if gender in report["failed"] else reason
                continue
            for conference in conferences:
                if (gender, str(season), conference["id"]) in have:
                    report["already"].append((gender, str(season), conference["id"]))
                else:
                    entries.append(_entry(season, gender, name, conference, today))
    return entries, report
