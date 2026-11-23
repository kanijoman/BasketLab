"""The FIBA events of the catalogue (#887, D3b): which ones exist on the site, as paused entries of ``config/competitions.json``.

``candidate_events`` lists the events FIBA has each year in the scope decided on 18/11/2026: the youth EuroBasket championships (U16, U18, U20) of both sexes, the U19 World Cup of both sexes and the absolute
EuroBasket of both sexes. ``new_entries`` asks the site about each (the page of the event, politely) and returns an entry, ``active: false``, only for the ones that exist and list games, leaving alone what the
catalogue already has. U16 and U18 are ``formacion`` with their age group; U19, U20 and the absolute events are senior (#918). Nothing here turns anything on.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Tuple

from src.external.fiba_client import FibaFetchError, FibaNotFound

YOUTH_AGES = (16, 18, 20)
FORMATION = {16: "U16", 18: "U18"}                       # the ages whose championships are formacion; U19 and U20 are senior (#918)


def _event(slug: str, year: int, competition: str, division: str, gender: str, **extra: Any) -> Dict[str, Any]:
    return {"event": slug, "competition": competition, "division": division, "gender": gender, "season_value": str(year), "season_label": str(year), "label": f"FIBA {competition}", **extra}


def candidate_events(years: Iterable[int]) -> List[Dict[str, Any]]:
    """The events FIBA may have in each of ``years``, in a stable order (a year at a time: youth by age, the U19 World Cup, the absolute events; men first)."""
    out: List[Dict[str, Any]] = []
    for year in years:
        for age in YOUTH_AGES:
            formation = {"category": "formacion", "age_group": FORMATION[age]} if age in FORMATION else {}
            out.append(_event(f"fiba-u{age}-eurobasket-{year}", year, f"U{age} EuroBasket", f"U{age}", "M", **formation))
            out.append(_event(f"fiba-u{age}-womens-eurobasket-{year}", year, f"U{age} EuroBasket Women", f"U{age}", "F", **formation))
        out.append(_event(f"fiba-u19-basketball-world-cup-{year}", year, "U19 World Cup", "U19", "M"))
        out.append(_event(f"fiba-u19-womens-basketball-world-cup-{year}", year, "U19 World Cup Women", "U19", "F"))
        out.append(_event(f"fiba-eurobasket-{year}", year, "EuroBasket", "Senior", "M"))
        out.append(_event(f"fiba-womens-eurobasket-{year}", year, "EuroBasket Women", "Senior", "F"))
    return out


CLUB_COMPETITIONS = (("euroleague-women", "EuroLeague Women"), ("eurocup-women", "EuroCup Women"))      # run by FIBA Europe, in the same site (#1039)


def candidate_club_events(seasons: Iterable[int]) -> List[Dict[str, Any]]:
    """The club competitions FIBA may have in each season (the year it STARTS in, as FEB's): the EuroLeague Women and the EuroCup Women. A season is named by the SHORT form of its two years
    (``euroleague-women-25-26``): the long one (``-2025-26``) is answered with the generic shell of the page, as is any season that does not exist (#1039: only 2024/25 onwards do)."""
    out: List[Dict[str, Any]] = []
    for year in seasons:
        for stem, competition in CLUB_COMPETITIONS:
            out.append({"event": f"{stem}-{year % 100:02d}-{(year + 1) % 100:02d}", "competition": competition, "division": "Senior", "gender": "F", "season_value": str(year),
                        "season_label": f"{year}/{year + 1}", "label": f"FIBA {competition}"})
    return out


def _entry(candidate: Dict[str, Any], games: int, today: str) -> Dict[str, Any]:
    entry = {"competition": candidate["competition"], "season_label": candidate["season_label"], "season_value": candidate["season_value"], "league": "fiba", "division": candidate["division"],
             "gender": candidate["gender"], "active": False, "fiba": {"event": candidate["event"]}, "label": candidate["label"],
             "note": f"FIBA {candidate['competition']} {candidate['season_label']}: {games} games listed on {today}; paused until it is turned on"}
    if "category" in candidate:
        entry.update({"category": candidate["category"], "age_group": candidate["age_group"]})
    return entry


def new_entries(client: Any, existing: List[Dict[str, Any]], years: Iterable[int], today: str, club_seasons: Iterable[int] = ()) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """The paused entries to add and what happened to the rest: ``{already, empty, missing, failed}`` (the events already in ``existing``, those that list no games, those that are not on the site and those that
    failed to answer, with the reason). The events already in the catalogue are not even asked about."""
    have = {e["fiba"]["event"] for e in existing if isinstance(e.get("fiba"), dict) and e["fiba"].get("event")}
    report: Dict[str, Any] = {"already": [], "empty": [], "missing": [], "failed": {}}
    entries: List[Dict[str, Any]] = []
    for candidate in [*candidate_events(years), *candidate_club_events(club_seasons)]:
        slug = candidate["event"]
        if slug in have:
            report["already"].append(slug)
            continue
        try:
            games = client.event_games(slug)
        except FibaNotFound:
            report["missing"].append(slug)
            continue
        except FibaFetchError as error:
            report["failed"][slug] = str(error)
            continue
        real = [g for g in games if g.get("teams")]                          # an event whose games are only the shell of the page has no games yet
        if not real:
            report["empty"].append(slug)
            continue
        entries.append(_entry(candidate, len(real), today))
    return entries, report
