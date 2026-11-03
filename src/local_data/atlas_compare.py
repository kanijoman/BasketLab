"""Archive against Atlas (issue #724, step 1): is everything Atlas holds in the archive, so that Atlas can be switched off?

Games are compared by ``_id`` (the archive restores them with the ids they have) and by whether they carry the current ``DERIVED``. Atlas is only
READ, and the connection is wrapped so that it cannot be anything else: ``ReadOnly`` lets through the listing of names and projected ``find`` /
``count_documents`` and raises ``PermissionError`` for everything else (writes, drops, indexes, aggregations that could ``$out``).
"""
from __future__ import annotations

from typing import Any, Dict, Iterator, List

from src.pbp.game_derived import DERIVED_VERSION

SHOWN = 20                                  # ids listed per collection in the summary


class _ReadOnlyCollection:
    def __init__(self, collection: Any) -> None:
        self._collection = collection

    def find(self, filter: Any = None, projection: Any = None, *args: Any, **kwargs: Any) -> Any:
        if projection is None:
            raise PermissionError("Atlas is read with a projection only (a game is about 1 MB)")
        return self._collection.find(filter or {}, projection, *args, **kwargs)

    def count_documents(self, filter: Any = None, **kwargs: Any) -> int:
        return self._collection.count_documents(filter or {}, **kwargs)

    def __getattr__(self, name: str) -> Any:
        raise PermissionError(f"Atlas is read only: '{name}' is not allowed")


class ReadOnly:
    """A database that can be listed and read, nothing else."""

    def __init__(self, db: Any) -> None:
        self._db = db

    def list_collection_names(self) -> List[str]:
        return self._db.list_collection_names()

    def __getitem__(self, name: str) -> _ReadOnlyCollection:
        return _ReadOnlyCollection(self._db[name])

    def __getattr__(self, name: str) -> Any:
        raise PermissionError(f"Atlas is read only: '{name}' is not allowed")


def _games(db: Any) -> List[str]:
    from src.services.derived_backfill import fbcyl_collection_names, feb_collection_names

    return sorted(set(feb_collection_names(db)) | set(fbcyl_collection_names(db)))


def _state(db: Any, name: str) -> Dict[str, bool]:
    """``{id: has the current DERIVED}`` of a collection (names the ids as text; nothing else of the game is read)."""
    return {str(doc["_id"]): (doc.get("DERIVED") or {}).get("v") == DERIVED_VERSION for doc in db[name].find({}, {"_id": 1, "DERIVED.v": 1})}


def compare(archive: Any, atlas: Any) -> List[Dict[str, Any]]:
    """One row per games collection of either side."""
    atlas = atlas if isinstance(atlas, ReadOnly) else ReadOnly(atlas)
    rows = []
    mine_names, atlas_names = set(_games(archive)), set(_games(atlas))
    for name in sorted(mine_names | atlas_names):
        mine = _state(archive, name) if name in mine_names else {}
        theirs = _state(atlas, name) if name in atlas_names else {}
        rows.append({
            "collection": name, "archive": len(mine), "atlas": len(theirs),
            "only_atlas": sorted(set(theirs) - set(mine)), "only_archive": sorted(set(mine) - set(theirs)),
            "archive_stale": sum(1 for ok in mine.values() if not ok), "atlas_stale": sum(1 for ok in theirs.values() if not ok),
        })
    return rows


def missing(report: List[Dict[str, Any]]) -> int:
    """Games that Atlas has and the archive does not: what would be lost."""
    return sum(len(r["only_atlas"]) for r in report)


def _lines(report: List[Dict[str, Any]]) -> Iterator[str]:
    lost = missing(report)
    yield "## ✅ Atlas no tiene nada que no esté en el archivo" if not lost else f"## ❌ Faltan {lost} partidos en el archivo (los tiene Atlas)"
    yield ""
    yield f"Colecciones: {len(report)} · partidos en Atlas: {sum(r['atlas'] for r in report)} · en el archivo: {sum(r['archive'] for r in report)}"
    yield ""
    yield "| Colección | Archivo | Atlas | Solo Atlas | Solo archivo | Sin DERIVED actual (archivo / Atlas) |"
    yield "|---|---:|---:|---:|---:|---:|"
    for r in report:
        flag = " ❌" if r["only_atlas"] else ""
        yield f"| {r['collection']}{flag} | {r['archive']} | {r['atlas']} | {len(r['only_atlas'])} | {len(r['only_archive'])} | {r['archive_stale']} / {r['atlas_stale']} |"
    for r in report:
        if r["only_atlas"]:
            shown = ", ".join(r["only_atlas"][:SHOWN]) + (" …" if len(r["only_atlas"]) > SHOWN else "")
            yield ""
            yield f"**{r['collection']}**: solo en Atlas: {shown}"


def render_markdown(report: List[Dict[str, Any]]) -> str:
    return "\n".join(_lines(report)) + "\n"
