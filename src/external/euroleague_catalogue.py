"""The Euroleague competitions of the catalogue (#1038, D6a of epic #872): which ones exist on the API, as paused entries of ``config/competitions.json``.

Scope decided on 23/11/2026 from the spike (``docs/evaluaciones/2026-11-23_euroleague-spike-1038.md``): the EuroLeague (``E``) and the EuroCup (``U``) since 2017/18 and the U18 Next Generation Tournament (``J``)
since 2019/20, the first season from which the play by play of each agrees with the official box in every game measured; before it the intents of two do not add up, so those seasons are not loaded (the rule of
the ten seasons: 2016/17 would be inside it and is not reliable). The API lists the seasons of a competition; an entry is a competition and the year it starts in. The U18 tournaments are many a season (the
qualifiers and the finals, each with a code of its own: ``JTA25``), so the entry of a season gathers them all and the source finds them by year. Nothing here turns anything on.
"""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

from src.external.euroleague_client import EuroleagueFetchError, EuroleagueNotFound
from src.external.euroleague_page import EuroleaguePageError

NAMES = {"E": "EuroLeague", "U": "EuroCup", "J": "U18 Next Generation"}
FIRST_YEARS = {"E": 2017, "U": 2017, "J": 2019}
PAUSE_NOTE = "paused until it is turned on"


def _entry(code: str, year: int, today: str) -> Dict[str, Any]:
    name = NAMES[code]
    season = f"{year}/{year + 1}"
    return {"competition": name, "season_label": season, "season_value": str(year), "league": "euroleague", "division": name, "gender": "M", "active": False,
            "euroleague": {"competition": code}, "label": f"Euroliga {name}", "note": f"{name} {season}: listed by the API on {today}; {PAUSE_NOTE}"}


def _years(client: Any, code: str) -> List[int]:
    return sorted({s["year"] for s in client.seasons(code) if s["year"] >= FIRST_YEARS[code]})


def new_entries(client: Any, existing: List[Dict[str, Any]], today: str) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """The paused entries to add and what happened to the rest: ``{already, empty, failed}`` (the seasons already in ``existing``, those that list no games and those that failed, with the reason). The
    seasons already in the catalogue are not even asked about. A senior season is asked for its games before it goes in; the U18 tournaments, whose games are many calendars, are taken as the API lists them."""
    have = {(e["euroleague"]["competition"], int(e["season_value"])) for e in existing if e.get("league") == "euroleague"}
    report: Dict[str, Any] = {"already": [], "empty": [], "failed": {}}
    entries: List[Dict[str, Any]] = []
    for code in NAMES:
        for year in _years(client, code):
            key = f"{code}{year}"
            if (code, year) in have:
                report["already"].append(key)
                continue
            if code != "J":
                try:
                    client.games(code, key)
                except (EuroleagueNotFound, EuroleaguePageError):
                    report["empty"].append(key)
                    continue
                except EuroleagueFetchError as error:
                    report["failed"][key] = str(error)
                    continue
            entries.append(_entry(code, year, today))
    return entries, report
