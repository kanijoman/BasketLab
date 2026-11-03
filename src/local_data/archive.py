"""The private archive of the games (#646): the raw match documents, one compressed file per competition, outside Atlas.

Every refresh restores the archive into a Mongo that lives as long as the job (the pipelines do not change), scrapes what is new, and writes the
archive back. A file is one game per line (extended JSON: every Mongo type round-trips), games sorted by ``_id`` and gzip without a timestamp, so
an unchanged competition is byte-identical and a refresh without news commits nothing. ``archive.json`` lists the files with their sha256, which
``load_archive`` checks before it touches the database. Seasons older than the previous one are kept *light* (no play-by-play: box score, shots
and ``DERIVED`` stay, about a third of the size).
"""
from __future__ import annotations

import gzip
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Iterator, List, Optional
from urllib.parse import quote

from bson import json_util

FORMAT = 1
MANIFEST = "archive.json"
SUFFIX = ".jsonl.gz"
PLAY_BY_PLAY = ("PLAYBYPLAY", "moves")                  # FEB and FBCYL: what a light game leaves out
META = "COLLECTION_META"                                # the metadata the FEB scrape writes per collection (#724): it travels in the archive, in a file of its own
META_FILE = META + SUFFIX
META_VOLATILE = ("saved_at",)                           # the time of the last scrape: it changes on every refresh and would commit the archive each time
BATCH = 500
_SEASON = re.compile(r"(20\d\d)_(20\d\d)")
_OPTIONS = json_util.CANONICAL_JSON_OPTIONS


def _season(name: str) -> Optional[int]:
    found = _SEASON.search(name)
    return int(found.group(1)) if found else None


def working_set(names: Iterable[str]) -> Callable[[str], bool]:
    """Whether a collection belongs to the working set: the latest season and the one before it, complete; a name without a season always does."""
    seasons = sorted({s for s in map(_season, names) if s is not None})
    keep = set(seasons[-2:])
    return lambda name: _season(name) is None or _season(name) in keep


def _file(name: str) -> str:
    return quote(name, safe="").replace("%", "~") + SUFFIX


def _games_collections(db: Any) -> List[str]:
    from src.services.derived_backfill import fbcyl_collection_names, feb_collection_names

    return sorted(set(feb_collection_names(db)) | set(fbcyl_collection_names(db)))


def _lines(collection: Any, light: bool) -> Iterator[bytes]:
    for doc in sorted(collection.find({}), key=lambda d: (type(d["_id"]).__name__, str(d["_id"]))):
        if light:
            doc = {k: v for k, v in doc.items() if k not in PLAY_BY_PLAY}
        yield json_util.dumps(doc, json_options=_OPTIONS, separators=(",", ":")).encode("utf-8") + b"\n"


def _meta_docs(db: Any) -> List[Dict[str, Any]]:
    if META not in db.list_collection_names():
        return []
    return [{k: v for k, v in doc.items() if k not in META_VOLATILE} for doc in db[META].find({})]


def _meta_bytes(docs: Iterable[Dict[str, Any]]) -> bytes:
    lines = (json_util.dumps(doc, json_options=_OPTIONS, separators=(",", ":")).encode("utf-8") + b"\n" for doc in sorted(docs, key=lambda d: str(d["_id"])))
    return gzip.compress(b"".join(lines), compresslevel=9, mtime=0)


def _read_meta(src_dir: Path, entry: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not entry:
        return []
    return [json_util.loads(line, json_options=_OPTIONS) for line in gzip.decompress((src_dir / entry["file"]).read_bytes()).splitlines()]


def _write_if_changed(path: Path, data: bytes) -> None:
    if not path.exists() or path.read_bytes() != data:
        path.write_bytes(data)


def _refuse_shrinking(db: Any, out_dir: Path, names: List[str], whole: bool) -> None:
    """Raise before writing anything if the archive already in ``out_dir`` has a collection that ``db`` no longer has (``whole`` only) or holds with fewer games."""
    if not (out_dir / MANIFEST).is_file():
        return
    stored = json.loads((out_dir / MANIFEST).read_text(encoding="utf-8"))
    if whole and (stored.get("meta") or {}).get("docs", 0) > len(_meta_docs(db)):
        raise ValueError(f"the database has fewer collection metadata ({len(_meta_docs(db))}) than the archive ({stored['meta']['docs']}): not overwriting it")
    for entry in stored["collections"]:
        name = entry["name"]
        if name in names:
            now = db[name].count_documents({})
            if now < entry["games"]:
                raise ValueError(f"{name} has fewer games ({now}) than the archive ({entry['games']}): not overwriting it")
        elif whole and entry["games"] > 0:               # a collection without games that is gone loses nothing
            raise ValueError(f"{name} is in the archive and no longer in the database (fewer games): not overwriting it")


def _dump_meta(db: Any, out_dir: Path, only: Optional[Iterable[str]]) -> Optional[Dict[str, Any]]:
    """The metadata file and its manifest entry: all of the database's, or with ``only`` the archive's own plus the database's of those collections."""
    docs = {str(d["_id"]): d for d in _meta_docs(db)}
    if only is not None:
        kept = {}
        if (out_dir / MANIFEST).is_file():
            previous = json.loads((out_dir / MANIFEST).read_text(encoding="utf-8")).get("meta")
            kept = {str(d["_id"]): d for d in _read_meta(out_dir, previous)}
        kept.update({k: v for k, v in docs.items() if k in set(only)})
        docs = kept
    if not docs:
        return None
    data = _meta_bytes(docs.values())
    _write_if_changed(out_dir / META_FILE, data)
    return {"file": META_FILE, "docs": len(docs), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def dump_archive(db: Any, out_dir: Path, light: Optional[Callable[[str], bool]] = None, only: Optional[Iterable[str]] = None,
                 allow_shrink: bool = True) -> Dict[str, Any]:
    """Write the file of every games collection and ``archive.json`` (returned); ``light(name)`` says which are kept without play-by-play
    (default: the ones outside the working set). With ``only`` the other files and entries are kept. Files of collections gone are removed.
    ``allow_shrink=False`` (what a refresh uses) refuses, before touching anything, to replace the archive with fewer games."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    names = _games_collections(db)
    if not allow_shrink:
        _refuse_shrinking(db, out_dir, [n for n in names if only is None or n in set(only)], whole=only is None)
    if light is None:
        in_set = working_set(names)
        light = lambda name: not in_set(name)  # noqa: E731
    entries: Dict[str, Dict[str, Any]] = {}
    if only is not None and (out_dir / MANIFEST).is_file():
        entries = {c["name"]: c for c in json.loads((out_dir / MANIFEST).read_text(encoding="utf-8"))["collections"]}
    for name in (names if only is None else [n for n in names if n in set(only)]):
        is_light = bool(light(name))
        data = gzip.compress(b"".join(_lines(db[name], is_light)), compresslevel=9, mtime=0)
        _write_if_changed(out_dir / _file(name), data)
        entries[name] = {"name": name, "file": _file(name), "light": is_light, "games": db[name].count_documents({}),
                         "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
    if only is None:
        entries = {n: e for n, e in entries.items() if n in set(names)}
    manifest = {"format": FORMAT, "collections": [entries[n] for n in sorted(entries)]}
    meta = _dump_meta(db, out_dir, only)
    if meta:
        manifest["meta"] = meta
    for stale in out_dir.glob("*" + SUFFIX):
        if stale.name not in {e["file"] for e in entries.values()} | {META_FILE}:
            stale.unlink()
    if not meta and (out_dir / META_FILE).exists():
        (out_dir / META_FILE).unlink()
    _write_if_changed(out_dir / MANIFEST, (json.dumps(manifest, ensure_ascii=False, indent=1) + "\n").encode("utf-8"))
    return manifest


def ensure_team_indexes(db: Any) -> int:
    """The index of the games of a team (``HEADER.TEAM.id``) on every FEB collection, as the refresh creates it on Atlas (issue #502); how many collections got it.

    An index is not part of the archive, so the Mongo restored from it starts without; the jobs that read the games of a team across the collections of a season (the live
    packages, the rule evaluation) call this right after the restore. Same name and key as ``IndexManager.ensure_team_index``: creating it twice is harmless. FBCYL has no
    ``HEADER.TEAM``."""
    import pymongo

    from src.services.derived_backfill import feb_collection_names

    names = feb_collection_names(db)
    for name in names:
        db[name].create_index([("HEADER.TEAM.id", pymongo.ASCENDING)], name="team_id_1", background=True)
    return len(names)


def load_archive(src_dir: Path, db: Any, only: Optional[Iterable[str]] = None) -> Dict[str, int]:
    """Replace the collections of ``db`` with the ones of the archive; ``{collection: games}``. Every file is checked against its sha256 first:
    a corrupt archive is refused with nothing loaded. The collection metadata (``COLLECTION_META``, #724) is restored by id, not replaced."""
    src_dir = Path(src_dir)
    manifest = json.loads((src_dir / MANIFEST).read_text(encoding="utf-8"))
    wanted = set(only) if only is not None else None
    entries = [e for e in manifest["collections"] if wanted is None or e["name"] in wanted]
    blobs = {}
    for entry in entries:
        blobs[entry["name"]] = data = (src_dir / entry["file"]).read_bytes()
        if hashlib.sha256(data).hexdigest() != entry["sha256"]:
            raise ValueError(f"{entry['file']}: sha256 does not match the manifest (corrupt or tampered archive)")
    meta_entry = manifest.get("meta")
    if meta_entry:
        blobs[META] = data = (src_dir / meta_entry["file"]).read_bytes()
        if hashlib.sha256(data).hexdigest() != meta_entry["sha256"]:
            raise ValueError(f"{meta_entry['file']}: sha256 does not match the manifest (corrupt or tampered archive)")
    loaded: Dict[str, int] = {}
    for entry in entries:
        name = entry["name"]
        db.drop_collection(name)
        collection, batch, count = db[name], [], 0
        for line in gzip.decompress(blobs[name]).splitlines():
            batch.append(json_util.loads(line, json_options=_OPTIONS))
            if len(batch) >= BATCH:
                collection.insert_many(batch, ordered=False)
                count, batch = count + len(batch), []
        if batch:
            collection.insert_many(batch, ordered=False)
            count += len(batch)
        if count == 0:
            db.create_collection(name)                  # Mongo creates a collection with its first document: an empty one would be missing otherwise
        loaded[name] = count
    if meta_entry:
        for doc in _read_meta(src_dir, meta_entry):
            if wanted is None or str(doc["_id"]) in wanted:
                db[META].replace_one({"_id": doc["_id"]}, doc, upsert=True)       # by id and without dropping: a scrape may have written some already
    return loaded
