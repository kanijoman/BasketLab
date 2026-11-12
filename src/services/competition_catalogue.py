"""The single catalogue of competitions (issue #724, step 2): ``config/competitions.json``.

One entry per competition and season (FEB, or a FBCYL group: ``"league": "fbcyl"`` with the ``fbcyl`` object the scraper needs) says everything about it: what the refresh scrapes (``competition_url``, ``season_*``, ``groups``, ``recheck_days``), what the packages
know of it (``level``, ``gender``, ``clubs``, ``rule_config``, ``group_rules``, and ``packages_groups``: the groups of the competition that get packages) and which
calendars the live recorder follows (``record``). Before it these lived in four files that drifted apart (the old refresh config, ``local_refresh.json``, the ``competitions``
of ``package_publish.json`` and the ``calendars`` of ``feb_watchlist.json``).

``packages: false`` (#875) marks a competition the staff does not play, like the youth championships of Mercado: it is scraped and goes to the web, but gets no live packages and is never recorded; its
gender and level still come from here (``package_catalog``), because the manifest reads them.

``active: false`` pauses an entry: it is neither scraped, published nor recorded, and its data stays where it is. Removing an entry never deletes data either: that is the
purge, a separate order that asks for confirmation. The metadata of the packages (level, gender, rules) survives a pause, because older seasons are still read.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

DEFAULT_CATALOGUE = "config/competitions.json"
ALL_GROUPS = "all"
_REQUIRED = ("competition", "competition_url", "season_label", "season_value")
_REQUIRED_FBCYL = ("competition", "season_label", "season_value")
LEAGUES = ("feb", "fbcyl")


def _norm(name: str) -> str:
    from src.scraper.schedule_client import normalize_name

    return normalize_name(name)


def _check_fbcyl(where: str, value: Any) -> None:
    """The ``fbcyl`` object of a FBCYL entry: the group (``competition_id``) and the ``category`` the scraper needs; ``gender`` and ``territory`` are texts too."""
    if not isinstance(value, dict):
        raise ValueError(f"{where}: fbcyl must be an object with competition_id and category")
    for key in ("competition_id", "category"):
        if not isinstance(value.get(key), str) or not value[key].strip():
            raise ValueError(f"{where}: fbcyl lacks: {key}")
    for key in ("gender", "territory"):
        if key in value and not isinstance(value[key], str):
            raise ValueError(f"{where}: fbcyl.{key} must be a text")


def _check(position: int, raw: Dict[str, Any]) -> Dict[str, Any]:
    """One entry, validated: ``ValueError`` names its position and the field."""
    where = f"competitions entry #{position}"
    league = raw.get("league", "feb")
    if league not in LEAGUES:
        raise ValueError(f"{where}: league must be one of {LEAGUES}, not {league!r}")
    missing = [k for k in (_REQUIRED if league == "feb" else _REQUIRED_FBCYL) if not isinstance(raw.get(k), str) or not raw[k].strip()]
    if missing:
        raise ValueError(f"{where} lacks: {', '.join(missing)}")
    groups = raw.get("groups", "")
    if league == "fbcyl":
        groups = ""
        _check_fbcyl(where, raw.get("fbcyl"))
    else:
        if groups not in ("", ALL_GROUPS):
            raise ValueError(f"{where}: groups must be \"{ALL_GROUPS}\" or absent, not {groups!r}")
        if groups == ALL_GROUPS and (raw.get("group_value") or raw.get("group_label")):
            raise ValueError(f"{where}: groups \"{ALL_GROUPS}\" excludes group_value and group_label")
        if groups != ALL_GROUPS and not (raw.get("group_value") and raw.get("group_label")):
            raise ValueError(f"{where}: a single group needs group_value and group_label")
    active = raw.get("active", True)
    if not isinstance(active, bool):
        raise ValueError(f"{where}: active must be true or false, not {active!r}")
    packages = raw.get("packages", True)
    if not isinstance(packages, bool):
        raise ValueError(f"{where}: packages must be true or false, not {packages!r}")
    days = raw.get("recheck_days", 0)
    if isinstance(days, bool) or not isinstance(days, int) or days < 0:
        raise ValueError(f"{where}: recheck_days must be a whole number of days, 0 or more, not {days!r}")
    for key in ("record", "packages_groups"):
        if not isinstance(raw.get(key, []), list) or any(not isinstance(v, str) for v in raw.get(key, [])):
            raise ValueError(f"{where}: {key} must be a list of texts")
    return {**raw, "league": league, "groups": groups, "active": active, "packages": packages, "recheck_days": days, "record": list(raw.get("record", [])), "packages_groups": list(raw.get("packages_groups", []))}


def load_catalogue(path: Any = DEFAULT_CATALOGUE) -> List[Dict[str, Any]]:
    """The validated entries of the catalogue (level, gender, clubs and rules are validated by ``normalize_catalog``, which names the position of a bad one)."""
    from src.live_prep.competition_info import normalize_catalog

    raw = json.loads(Path(path).read_text(encoding="utf-8")).get("competitions", [])
    entries = [_check(i, e) for i, e in enumerate(raw, start=1)]
    normalize_catalog(entries)
    seen = set()
    for i, e in enumerate(entries, start=1):
        key = (e["league"], _norm(e["competition"]), e["season_value"], e.get("group_value", "") or (e.get("fbcyl") or {}).get("competition_id", ""))
        if key in seen:
            raise ValueError(f"competitions entry #{i}: {e['competition']} {e['season_label']} is listed twice")
        seen.add(key)
    return entries


def _refresh_entry(entry: Dict[str, Any], group_filter: List[str]) -> Any:
    from src.services.competition_refresh import RefreshEntry

    return RefreshEntry(
        competition_url=entry["competition_url"], season_value=entry["season_value"], competition_label=entry["competition"], season_label=entry["season_label"],
        group_value=entry.get("group_value", ""), group_label=entry.get("group_label", ""), year=entry.get("year", "2025"), groups=entry["groups"],
        group_filter=group_filter, recheck_days=entry["recheck_days"])


def _fbcyl_entry(entry: Dict[str, Any]) -> Any:
    from src.services.competition_refresh import RefreshEntry

    fbcyl = {"gender": "", "territory": "0", **entry["fbcyl"]}
    return RefreshEntry(competition_url="", season_value=entry["season_value"], competition_label=entry["competition"], season_label=entry["season_label"],
                        year=entry["season_value"], league="fbcyl", fbcyl=fbcyl)


def refresh_entries(catalogue: List[Dict[str, Any]]) -> List[Any]:
    """What the refresh scrapes: the active entries, every group of each FEB competition and the FBCYL groups listed."""
    return [_fbcyl_entry(e) if e["league"] == "fbcyl" else _refresh_entry(e, []) for e in catalogue if e["active"]]


def package_entries(catalogue: List[Dict[str, Any]]) -> List[Any]:
    """What the packages are made for: the active entries, narrowed to ``packages_groups`` (a competition scraped complete can publish only some of its groups). ``packages: false`` leaves one out (#875)."""
    return [_refresh_entry(e, list(e["packages_groups"])) for e in catalogue if e["active"] and e["league"] == "feb" and e["packages"]]


def fbcyl_groups(catalogue: List[Dict[str, Any]]) -> Dict[str, str]:
    """``{collection name: id of the group in the ESB calendar}`` of the active FBCYL entries: the matches of a FBCYL competition come from that calendar (issue #446)."""
    from src.database import get_collection_name

    return {get_collection_name(f"FBCYL_{e['competition']}", e["season_value"], ""): str(e["fbcyl"]["competition_id"]) for e in catalogue if e["active"] and e["league"] == "fbcyl"}


def package_catalog(catalogue: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """The ``competitions`` the packages match by name (level, gender, clubs, rules): one per competition, the active entry if there is one, else the latest. Pausing keeps it."""
    from src.live_prep.competition_info import normalize_catalog

    chosen: Dict[str, Dict[str, Any]] = {}
    for entry in (e for e in catalogue if e["league"] == "feb"):          # FBCYL has no packages
        key = _norm(entry["competition"])
        if key not in chosen or entry["active"] or not chosen[key]["active"]:
            chosen[key] = entry
    return normalize_catalog(chosen.values())


def record_calendars(catalogue: List[Dict[str, Any]]) -> List[str]:
    """The calendars the live recorder scans: those of the active entries, in order, without repeats."""
    return list(dict.fromkeys(url for e in catalogue if e["active"] and e["league"] == "feb" and e["packages"] for url in e["record"]))
