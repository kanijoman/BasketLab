"""The purge of a competition from the archive (issue #724): the one order that reduces the archive, and the only one that deletes data.

Pausing or removing an entry of the catalogue never deletes anything and the refresh refuses to shrink the archive, so a competition that is gone for good needs its own
deliberate order. ``purge`` works on the files of the archive directory (where the games live): it finds the collections of a competition and season by their name, shows what it
would delete (a dry run is what you get without the confirmation), asks for the competition and the season typed again, refuses a competition that is still ACTIVE in the
catalogue, and removes the files, the entries of ``archive.json`` and the collection metadata. The last versions of the archive stay reachable through the tags the push leaves.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from src.local_data.archive import META, META_FILE, MANIFEST, _meta_bytes, _read_meta, _write_if_changed


class NothingToPurge(ValueError):
    """No collection of the archive matches."""


class StillActive(ValueError):
    """The competition is active in the catalogue: pause it first (or the next refresh would bring it back)."""


def _prefix(competition: str, season: str, league: str) -> str:
    from src.database.utils import get_collection_name

    label = f"FBCYL_{competition}" if league == "fbcyl" else competition
    return get_collection_name(label, season, "")                    # ``COMPETITION_SEASON_``: the group (or phase) follows


def collections_of(names: Iterable[str], competition: str, season: str, league: str = "feb") -> List[str]:
    """The collections of a competition and season (every phase and group of it), by name; FBCYL groups are named ``FBCYL_<label>_<season>_``."""
    prefix = _prefix(competition, season, league)
    return [n for n in names if n.startswith(prefix)]


def confirmation_for(competition: str, season: str) -> str:
    """What has to be typed to purge: the competition and the season, as they were asked."""
    return f"{competition} {season}"


def refuse_if_active(catalogue: Any, competition: str, season: str, league: str) -> None:
    """``StillActive`` if the catalogue has an active entry of that competition and season (case, spaces and punctuation of the name ignored)."""
    from src.scraper.schedule_client import normalize_name
    from src.services.competition_catalogue import load_catalogue

    for entry in load_catalogue(catalogue):
        if entry["active"] and entry["league"] == league and normalize_name(entry["competition"]) == normalize_name(competition) \
                and season in (entry["season_label"], entry["season_value"]):
            raise StillActive(f"{competition} {season} is active in the catalogue: pause it (\"active\": false) and let the refresh run before purging, "
                              "or the next refresh would bring it back")


def purge_archive(archive_dir: Any, names: Iterable[str]) -> Dict[str, Any]:
    """Remove those collections from the archive directory: their files, their entries of ``archive.json`` and their metadata. ``NothingToPurge`` (nothing changes) if none is in it."""
    archive_dir = Path(archive_dir)
    manifest = json.loads((archive_dir / MANIFEST).read_text(encoding="utf-8"))
    wanted = set(names)
    gone = [c for c in manifest["collections"] if c["name"] in wanted]
    if not gone:
        raise NothingToPurge("no collection of the archive matches")
    for entry in gone:
        (archive_dir / entry["file"]).unlink(missing_ok=True)
    manifest["collections"] = [c for c in manifest["collections"] if c["name"] not in wanted]
    metadata = 0
    if manifest.get("meta"):
        docs = _read_meta(archive_dir, manifest["meta"])
        kept = [d for d in docs if str(d["_id"]) not in wanted]
        metadata = len(docs) - len(kept)
        if kept:
            import hashlib

            data = _meta_bytes(kept)
            _write_if_changed(archive_dir / META_FILE, data)
            manifest["meta"] = {"file": META_FILE, "docs": len(kept), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
        else:
            (archive_dir / META_FILE).unlink(missing_ok=True)
            manifest.pop("meta")
    _write_if_changed(archive_dir / MANIFEST, (json.dumps(manifest, ensure_ascii=False, indent=1) + "\n").encode("utf-8"))
    return {"collections": [c["name"] for c in gone], "games": sum(c["games"] for c in gone), "bytes": sum(c["bytes"] for c in gone), "metadata": metadata}


def purge(archive_dir: Any, competition: str, season: str, catalogue: Any, league: str = "feb", confirm: Optional[str] = None) -> Dict[str, Any]:
    """The purge order. Without ``confirm`` it only reports what it would delete (``purged: False``); with exactly ``confirmation_for`` it deletes. An active competition is
    refused either way; a wrong confirmation is a ``ValueError`` and changes nothing."""
    refuse_if_active(catalogue, competition, season, league)
    archive_dir = Path(archive_dir)
    manifest = json.loads((archive_dir / MANIFEST).read_text(encoding="utf-8"))
    names = collections_of([c["name"] for c in manifest["collections"]], competition, season, league)
    plan = {"competition": competition, "season": season, "league": league, "collections": names,
            "games": sum(c["games"] for c in manifest["collections"] if c["name"] in names),
            "bytes": sum(c["bytes"] for c in manifest["collections"] if c["name"] in names)}
    if not names:
        raise NothingToPurge(f"no collection of {competition} {season} in the archive")
    if confirm is None:
        return {**plan, "purged": False}
    if confirm != confirmation_for(competition, season):
        raise ValueError(f"the confirmation does not match: type exactly \"{confirmation_for(competition, season)}\" (--confirm) to purge")
    return {**plan, **purge_archive(archive_dir, names), "purged": True}
