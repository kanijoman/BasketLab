"""The publication of the external sources, ``web-data-ext`` (#884): the same pipeline as ``web-data`` over ACB, FIBA and NCAA, in a publication of its own.

It restores the archive of each source into the database of the run, leaves out the games that do not reconcile with their official box (they stay in the archive flagged ``_reliable: false`` but never enter rates,
percentiles or the published rows; the database of the run is ephemeral, the archive is not touched) and publishes only the external competitions of the catalogue with ``publish_web_data``. The manifest carries
the ``league`` of each competition (its source) and the freshness of each source (``sources``): a failed run still publishes the rows of the last good one and says so.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from src.external.refresh import STATUS
from src.local_data.archive import MANIFEST, load_archive
from src.local_data.web_data import publish_web_data
from src.services.competition_catalogue import external_collections
from src.utils.collection_utils import EXTERNAL_SOURCES


def _status(folder: Path) -> Dict[str, Any]:
    path = folder / STATUS
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


def _facts(entry: Dict[str, Any]) -> Dict[str, Any]:
    """What the selector reads of an external competition: its category and age group (a youth championship of FIBA is ``formacion`` with its ``U16`` or ``U18``, as in the catalogue), the name people read and,
    for NCAA, its conference as the group."""
    from src.services.competition_category import category_facts

    facts = category_facts(entry)
    facts.setdefault("label", f"{entry['league'].upper()} {entry['competition']}")
    return {**facts, **({"group_label": entry["conference"]} if entry.get("conference") else {})}


def publish_external(archive_dir: Path, out_dir: Path, catalogue: List[Dict[str, Any]], handler: Any, sealer: Any) -> Dict[str, Any]:
    """Publish the external competitions of ``catalogue`` that are in the archive; returns the manifest. With no archive the manifest is valid and empty."""
    archive_dir, db = Path(archive_dir), handler.connection.client["BASKETBALL"]
    wanted = external_collections(catalogue)
    freshness: List[Dict[str, Any]] = []
    published: Dict[str, int] = {}
    for source in EXTERNAL_SOURCES:
        folder = archive_dir / source
        if not (folder / MANIFEST).is_file():
            continue
        load_archive(folder, db)
        status = _status(folder)
        count = 0
        for name, entry in wanted.items():
            if entry["league"] != source:
                continue
            db[name].delete_many({"_reliable": {"$ne": True}})          # kept in the archive, flagged; out of everything that is published
            count += db[name].count_documents({})
        published[source] = count
        freshness.append({"source": source, "state": status.get("state", "ok"), "ok": status.get("ok") is not False, **({"last_ok": status["last_ok"]} if status.get("last_ok") else {}),
                          **({"finished": status["finished"]} if status.get("finished") else {}), "games": int(status.get("games", count)), "unreliable": int(status.get("unreliable", 0)), "published": count})
    names = [name for name, entry in wanted.items() if published.get(entry["league"]) and db[name].count_documents({}) > 0]
    return publish_web_data(handler, out_dir, sealer, names, genders={n: wanted[n]["gender"] for n in names}, categories={n: _facts(wanted[n]) for n in names}, sources=freshness)
