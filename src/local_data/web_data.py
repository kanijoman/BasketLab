"""What the refresh publishes for the web (#328, #640): the ``web-data`` branch, read through a static host with no server.

``index.json`` is the manifest (the only file that keeps its name): ``schema`` of the contract, ``v`` and ``open_key`` of the sealing (same index as
the live packages), the ``rows`` of each competition (the contract of ``export``) and, per competition, the index of its ``reports`` (``team_reports``).
Everything but the manifest is sealed by scope and named after the hash of its content, so a file never changes in place: a client holding an older
manifest finds either the old file or a 404, never a mix. The previous publication in ``out_dir`` is the base of the next one: what did not change
keeps its bytes (sealing is random), what is no longer referenced is removed.
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional

from src.live_prep.package_sealing import Sealer
from src.local_data import build_cache
from src.local_data.build_cache import code_version
from src.live_prep.publisher import VERCEL_GUARD
from src.local_data.contract import SCHEMA
from src.local_data.export import export_collection, export_derived, file_name
from src.local_data.consistency_export import export_consistency
from src.local_data.images_export import Source, current_season_collections, seal_images
from src.local_data.inout_export import export_inout
from src.local_data.lineups_export import export_lineups
from src.local_data.matches_export import export_matches
from src.local_data.possessions_export import export_possession_csv, export_possessions
from src.local_data.assist_connections_export import export_assist_connections
from src.local_data.rival_adjusted_export import export_rival_adjusted
from src.local_data.rotations_export import export_rotations
from src.local_data.shots_export import export_shots
from src.local_data.team_reports import seal_file, seal_reports

INDEX = "index.json"
ROWS, REPORTS, SCOUTING, DERIVED, IMAGES = "rows/", "reports/", "scouting/", "derived/", "images/"
# The files of a competition besides its rows (#676, #684, #685): the manifest key and the folder of each (sealed for the competition, named after their hash)
SECTIONS = {"derived": DERIVED, "shots": "shots/", "rotations": "rotations/", "matches": "matches/",
            "possessions": "possessions/", "possession_csv": "possession_csv/", "lineups": "lineups/", "inout": "inout/", "consistency": "consistency/", "rival_adjusted": "rival_adjusted/",
            "assist_connections": "assist_connections/"}


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)


def _read(path: Path) -> Optional[Dict[str, Any]]:
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return manifest if manifest.get("schema") == SCHEMA else None


def _write_if_changed(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists() or path.read_bytes() != data:
        path.write_bytes(data)


def _previous_reports(out_dir: Path, manifest: Optional[Dict[str, Any]]) -> Dict[Any, Dict[str, Any]]:
    """The entries of the reports already published, by ``(collection, team_id, mode)``."""
    old: Dict[Any, Dict[str, Any]] = {}
    for entry in (manifest or {}).get("reports", []):
        try:
            index = json.loads((out_dir / entry["file"]).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for report in index.get("reports", []):
            old[(entry["collection"], report["team_id"], report["mode"], report.get("scope"))] = {**report, "collection": entry["collection"]}
    return old


def _publish_rows(db: Any, collection: str, out_dir: Path, sealer: Sealer, kept: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    payload = export_collection(db[collection], collection)
    fields = seal_file(out_dir, f"{collection}", _json(payload), [f"competicion:{collection}"], sealer, kept, ROWS)
    return {"collection": collection, "league": payload["league"], "games": payload["games"], **fields}


def _section_payload(section: str, handler: Any, db: Any, collection: str) -> Optional[Dict[str, Any]]:
    """What a competition has for ``section``, or ``None`` when it has nothing to publish: no game with ``DERIVED`` or with shots, or no play-by-play to analyse the rotations or the lineups."""
    if section == "derived":
        payload = export_derived(db[collection], collection)
        return payload if payload["rows"] else None
    if section == "shots":
        payload = export_shots(db[collection], collection)
        return payload if payload["shots"] else None
    if section == "possessions":
        payload = export_possessions(handler, collection)
        return payload if payload["table"] else None
    if section == "possession_csv":
        payload = export_possession_csv(handler, collection)
        return payload if payload["csv"] else None
    if section == "matches":
        payload = export_matches(handler, collection)
        return payload if payload["matches"] else None
    if section == "inout":
        payload = export_inout(handler, collection)
        return payload if payload["players"] else None
    if section == "consistency":
        payload = export_consistency(handler, collection)
        return payload if payload["players"] else None
    if section == "rival_adjusted":
        payload = export_rival_adjusted(handler, collection)
        return payload if payload["teams"] else None
    if section == "assist_connections":
        payload = export_assist_connections(handler, collection)
        return payload if payload["teams"] else None
    if section == "lineups":
        payload = export_lineups(handler, collection)
        return payload if payload["teams"] else None
    payload = export_rotations(handler, collection)
    return payload if any(t["analysis"].get("games_with_playbyplay") for t in payload["teams"]) else None


def _publish_section(section: str, handler: Any, db: Any, collection: str, out_dir: Path, sealer: Sealer, kept: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    payload = _section_payload(section, handler, db, collection)
    if payload is None:
        return None
    fields = seal_file(out_dir, f"{collection}", _json(payload), [f"competicion:{collection}"], sealer, kept, SECTIONS[section])
    return {"collection": collection, "league": payload["league"], "games": payload.get("games", len(payload.get("teams", payload.get("players", [])))), **fields}       # rotations: ``games`` counts the teams


def _publish_report_index(handler: Any, collection: str, out_dir: Path, sealer: Sealer, old: Dict[Any, Dict[str, Any]], scout: bool = False,
                          scouting_service: Optional[Callable[[Any], Any]] = None, images: Optional[Source] = None) -> Dict[str, Any]:
    """Seal the reports of a competition (and its scouting and the crest and photos of its teams, when asked) and write their index (plain: the wraps are not secret), named after its hash."""
    entries = seal_reports(handler, collection, out_dir, sealer, old, REPORTS)
    if images is not None:
        entries += seal_images(handler.connection.client["BASKETBALL"][collection], collection, out_dir, sealer, old, IMAGES, images)
    if scout:
        from src.local_data.scouting_export import seal_scouting

        entries += seal_scouting(handler, collection, out_dir, sealer, old, SCOUTING, scouting_service)
    reports = [{k: v for k, v in e.items() if k != "collection"} for e in entries]
    data = (_json({"collection": collection, "reports": reports}) + "\n").encode("utf-8")
    sha = hashlib.sha256(data).hexdigest()
    file = REPORTS + file_name(f"{collection}|index|{sha[:12]}")
    _write_if_changed(out_dir / file, data)
    return {"collection": collection, "teams": len({r["team_id"] for r in reports}), "file": file, "bytes": len(data), "sha256": sha}


def _publish_sections(name: str, rows_entry: Dict[str, Any], handler: Any, db: Any, out_dir: Path, sealer: Sealer, kept_sections: Dict[str, Dict[str, Any]],
                      remembered: Optional[Dict[str, Any]], on_section: Optional[Callable[[str, str, float, bool], None]]) -> Dict[str, Dict[str, Any]]:
    """The entries of the files of a competition besides its rows, by section, and what to remember of it (#700): the derived figures are always read (they are cheap and part of
    the fingerprint); when the fingerprint of the rows and the derived is the one of the previous publication, the heavy sections reuse their sealed files and compute nothing."""
    entries: Dict[str, Dict[str, Any]] = {}
    started = time.time()
    derived = _publish_section("derived", handler, db, name, out_dir, sealer, kept_sections["derived"].get(name))
    if derived:
        entries["derived"] = derived
    if on_section:
        on_section(name, "derived", time.time() - started, False)
    fp = build_cache.fingerprint(rows_entry["sha256"], derived["sha256"] if derived else None)
    had = [s for s in (remembered or {}).get("sections", []) if s in SECTIONS and s != "derived"]
    reuse = bool(remembered) and remembered.get("fingerprint") == fp and all(
        kept_sections[s].get(name) and (out_dir / kept_sections[s][name]["file"]).is_file() for s in had)
    for section in SECTIONS:
        if section == "derived":
            continue
        started = time.time()
        if reuse:
            entry = kept_sections[section].get(name) if section in had else None
        else:
            entry = _publish_section(section, handler, db, name, out_dir, sealer, kept_sections[section].get(name))
        if entry:
            entries[section] = entry
        if on_section:
            on_section(name, section, time.time() - started, reuse)
    entries["_memory"] = {"fingerprint": fp, "sections": [s for s in SECTIONS if s in entries]}
    return entries


def _referenced(out_dir: Path, manifest: Dict[str, Any]) -> set:
    files = {INDEX, "frontend/vercel.json"}
    for entry in manifest["rows"] + [e for section in SECTIONS for e in manifest.get(section, [])]:
        files.add(entry["file"])
    for entry in manifest["reports"]:
        files.add(entry["file"])
        files.update(r["file"] for r in json.loads((out_dir / entry["file"]).read_text(encoding="utf-8"))["reports"])
    return files


def publish_web_data(handler: Any, out_dir: Path, sealer: Sealer, collections: Iterable[str], keep_others: bool = False,
                     on_collection: Optional[Callable[[str], None]] = None, scouting: Optional[Iterable[str]] = None,
                     scouting_service: Optional[Callable[[Any], Any]] = None, on_section: Optional[Callable[[str, str, float, bool], None]] = None,
                     image_source: Optional[Source] = None) -> Dict[str, Any]:
    """Write the artifacts of ``collections`` and the manifest (returned). With ``keep_others`` the competitions of the previous publication that are
    not in ``collections`` stay as they were (a partial refresh); otherwise the directory mirrors ``collections``. ``scouting`` lists the
    collections whose teams also get their full scouting by scope (``scouting_export``; ``scouting_service`` builds the service, for tests). A competition that has not
    changed since the previous publication (``build_cache``) reuses its sealed files; ``image_source`` (the FEB, or a fake) makes the competitions of the newest season publish the crest and the photos of their teams (#717); ``on_section(competition, section, seconds, reused)`` says what each one cost (#700)."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    db = handler.connection.client["BASKETBALL"]
    names, scouted = list(collections), set(scouting or [])
    previous = _read(out_dir / INDEX)
    old_reports = _previous_reports(out_dir, previous)
    rows = {e["collection"]: e for e in (previous or {}).get("rows", []) if keep_others and e["collection"] not in names}
    reports = {e["collection"]: e for e in (previous or {}).get("reports", []) if keep_others and e["collection"] not in names}
    kept_rows = {e["collection"]: e for e in (previous or {}).get("rows", [])}
    sections = {s: {e["collection"]: e for e in (previous or {}).get(s, []) if keep_others and e["collection"] not in names} for s in SECTIONS}
    kept_sections = {s: {e["collection"]: e for e in (previous or {}).get(s, [])} for s in SECTIONS}
    imaged = current_season_collections(names) if image_source is not None else set()
    memory, code = build_cache.load(out_dir), code_version()
    remembered = {k: v for k, v in memory["competitions"].items() if keep_others and k not in names}
    for name in names:
        rows[name] = _publish_rows(db, name, out_dir, sealer, kept_rows.get(name))
        entries = _publish_sections(name, rows[name], handler, db, out_dir, sealer, kept_sections,
                                    memory["competitions"].get(name) if memory["code"] == code else None, on_section)
        remembered[name] = entries.pop("_memory")
        for section, entry in entries.items():
            sections[section][name] = entry
        reports[name] = _publish_report_index(handler, name, out_dir, sealer, old_reports, name in scouted, scouting_service, image_source if name in imaged else None)
        if on_collection:
            on_collection(name)
    manifest = {"schema": SCHEMA, "v": sealer.index_version, **sealer.index_extra(),
                "rows": [rows[n] for n in sorted(rows)], **{s: [sections[s][n] for n in sorted(sections[s])] for s in SECTIONS},
                "reports": [reports[n] for n in sorted(reports)]}
    _write_if_changed(out_dir / "frontend" / "vercel.json", json.dumps(VERCEL_GUARD, indent=1).encode("utf-8"))
    _write_if_changed(out_dir / INDEX, (_json(manifest) + "\n").encode("utf-8"))
    _write_if_changed(out_dir / build_cache.CACHE, build_cache.save(out_dir, code, remembered))
    keep = _referenced(out_dir, manifest)
    for folder in (ROWS, *SECTIONS.values(), REPORTS, SCOUTING, IMAGES):
        for stale in (out_dir / folder).glob("*.json"):
            if f"{folder}{stale.name}" not in keep:
                stale.unlink()
    return manifest
