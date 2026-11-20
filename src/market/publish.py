"""The Talent publication (B2, #878): one sealed file per competition and season, and a manifest of its own.

A competition's file holds ONE ROW PER PLAYER, TEAM AND COMPETITION (``season_rows`` and the modules around it); competitions are never mixed (``competitions``). The file is sealed for the
``talent`` scope (and the open one while the beta is open, as in ``web-data``) with the same sealing as the rest of the web (``team_reports.seal_file``): the name carries the hash of the content,
so it never changes in place, and an unchanged competition keeps its bytes (sealing is random, rewriting it would invalidate every cache). ``index.json`` is the only file that keeps its name.

The branch carries ``frontend/vercel.json`` (the same guard as ``web-data``): the Vercel projects of the repository build every branch and this one has no project, so the folder exists and its deployments are off.

It is published in its own branch by its own workflow (``talent-data.yml``): two writers on the branch of ``web-data`` would race, and a failure of this one must not stop that one.
What costs here is the export of every collection; the output is deterministic, so a run with no new game rewrites nothing. A cache of the export per competition (as ``build_cache`` does for
``web-data``) is the next step if the run gets long.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence

from src.live_prep.publisher import VERCEL_GUARD
from src.local_data.export import export_collection
from src.local_data.team_reports import seal_file
from src.market.advanced import add_advanced, team_context
from src.market.competitions import CompetitionSeason, competitions_of
from src.market.contract import TALENT_SCHEMA
from src.market.equivalence_publish import build_document
from src.market.formation_publish import build_document as build_formation
from src.market.profile import add_profiles
from src.market.season_rows import attach_bio, season_player_rows
from src.market.zones import ZONE_ORDER, competition_zones
from src.services.competition_category import category_facts, category_of_competition

INDEX = "index.json"
IDENTITIES = "identities"
EQUIVALENCES = "equivalences"
FORMATION = "formation"
SUBDIR = "players/"
SCOPE = "talent"
FORMAT = 1


def _norm(text: str) -> str:
    from src.scraper.schedule_client import normalize_name

    return normalize_name(text)


def _category(facts: Mapping[str, Any]) -> Dict[str, Any]:
    """``category``, ``age_group`` and ``competition_label`` (the name people read) when the catalogue says them (#914)."""
    return {**{k: facts[k] for k in ("category", "age_group") if facts.get(k)}, **({"competition_label": facts["label"]} if facts.get("label") else {})}


def _attributes(competition: CompetitionSeason, catalogue: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    """Gender and level from the catalogue: the entry of the competition (FEB) or of its category and territory (FBCYL). What the catalogue does not say is left out, never guessed."""
    if competition.league == "fbcyl":
        key = competition.key.split("|")[1]
        entry = next((e for e in catalogue if e.get("league") == "fbcyl" and f"{e['fbcyl']['category']}-{e['fbcyl'].get('territory', '0')}" == key), None)
        gender = ((entry or {}).get("fbcyl") or {}).get("gender")
        return {**({"gender": gender} if gender in ("F", "M") else {}), **_category(category_facts(entry) if entry else {})}
    from src.services.competition_catalogue import package_catalog

    chosen = next((c for c in package_catalog([dict(e, packages=e.get("packages", True)) for e in catalogue if e.get("league", "feb") == "feb"])
                   if _norm(c["competition"]) == _norm(competition.competition)), None) or {}
    out: Dict[str, Any] = {}
    if chosen.get("gender") in ("F", "M"):
        out["gender"] = chosen["gender"]
    if isinstance(chosen.get("level"), int):
        out["level"] = chosen["level"]
    return {**out, **_category(category_of_competition(competition.competition, catalogue))}


def _metas(connection: Any, names: Iterable[str]) -> Dict[str, Dict[str, Any]]:
    docs = connection.get_collection("COLLECTION_META").find({"_id": {"$in": list(names)}})
    return {d["_id"]: d for d in docs}


def competition_rows(connection: Any, members: Sequence[Any], roster_rows: Iterable[Mapping[str, Any]], season: str, external_bio: Optional[Mapping[str, Any]] = None,
                     links: Optional[Mapping[str, str]] = None) -> List[Dict[str, Any]]:
    """The rows of one competition and season: totals, bio, advanced figures in the context of each team, and rates, role and percentiles of the whole competition."""
    parts = []
    for member in members:
        parts.append((member.group, export_collection(connection.get_collection(member.collection), member.collection)))
    rows = season_player_rows(parts)
    rows = attach_bio(rows, roster_rows, season, external=external_bio, linked=links)
    rows = add_advanced(rows, team_context(r for _, payload in parts for r in payload["team_rows"]))
    return add_profiles(rows)


def _read_previous(out_dir: Path) -> Dict[str, Dict[str, Any]]:
    try:
        manifest = json.loads((out_dir / INDEX).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {e["key"]: e for e in manifest.get("competitions", [])} if manifest.get("schema") == TALENT_SCHEMA else {}


def _zones_file(out_dir: Path, sealer: Any, connection: Any, competition: CompetitionSeason, members: Sequence[Any], kept: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """The sealed shots-by-zone file of a competition and season (#994, ``zones.py``) apart from the rows, so the search never downloads it; ``None`` when no shot is known."""
    table = competition_zones(connection, [m.collection for m in members])
    if not any(table["league"]):
        return None
    plain = json.dumps({"format": FORMAT, "zones": list(ZONE_ORDER), **table}, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return seal_file(out_dir, f"{competition.key}|zones", plain, [SCOPE], sealer, kept, SUBDIR)


def _read_previous_identities(out_dir: Path) -> Optional[Dict[str, Any]]:
    try:
        manifest = json.loads((out_dir / INDEX).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return manifest.get("identities") if manifest.get("schema") == TALENT_SCHEMA else None


def _identities(out_dir: Path, sealer: Any, kept: Optional[Dict[str, Any]], rows_by_key: Mapping[str, List[Dict[str, Any]]]) -> Optional[Dict[str, Any]]:
    """The sealed ``identities`` file (#996): ``links`` (FBCYL id to FEB id) and ``by_feb`` (the competitions that hold rows of each FEB person), only for the links whose rows are published; ``None`` when there is none."""
    links: Dict[str, str] = {}
    by_feb: Dict[str, List[str]] = {}
    for key in sorted(rows_by_key):
        for row in rows_by_key[key]:
            if row.get("linked_to"):
                links[row["person_id"]] = row["linked_to"]
                if key not in by_feb.setdefault(row["linked_to"], []):
                    by_feb[row["linked_to"]].append(key)
    if not links:
        return None
    plain = json.dumps({"format": FORMAT, "links": links, "by_feb": by_feb}, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return seal_file(out_dir, IDENTITIES, plain, [SCOPE], sealer, kept, SUBDIR)


def _read_previous_entry(out_dir: Path, name: str) -> Optional[Dict[str, Any]]:
    try:
        manifest = json.loads((out_dir / INDEX).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return manifest.get(name) if manifest.get("schema") == TALENT_SCHEMA else None


def _modelled(out_dir: Path, sealer: Any, name: str, builder: Callable[..., Optional[Dict[str, Any]]], kept: Optional[Dict[str, Any]], rows_by_key: Mapping[str, List[Dict[str, Any]]],
              entries: Sequence[Mapping[str, Any]]) -> Optional[Dict[str, Any]]:
    """A sealed document fitted on the rows just published (``builder(rows, competitions)``) with its ``usable`` and ``sexes`` for the manifest; ``None`` when there is nothing to publish."""
    rows = [{**row, "comp": key} for key, group in rows_by_key.items() for row in group]
    document = builder(rows, {e["key"]: e for e in entries})
    if not document:
        return None
    plain = json.dumps(document, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return {**seal_file(out_dir, name, plain, [SCOPE], sealer, kept, SUBDIR), "usable": document["usable"], "sexes": sorted(document["sexes"])}


def _equivalences(out_dir: Path, sealer: Any, kept: Optional[Dict[str, Any]], rows_by_key: Mapping[str, List[Dict[str, Any]]], entries: Sequence[Mapping[str, Any]]) -> Optional[Dict[str, Any]]:
    """The sealed ``equivalences`` file (#891, E1c): the graph of levels between the senior competitions of FEB (``equivalence_publish``); ``None`` when no sex has a graph."""
    return _modelled(out_dir, sealer, EQUIVALENCES, build_document, kept, rows_by_key, entries)


def _formation(out_dir: Path, sealer: Any, kept: Optional[Dict[str, Any]], rows_by_key: Mapping[str, List[Dict[str, Any]]], entries: Sequence[Mapping[str, Any]]) -> Optional[Dict[str, Any]]:
    """The sealed ``formation`` file (#893, E3b): the index of the formation (``formation_publish``); ``None`` without formation, graph or players who made it to the senior game."""
    return _modelled(out_dir, sealer, FORMATION, build_formation, kept, rows_by_key, entries)


def _write_if_changed(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists() or path.read_bytes() != data:
        path.write_bytes(data)


def publish_talent_data(connection: Any, out_dir: Any, sealer: Any, names: Iterable[str], catalogue: Sequence[Mapping[str, Any]],
                        roster_rows: Iterable[Mapping[str, Any]] = (), external_bio: Optional[Mapping[str, Any]] = None, links: Optional[Mapping[str, str]] = None, on_competition: Optional[Callable[[CompetitionSeason, int, int], None]] = None,
                        on_unknown: Optional[Callable[[List[str]], None]] = None) -> Dict[str, Any]:
    """Write the sealed file of every competition and season of ``names`` and ``index.json`` (returned). Files that are no longer referenced are removed.

    ``roster_rows`` are the rows of ``roster_sweep`` (all seasons); ``external_bio`` the bio the linked external players lend to FEB persons (``external_bio``, #979); ``links`` the ``linked`` identity links ``{person id: FEB person id}`` of FBCYL (#996: the rows say ``linked_to``, inherit the FEB bio, and ``identities`` says who is who); ``on_competition(competition, players, files)`` reports progress; ``on_unknown`` gets the collections that say neither
    their competition nor their season (they are left out, never guessed)."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    roster = list(roster_rows)
    names = list(names)
    found, unknown = competitions_of(names, _metas(connection, names), catalogue)
    if unknown and on_unknown:
        on_unknown(unknown)
    kept = _read_previous(out_dir)
    kept_identities = _read_previous_identities(out_dir)
    kept_equivalences, kept_formation = _read_previous_entry(out_dir, "equivalences"), _read_previous_entry(out_dir, "formation")
    entries = []
    rows_by_key: Dict[str, List[Dict[str, Any]]] = {}
    for competition, members in found.items():
        rows = competition_rows(connection, members, roster, competition.season, external_bio, links)
        attributes = _attributes(competition, catalogue)
        head = {"key": competition.key, "league": competition.league, "competition": competition.competition, "season": competition.season, "season_label": competition.season_label,
                "groups": sorted({m.group for m in members}), **attributes}
        plain = json.dumps({"format": FORMAT, "competition": head, "rows": rows}, ensure_ascii=False, separators=(",", ":"), sort_keys=True, default=str)
        fields = seal_file(out_dir, competition.key, plain, [SCOPE], sealer, kept.get(competition.key), SUBDIR)
        zones = _zones_file(out_dir, sealer, connection, competition, members, (kept.get(competition.key) or {}).get("zones"))
        entries.append({**head, "players": len(rows), **fields, **({"zones": zones} if zones else {})})
        rows_by_key[competition.key] = rows
        if on_competition:
            on_competition(competition, len(rows), len(members))
    identities = _identities(out_dir, sealer, kept_identities, rows_by_key)
    equivalences = _equivalences(out_dir, sealer, kept_equivalences, rows_by_key, entries)
    formation = _formation(out_dir, sealer, kept_formation, rows_by_key, entries)
    manifest = {"schema": TALENT_SCHEMA, "kind": "talent", "v": sealer.index_version, **sealer.index_extra(), "competitions": entries, **({"identities": identities} if identities else {}),
                **({"equivalences": equivalences} if equivalences else {}), **({"formation": formation} if formation else {})}
    _write_if_changed(out_dir / "frontend" / "vercel.json", json.dumps(VERCEL_GUARD, indent=1).encode("utf-8"))      # Vercel builds every branch: this one is data, not a project (#906 regression)
    _write_if_changed(out_dir / INDEX, (json.dumps(manifest, ensure_ascii=False, separators=(",", ":"), default=str) + "\n").encode("utf-8"))
    referenced = {e["file"] for e in entries} | {e["zones"]["file"] for e in entries if e.get("zones")} | ({identities["file"]} if identities else set()) | ({equivalences["file"]} if equivalences else set()) | ({formation["file"]} if formation else set())
    for path in (out_dir / SUBDIR).glob("*.json"):
        if f"{SUBDIR}{path.name}" not in referenced:
            path.unlink()
    return manifest
