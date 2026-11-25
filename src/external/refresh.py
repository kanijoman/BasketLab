"""The refresh of an external source (#884): its own job, its own archive and its own freshness, isolated from the others and from FEB.

For one source: restore its archive, ask the registered source for the games of each of its active competitions since the rewrite window, validate each one (``market.canonical.validate_game``; a game that is not
canonical is rejected with its reason), mark it with its reconciliation (``market.box_reconciliation``: an unreliable game is kept and flagged ``_reliable: false``, never discarded), merge it by ``_id`` and write
the archive back (the format of the private archive, ``local_data.archive``) in ``<out>/<source>/`` together with ``status.json`` (when it ran, when it last worked, how many games). A failure is reported in the status, keeps the games the run had already merged (#1090) and does not move the date of the last good run; it never reaches another source.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from src.external.registry import SOURCES
from src.local_data.archive import MANIFEST, dump_archive, load_archive
from src.market.box_reconciliation import CORE_STATS, RECONCILE_VERSION, reconcile_game
from src.market.canonical import validate_game
from src.services.competition_catalogue import external_collections

STATUS = "status.json"
DEFAULT_WINDOW_DAYS = 3                       # the sources correct games after the fact: the last days are asked again on every run
_STAMP = "%Y-%m-%dT%H:%M:%SZ"
_REASONS = 5                                  # how many rejected games the status lists (the count is complete)
_NOTES = 20                                   # and how many notes of the source


def _stamp(now: datetime) -> str:
    return now.strftime(_STAMP)


def _previous(folder: Path) -> Dict[str, Any]:
    path = folder / STATUS
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


def _since(previous: Dict[str, Any], window_days: int) -> Optional[str]:
    """The first run asks for everything; later ones for what changed since the previous good run, minus the rewrite window."""
    if not previous.get("last_ok"):
        return None
    return (datetime.strptime(previous["last_ok"], _STAMP) - timedelta(days=window_days)).strftime("%Y-%m-%d")


def _marked(doc: Dict[str, Any]) -> Dict[str, Any]:
    """The game with its reconciliation: ``_reliable`` and, when it does not reconcile, the core statistics that fail. A game that cannot be reconciled (no box) is unreliable."""
    try:
        result = reconcile_game(doc)
    except ValueError:
        return {**doc, "_reliable": False, "_mismatches": ["BOX"], "_reconciled_with": RECONCILE_VERSION}
    failing = sorted({c.stat for c in result.mismatches(CORE_STATS)}, key=CORE_STATS.index)
    return {**doc, "_reliable": result.reliable, "_reconciled_with": RECONCILE_VERSION, **({"_mismatches": failing} if failing else {})}


def _known_filter(source: Any) -> Dict[str, Any]:
    """The stored games the source does not need to ask for again: all, except those its ``refetch_filter`` (a Mongo filter, optional) selects, the ones stored before the source kept a field it keeps now. Once
    asked for again they have the field (empty or not), so the filter no longer selects them."""
    refetch = getattr(source, "refetch_filter", None)
    return {"$nor": [refetch]} if refetch else {}


def _rejudge(collection: Any) -> int:
    """Judge again, from what is stored (no request), the games flagged unreliable under an older version of the rule. Once per version: the stamp stops a really bad game from being judged on every run."""
    done = 0
    for stored in list(collection.find({"_reliable": False, "_reconciled_with": {"$not": {"$gte": RECONCILE_VERSION}}})):
        doc = _marked({k: v for k, v in stored.items() if k not in ("_reliable", "_mismatches", "_reconciled_with")})
        collection.replace_one({"_id": doc["_id"]}, doc)
        done += doc != stored
    return done


def _merge(collection: Any, docs: Iterable[Dict[str, Any]], gender: str, rejected: List[Dict[str, str]]) -> Dict[str, int]:
    new = updated = 0
    for raw in docs:
        problems = validate_game(raw, gender) if isinstance(raw, dict) else ["not a document"]
        if problems:
            rejected.append({"id": str(raw.get("_id") if isinstance(raw, dict) else None), "reason": problems[0]})
            continue
        doc = _marked(raw)
        stored = collection.find_one({"_id": doc["_id"]})
        if stored is None:
            new += 1
        elif stored != doc:
            updated += 1
        else:
            continue
        collection.replace_one({"_id": doc["_id"]}, doc, upsert=True)
    return {"new": new, "updated": updated}


def _pending(source: str, why: str) -> Dict[str, Any]:
    return {"source": source, "state": "pending", "ok": None, "reason": why}


def _save_what_was_read(db: Any, folder: Path, collections: Dict[str, Any], status: Dict[str, Any], previous: Dict[str, Any]) -> Dict[str, Any]:
    """A run that fails midway keeps the games it had already merged (#1090: a batch is ≈ 20 minutes of requests). The date of the last good run does not move, so the next run asks again; the counts are those of
    what the archive now holds. If even saving fails, the error says it and the archive stays as it was."""
    try:
        dump_archive(db, folder, light=lambda _name: False, only=list(collections), allow_shrink=False)
    except Exception as error:  # noqa: BLE001
        return {"error": f"{status['error']}; and it could not save what it had read: {type(error).__name__}: {error}"[:300]}
    stored = [d for name in collections for d in db[name].find({}, {"_reliable": 1})]
    gained = len(stored) - previous.get("games", 0)
    return {"games": len(stored), "unreliable": sum(1 for d in stored if not d.get("_reliable")), **({"saved": gained} if gained > 0 else {})}


def refresh_source(source: str, catalogue: List[Dict[str, Any]], db: Any, out_root: Path, now: datetime, window_days: int = DEFAULT_WINDOW_DAYS) -> Dict[str, Any]:
    """Refresh one source into ``<out_root>/<source>/`` and return its status. A source that is not registered, or has no active competition, is ``pending`` and writes nothing."""
    collections = {name: entry for name, entry in external_collections(catalogue).items() if entry["league"] == source}
    if source not in SOURCES:
        return _pending(source, "no scraper is registered for this source yet")
    if not collections:
        return _pending(source, "the catalogue has no active competition of this source")
    folder = Path(out_root) / source
    previous = _previous(folder)
    # a failed run does not change what the archive holds: the status keeps the counts of the last good one (the freshness of the web must not say the source has fewer games)
    status: Dict[str, Any] = {"source": source, "state": "failed", "ok": False, "finished": _stamp(now), "last_ok": previous.get("last_ok"),
                              **{key: previous[key] for key in ("competitions", "games", "unreliable") if key in previous}}
    restored = False
    try:
        if (folder / MANIFEST).is_file():
            load_archive(folder, db)
        restored = True
        since, rejected, totals = _since(previous, window_days), [], {"new": 0, "updated": 0}
        for name, entry in collections.items():
            rejudged = _rejudge(db[name])
            known = frozenset(doc["_id"] for doc in db[name].find(_known_filter(SOURCES[source]), {"_id": 1}))
            counts = _merge(db[name], SOURCES[source].fetch(entry, since, known), entry["gender"], rejected)
            totals = {k: totals[k] + counts[k] + (rejudged if k == "updated" else 0) for k in totals}
        getattr(SOURCES[source], "finish", lambda: None)()           # the end of the run: a source may fail it for what it saw in all the entries (NCAA, #1086)
        dump_archive(db, folder, light=lambda _name: False, only=list(collections), allow_shrink=False)
    except Exception as error:  # noqa: BLE001 - whatever the source does wrong stays in its own status
        status["error"] = f"{type(error).__name__}: {error}"[:300]
        if restored:
            status.update(_save_what_was_read(db, folder, collections, status, previous))
    else:
        stored = [d for name in collections for d in db[name].find({}, {"_reliable": 1})]
        notes = list(getattr(SOURCES[source], "notes", []))
        partial = getattr(SOURCES[source], "complete", True) is False        # it stopped for its budget (#888): what it read is kept, but the date the next run starts from does not move
        status.update({"state": "ok", "ok": True, "last_ok": status["last_ok"] if partial else _stamp(now), "window_days": window_days, **({"partial": True} if partial else {}), "competitions": list(collections), "games": len(stored), **totals,
                       "unreliable": sum(1 for d in stored if not d.get("_reliable")), "rejected": rejected[:_REASONS], "rejected_total": len(rejected),
                       **({"notes": notes[:_NOTES], "notes_total": len(notes)} if notes else {})})
    folder.mkdir(parents=True, exist_ok=True)
    (folder / STATUS).write_text(json.dumps(status, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return status


def run_sources(names: Iterable[str], catalogue: List[Dict[str, Any]], db: Any, out_root: Path, now: datetime, window_days: int = DEFAULT_WINDOW_DAYS) -> Dict[str, Dict[str, Any]]:
    """Every source on its own: whatever one of them does, the others run and write theirs."""
    return {name: refresh_source(name, catalogue, db, out_root, now, window_days) for name in names}
