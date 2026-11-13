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
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional

from src.live_prep.package_sealing import Sealer
from src.local_data import build_cache
from src.local_data.calendar_export import CalendarSource, calendar_collections, export_calendar
from src.local_data.build_cache import section_versions
from src.live_prep.publisher import VERCEL_GUARD
from src.local_data.contract import SCHEMA
from src.local_data.export import export_collection, file_name
from src.local_data.images_export import Source, current_season_collections, seal_images
from src.local_data.sections import section_payload
from src.local_data.team_reports import seal_file, seal_reports

log = logging.getLogger(__name__)
INDEX = "index.json"
ROWS, REPORTS, SCOUTING, DERIVED, IMAGES = "rows/", "reports/", "scouting/", "derived/", "images/"
# The files of a competition besides its rows (#676, #684, #685): the manifest key and the folder of each (sealed for the competition, named after their hash)
SECTIONS = {"derived": DERIVED, "shots": "shots/", "rotations": "rotations/", "matches": "matches/",
            "possessions": "possessions/", "possession_csv": "possession_csv/", "lineups": "lineups/", "inout": "inout/", "consistency": "consistency/", "rival_adjusted": "rival_adjusted/",
            "assist_connections": "assist_connections/", "calendar": "calendar/"}
# What is not part of the build cache: the derived figures are its fingerprint, and the calendar (#842) changes without a new game, so it is read on every publication
UNCACHED = {"derived", "calendar"}
CACHED = [s for s in SECTIONS if s not in UNCACHED]
HANDLER = "src.database"   # the exporters are handed the database handler and call its methods without importing it: its code is a dependency of every section that uses it
# The module that computes each section (#783): the version of the code of a section is the hash of what that module imports, so the cache recomputes only the sections whose code changed.
# A new section must be declared here (``test_build_cache_sections`` fails otherwise): without it nothing would notice a change in its exporter. ``derived`` is not cached (it is the fingerprint).
# What a version does NOT see: the rules of ``sections.section_payload`` (when a section has nothing to publish) and how files are sealed (``team_reports.seal_file``): changing them needs ``build_cache.EPOCH`` raised.
SECTION_MODULES = {
    "shots": "src.local_data.shots_export",                                                     # reads the games' collection directly: its imports are all it depends on
    "rotations": ["src.local_data.rotations_export", HANDLER], "matches": ["src.local_data.matches_export", HANDLER],
    "possessions": ["src.local_data.possessions_export", HANDLER], "possession_csv": ["src.local_data.possessions_export", HANDLER],
    "lineups": ["src.local_data.lineups_export", HANDLER], "inout": ["src.local_data.inout_export", HANDLER],
    "consistency": ["src.local_data.consistency_export", HANDLER], "rival_adjusted": ["src.local_data.rival_adjusted_export", HANDLER],
    "assist_connections": ["src.local_data.assist_connections_export", HANDLER],
}


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


def _category_fields(category: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """``category``, ``age_group`` and ``competition_label`` of a competition (#914), when the catalogue says them: the selector of the browser groups and names the competitions with them."""
    said = category or {}
    return {**{k: said[k] for k in ("category", "age_group") if said.get(k)}, **({"competition_label": said["label"]} if said.get("label") else {})}


def _publish_rows(db: Any, collection: str, out_dir: Path, sealer: Sealer, kept: Optional[Dict[str, Any]], gender: Optional[str] = None,
                  category: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    payload = export_collection(db[collection], collection)
    fields = seal_file(out_dir, f"{collection}", _json(payload), [f"competicion:{collection}"], sealer, kept, ROWS)
    return {"collection": collection, "league": payload["league"], "games": payload["games"], **({"gender": gender} if gender else {}), **_category_fields(category), **fields}      # ``gender`` (#843): the family of the win probability


def _publish_section(section: str, handler: Any, db: Any, collection: str, out_dir: Path, sealer: Sealer, kept: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    return _seal_section(section, section_payload(section, handler, db, collection), collection, out_dir, sealer, kept)


def _seal_section(section: str, payload: Optional[Dict[str, Any]], collection: str, out_dir: Path, sealer: Sealer, kept: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
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


def _can_reuse(section: str, same_data: bool, versions: Dict[str, str], old_versions: Dict[str, str], had: List[str],
               kept_entry: Optional[Dict[str, Any]], out_dir: Path) -> bool:
    """A section reuses its sealed file when the data and the code of the section are those of the previous publication and, if the section had a file, that file is still there."""
    if not (same_data and section in versions and old_versions.get(section) == versions[section]):
        return False
    return section not in had or bool(kept_entry and (out_dir / kept_entry["file"]).is_file())


def _publish_sections(name: str, rows_entry: Dict[str, Any], handler: Any, db: Any, out_dir: Path, sealer: Sealer, kept_sections: Dict[str, Dict[str, Any]],
                      remembered: Optional[Dict[str, Any]], on_section: Optional[Callable[[str, str, float, bool], None]],
                      versions: Optional[Dict[str, str]] = None) -> Dict[str, Dict[str, Any]]:
    """The entries of the files of a competition besides its rows, by section, and what to remember of it (#700, #783): the derived figures are always read (they are cheap and part of
    the fingerprint); a section reuses its sealed file and computes nothing when the fingerprint of the rows and the derived is the one of the previous publication AND the version of
    the code of that section (the hash of the modules its exporter imports) is too; a section whose code changed, or that the memory never saw, is the only one computed."""
    versions = versions or {}
    entries: Dict[str, Dict[str, Any]] = {}
    started = time.time()
    derived = _publish_section("derived", handler, db, name, out_dir, sealer, kept_sections["derived"].get(name))
    if derived:
        entries["derived"] = derived
    if on_section:
        on_section(name, "derived", time.time() - started, False)
    fp = build_cache.fingerprint(rows_entry["sha256"], derived["sha256"] if derived else None)
    had = [s for s in (remembered or {}).get("sections", []) if s in CACHED]
    same_data = bool(remembered) and remembered.get("fingerprint") == fp
    old_versions = (remembered or {}).get("versions") or {}
    for section in CACHED:
        started = time.time()
        kept_entry = kept_sections[section].get(name)
        reuse = _can_reuse(section, same_data, versions, old_versions, had, kept_entry, out_dir)
        if reuse:
            entry = kept_entry if section in had else None
        else:
            entry = _publish_section(section, handler, db, name, out_dir, sealer, kept_entry)
        if entry:
            entries[section] = entry
        if on_section:
            on_section(name, section, time.time() - started, reuse)
    entries["_memory"] = {"fingerprint": fp, "sections": [s for s in SECTIONS if s in entries], "versions": {s: versions[s] for s in SECTIONS if s in versions}}
    return entries


def _referenced(out_dir: Path, manifest: Dict[str, Any]) -> set:
    files = {INDEX, "frontend/vercel.json"}
    for entry in manifest["rows"] + [e for section in SECTIONS for e in manifest.get(section, [])]:
        files.add(entry["file"])
    for entry in manifest["reports"]:
        files.add(entry["file"])
        files.update(r["file"] for r in json.loads((out_dir / entry["file"]).read_text(encoding="utf-8"))["reports"])
    return files


@dataclass
class _Context:
    """What the competitions of ONE publication share: where it writes, what the previous publication left and the memory of the cache (#700, #783)."""
    handler: Any
    db: Any
    out_dir: Path
    sealer: Sealer
    kept_rows: Dict[str, Dict[str, Any]]
    kept_sections: Dict[str, Dict[str, Any]]
    old_reports: Dict[Any, Dict[str, Any]]
    memory: Dict[str, Any]
    trusted: bool
    versions: Dict[str, str]
    on_section: Optional[Callable[[str, str, float, bool], None]]
    scouted: set
    scouting_service: Optional[Callable[[Any], Any]]
    image_source: Optional[Source]
    imaged: set
    calendar_source: Optional[CalendarSource]
    calendar_names: set
    groups: Dict[str, str]
    genders: Dict[str, str]
    categories: Dict[str, Dict[str, Any]]


def _publish_calendar(ctx: _Context, name: str) -> Optional[Dict[str, Any]]:
    """The sealed calendar of a competition of the newest season (#842), read now; one that cannot be read keeps the previous entry (its file is still there) and, with none, publishes nothing."""
    if ctx.calendar_source is None or name not in ctx.calendar_names:
        return None
    started = time.time()
    kept = ctx.kept_sections["calendar"].get(name)
    entry = _seal_section("calendar", export_calendar(ctx.calendar_source, ctx.handler, name, ctx.groups.get(name)), name, ctx.out_dir, ctx.sealer, kept)
    if entry is None and kept and (ctx.out_dir / kept["file"]).is_file():
        log.warning("%s: calendar unavailable, the previous one is kept", name)
        entry = kept
    if ctx.on_section:
        ctx.on_section(name, "calendar", time.time() - started, False)
    return entry


def _carried_over(previous: Optional[Dict[str, Any]], names: List[str], keep_others: bool):
    """What a partial refresh keeps of the previous publication: the rows, the reports and the sections of the competitions that are NOT being published now (nothing without ``keep_others``)."""
    def kept(entries: Iterable[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        return {e["collection"]: e for e in entries if keep_others and e["collection"] not in names}

    before = previous or {}
    return kept(before.get("rows", [])), kept(before.get("reports", [])), {s: kept(before.get(s, [])) for s in SECTIONS}


def _publish_competition(ctx: _Context, name: str):
    """One competition: its rows, its sections and its report index, in that order (what each cost goes to ``on_section``). Returns the entry of the rows, those of the sections (with ``_memory``) and the report index."""
    started = time.time()
    rows_entry = _publish_rows(ctx.db, name, ctx.out_dir, ctx.sealer, ctx.kept_rows.get(name), ctx.genders.get(name), ctx.categories.get(name))
    if ctx.on_section:
        ctx.on_section(name, "rows", time.time() - started, False)
    entries = _publish_sections(name, rows_entry, ctx.handler, ctx.db, ctx.out_dir, ctx.sealer, ctx.kept_sections,
                                ctx.memory["competitions"].get(name) if ctx.trusted else None, ctx.on_section, ctx.versions)
    calendar = _publish_calendar(ctx, name)
    if calendar:
        entries["calendar"] = calendar
    started = time.time()
    report_index = _publish_report_index(ctx.handler, name, ctx.out_dir, ctx.sealer, ctx.old_reports, name in ctx.scouted, ctx.scouting_service,
                                         ctx.image_source if name in ctx.imaged else None)
    if ctx.on_section:
        ctx.on_section(name, "reports", time.time() - started, False)
    return rows_entry, entries, report_index


def _sweep_stale(out_dir: Path, manifest: Dict[str, Any]) -> None:
    """Remove the sealed files that the manifest no longer references."""
    keep = _referenced(out_dir, manifest)
    for folder in (ROWS, *SECTIONS.values(), REPORTS, SCOUTING, IMAGES):
        for stale in (out_dir / folder).glob("*.json"):
            if f"{folder}{stale.name}" not in keep:
                stale.unlink()


def publish_web_data(handler: Any, out_dir: Path, sealer: Sealer, collections: Iterable[str], keep_others: bool = False,
                     on_collection: Optional[Callable[[str], None]] = None, scouting: Optional[Iterable[str]] = None,
                     scouting_service: Optional[Callable[[Any], Any]] = None, on_section: Optional[Callable[[str, str, float, bool], None]] = None,
                     image_source: Optional[Source] = None, calendar_source: Optional[CalendarSource] = None,
                     fbcyl_groups: Optional[Dict[str, str]] = None, genders: Optional[Dict[str, str]] = None, categories: Optional[Dict[str, Dict[str, Any]]] = None) -> Dict[str, Any]:
    """Write the artifacts of ``collections`` and the manifest (returned). With ``keep_others`` the competitions of the previous publication that are
    not in ``collections`` stay as they were (a partial refresh); otherwise the directory mirrors ``collections``. ``scouting`` lists the
    collections whose teams also get their full scouting by scope (``scouting_export``; ``scouting_service`` builds the service, for tests). A competition that has not
    changed since the previous publication (``build_cache``) reuses its sealed files; ``image_source`` (the FEB, or a fake) makes the competitions of the newest season publish the crest and the photos of their teams (#717); ``on_section(competition, section, seconds, reused)`` says what each one cost (#700); ``calendar_source`` (the federations, or a fake) makes the competitions of the newest season publish their calendar (#842; ``fbcyl_groups`` maps a FBCYL competition to its ESB group), always read again; ``genders`` (``competition_gender.competition_genders``) puts the ``F``/``M`` of each competition in its rows entry (#843)."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    names = list(collections)
    previous = _read(out_dir / INDEX)
    rows, reports, sections = _carried_over(previous, names, keep_others)
    memory = build_cache.load(out_dir)
    trusted = memory["epoch"] == build_cache.EPOCH                       # another epoch, or the old format with one version for all the code: compute everything once
    ctx = _Context(handler=handler, db=handler.connection.client["BASKETBALL"], out_dir=out_dir, sealer=sealer,
                   kept_rows={e["collection"]: e for e in (previous or {}).get("rows", [])},
                   kept_sections={s: {e["collection"]: e for e in (previous or {}).get(s, [])} for s in SECTIONS},
                   old_reports=_previous_reports(out_dir, previous), memory=memory, trusted=trusted, versions=section_versions(SECTION_MODULES),
                   on_section=on_section, scouted=set(scouting or []), scouting_service=scouting_service, image_source=image_source,
                   imaged=current_season_collections(names) if image_source is not None else set(),
                   calendar_source=calendar_source, calendar_names=calendar_collections(names, fbcyl_groups or {}) if calendar_source is not None else set(), groups=fbcyl_groups or {}, genders=genders or {}, categories=categories or {})
    remembered = {k: v for k, v in memory["competitions"].items() if trusted and keep_others and k not in names}
    for name in names:
        rows[name], entries, reports[name] = _publish_competition(ctx, name)
        remembered[name] = entries.pop("_memory")
        for section, entry in entries.items():
            sections[section][name] = entry
        if on_collection:
            on_collection(name)
    manifest = {"schema": SCHEMA, "v": sealer.index_version, **sealer.index_extra(),
                "rows": [rows[n] for n in sorted(rows)], **{s: [sections[s][n] for n in sorted(sections[s])] for s in SECTIONS},
                "reports": [reports[n] for n in sorted(reports)]}
    _write_if_changed(out_dir / "frontend" / "vercel.json", json.dumps(VERCEL_GUARD, indent=1).encode("utf-8"))
    _write_if_changed(out_dir / INDEX, (_json(manifest) + "\n").encode("utf-8"))
    _write_if_changed(out_dir / build_cache.CACHE, build_cache.save(out_dir, remembered))
    _sweep_stale(out_dir, manifest)
    return manifest
