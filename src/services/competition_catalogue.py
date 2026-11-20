"""The single catalogue of competitions (issue #724, step 2): ``config/competitions.json``.

One entry per competition and season (FEB, or a FBCYL group: ``"league": "fbcyl"`` with the ``fbcyl`` object the scraper needs) says everything about it: what the refresh scrapes (``competition_url``, ``season_*``, ``groups``, ``recheck_days``), what the packages
know of it (``level``, ``gender``, ``clubs``, ``rule_config``, ``group_rules``, and ``packages_groups``: the groups of the competition that get packages) and which
calendars the live recorder follows (``record``). ``category`` (``formacion``; absent is senior), ``age_group`` (``U14``/``U16``/``U18``/``U20``) and ``label`` (the name people read) are
the category of a youth competition (#914, ``competition_category``). Before it these lived in four files that drifted apart (the old refresh config, ``local_refresh.json``, the ``competitions``
of ``package_publish.json`` and the ``calendars`` of ``feb_watchlist.json``).

``packages: false`` (#875) marks a competition the staff does not play, like the youth championships of Mercado: it is scraped and goes to the web, but gets no live packages and is never recorded; its
gender and level still come from here (``package_catalog``), because the manifest reads them.

``active: false`` pauses an entry: it is neither scraped, published nor recorded, and its data stays where it is. Removing an entry never deletes data either: that is the
purge, a separate order that asks for confirmation. The metadata of the packages (level, gender, rules) survives a pause, because older seasons are still read.

The external sources (ACB, FIBA, NCAA; #884, epic #872) are competitions whose ``league`` is their source: they carry ``division``, ``gender`` and, where the source needs it (NCAA),
``conference`` (one competition per conference, never a flat list). They are read only by ``external_entries``: the refresh of the FEB archive, the live packages and the recorder never see them.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

DEFAULT_CATALOGUE = "config/competitions.json"
ALL_GROUPS = "all"
_REQUIRED = ("competition", "competition_url", "season_label", "season_value")
_REQUIRED_FBCYL = ("competition", "season_label", "season_value")
from src.utils.collection_utils import EXTERNAL_SOURCES

EXTERNAL_LEAGUES = EXTERNAL_SOURCES
LEAGUES = ("feb", "fbcyl", *EXTERNAL_LEAGUES)
CONFERENCE_REQUIRED = ("ncaa",)                 # the sources whose competitions are split by conference
_REQUIRED_EXTERNAL = ("competition", "season_label", "season_value", "division")


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


def _check_fiba(where: str, value: Any) -> Dict[str, Any]:
    """The ``fiba`` object of a FIBA entry: the ``event`` of its site (``fiba-u18-eurobasket-2025``) and, optionally, ``max_games``: how many games of it a run asks for at most (#887)."""
    if not isinstance(value, dict) or not isinstance(value.get("event"), str) or not value["event"].strip():
        raise ValueError(f"{where}: a fiba competition needs fiba.event, the event of the site of FIBA (fiba-u18-eurobasket-2025)")
    cap = value.get("max_games")
    if cap is not None and (isinstance(cap, bool) or not isinstance(cap, int) or cap < 1):
        raise ValueError(f"{where}: fiba.max_games must be a whole number of games, 1 or more, not {cap!r}")
    return {"event": value["event"].strip(), **({"max_games": cap} if cap is not None else {})}


def _check_acb(where: str, value: Any) -> Dict[str, Any]:
    """The ``acb`` object of an ACB entry: the ``competition_id`` and the ``edition_id`` of its API (the Liga Endesa 2019/20 is 1 and 84) and, optionally, ``max_games``: how many games of it a run asks for at most (#886)."""
    ids = ("competition_id", "edition_id")
    if not isinstance(value, dict) or any(isinstance(value.get(k), bool) or not isinstance(value.get(k), int) or value[k] < 1 for k in ids):
        raise ValueError(f"{where}: an acb competition needs acb.competition_id and acb.edition_id, whole numbers of the API of ACB (1 and 84: the Liga Endesa 2019/20)")
    cap = value.get("max_games")
    if cap is not None and (isinstance(cap, bool) or not isinstance(cap, int) or cap < 1):
        raise ValueError(f"{where}: acb.max_games must be a whole number of games, 1 or more, not {cap!r}")
    return {**{k: value[k] for k in ids}, **({"max_games": cap} if cap is not None else {})}


def _check_external(where: str, raw: Dict[str, Any]) -> Dict[str, Any]:
    """An external competition (ACB, FIBA, NCAA): its division, its gender and, where the source splits by them, its conference. Nothing to scrape: no URL, no groups."""
    from src.live_prep.competition_info import GENDERS

    league = raw["league"]
    missing = [k for k in _REQUIRED_EXTERNAL if not isinstance(raw.get(k), str) or not raw[k].strip()]
    if missing:
        raise ValueError(f"{where} lacks: {', '.join(missing)}")
    if raw.get("gender") not in GENDERS:
        raise ValueError(f"{where}: gender must be one of {GENDERS} (it lacks or is {raw.get('gender')!r})")
    conference = raw.get("conference")
    if conference is not None and (not isinstance(conference, str) or not conference.strip()):
        raise ValueError(f"{where}: conference must be a text")
    if conference is None and league in CONFERENCE_REQUIRED:
        raise ValueError(f"{where}: a {league} competition lacks: conference (one competition per conference)")
    extra = {"fiba": _check_fiba(where, raw.get("fiba"))} if league == "fiba" else {"acb": _check_acb(where, raw.get("acb"))} if league == "acb" else {}
    return {"source": league, "groups": "", "conference": conference.strip() if conference else None, **extra}


def _check(position: int, raw: Dict[str, Any]) -> Dict[str, Any]:
    """One entry, validated: ``ValueError`` names its position and the field."""
    from src.services.competition_category import check_category

    where = f"competitions entry #{position}"
    league = raw.get("league", "feb")
    if league not in LEAGUES:
        raise ValueError(f"{where}: league must be one of {LEAGUES}, not {league!r}")
    external = _check_external(where, raw) if league in EXTERNAL_LEAGUES else {}
    missing = [] if external else [k for k in (_REQUIRED if league == "feb" else _REQUIRED_FBCYL) if not isinstance(raw.get(k), str) or not raw[k].strip()]
    if missing:
        raise ValueError(f"{where} lacks: {', '.join(missing)}")
    groups = raw.get("groups", "")
    if external:
        groups = ""
    elif league == "fbcyl":
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
    return {**raw, **check_category(where, raw), **external, "league": league, "groups": groups, "active": active, "packages": packages, "recheck_days": days, "record": list(raw.get("record", [])), "packages_groups": list(raw.get("packages_groups", []))}


def load_catalogue(path: Any = DEFAULT_CATALOGUE) -> List[Dict[str, Any]]:
    """The validated entries of the catalogue (level, gender, clubs and rules are validated by ``normalize_catalog``, which names the position of a bad one)."""
    from src.live_prep.competition_info import normalize_catalog

    raw = json.loads(Path(path).read_text(encoding="utf-8")).get("competitions", [])
    entries = [_check(i, e) for i, e in enumerate(raw, start=1)]
    normalize_catalog(entries)
    seen = set()
    for i, e in enumerate(entries, start=1):
        key = (e["league"], _norm(e["competition"]), e["season_value"], e.get("group_value", "") or (e.get("fbcyl") or {}).get("competition_id", ""), (e.get("conference") or "").lower())
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
    """What the refresh scrapes: the active entries, every group of each FEB competition and the FBCYL groups listed. The external sources have their own jobs (``external_entries``): a failure of theirs never stops this one."""
    return [_fbcyl_entry(e) if e["league"] == "fbcyl" else _refresh_entry(e, []) for e in catalogue if e["active"] and e["league"] not in EXTERNAL_LEAGUES]


def external_entries(catalogue: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """The active external competitions (ACB, FIBA, NCAA), in the order of the catalogue: what their own refresh jobs and the publication of the external data read (#884)."""
    return [e for e in catalogue if e["active"] and e["league"] in EXTERNAL_LEAGUES]


def external_collections(catalogue: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """``{collection name: entry}`` of the active external competitions: ``<SOURCE>_<competition>_<season>_<conference>`` (``NCAA_D1_2026_SEC``), so the source reads from the name (``source_of``)
    and a conference is its own collection (#884)."""
    from src.database import get_collection_name

    return {get_collection_name(f"{e['league'].upper()}_{e['competition']}", e["season_value"], e.get("conference") or ""): e for e in external_entries(catalogue)}


def package_entries(catalogue: List[Dict[str, Any]]) -> List[Any]:
    """What the packages are made for: the active entries, narrowed to ``packages_groups`` (a competition scraped complete can publish only some of its groups). ``packages: false`` leaves one out (#875)."""
    return [_refresh_entry(e, list(e["packages_groups"])) for e in catalogue if e["active"] and e["league"] == "feb" and e["packages"]]


def fbcyl_groups(catalogue: List[Dict[str, Any]]) -> Dict[str, str]:
    """``{collection name: id of the group in the ESB calendar}`` of the active FBCYL entries: the matches of a FBCYL competition come from that calendar (issue #446)."""
    from src.database import get_collection_name

    return {get_collection_name(f"FBCYL_{e['competition']}", e["season_value"], ""): str(e["fbcyl"]["competition_id"]) for e in catalogue if e["active"] and e["league"] == "fbcyl"}


def package_catalog(catalogue: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """The ``competitions`` the packages match by name (level, gender, clubs, rules): one per competition: the entry with packages, then the active one, then the latest. Pausing keeps it."""
    from src.live_prep.competition_info import normalize_catalog

    chosen: Dict[str, Dict[str, Any]] = {}
    for entry in (e for e in catalogue if e["league"] == "feb"):          # FBCYL has no packages
        key = _norm(entry["competition"])
        if key not in chosen or (entry["packages"], entry["active"]) >= (chosen[key]["packages"], chosen[key]["active"]):    # packages first: a past season listed later must not take the clubs and rules of the current one (#876)
            chosen[key] = entry
    return normalize_catalog(chosen.values())


def record_calendars(catalogue: List[Dict[str, Any]]) -> List[str]:
    """The calendars the live recorder scans: those of the active entries, in order, without repeats."""
    return list(dict.fromkeys(url for e in catalogue if e["active"] and e["league"] == "feb" and e["packages"] for url in e["record"]))
