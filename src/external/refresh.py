"""The refresh of an external source (#884): its own job, its own archive and its own freshness, isolated from the others and from FEB.

For one source: restore its archive, ask the registered source for the games of each of its active competitions since the rewrite window, validate each one (``market.canonical.validate_game``; a game that is not
canonical is rejected with its reason), mark it with its reconciliation (``market.box_reconciliation``: an unreliable game is kept and flagged ``_reliable: false``, never discarded), merge it by ``_id`` and write
the archive back (the format of the private archive, ``local_data.archive``) in ``<out>/<source>/`` together with ``status.json`` (when it ran, when it last worked, how many games). A failure is reported in the status
and leaves the archive as it was; it never reaches another source.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from src.external.registry import SOURCES
from src.local_data.archive import MANIFEST, dump_archive, load_archive
from src.market.box_reconciliation import CORE_STATS, reconcile_game
from src.market.canonical import validate_game
from src.services.competition_catalogue import external_collections

STATUS = "status.json"
DEFAULT_WINDOW_DAYS = 3                       # the sources correct games after the fact: the last days are asked again on every run
_STAMP = "%Y-%m-%dT%H:%M:%SZ"
_REASONS = 5                                  # how many rejected games the status lists (the count is complete)


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
        return {**doc, "_reliable": False, "_mismatches": ["BOX"]}
    failing = sorted({c.stat for c in result.mismatches(CORE_STATS)}, key=CORE_STATS.index)
    return {**doc, "_reliable": result.reliable, **({"_mismatches": failing} if failing else {})}


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
    try:
        if (folder / MANIFEST).is_file():
            load_archive(folder, db)
        since, rejected, totals = _since(previous, window_days), [], {"new": 0, "updated": 0}
        for name, entry in collections.items():
            counts = _merge(db[name], SOURCES[source].fetch(entry, since), entry["gender"], rejected)
            totals = {k: totals[k] + counts[k] for k in totals}
        dump_archive(db, folder, light=lambda _name: False, only=list(collections), allow_shrink=False)
    except Exception as error:  # noqa: BLE001 - whatever the source does wrong stays in its own status
        status["error"] = f"{type(error).__name__}: {error}"[:300]
    else:
        stored = [d for name in collections for d in db[name].find({}, {"_reliable": 1})]
        status.update({"state": "ok", "ok": True, "last_ok": _stamp(now), "window_days": window_days, "competitions": list(collections), "games": len(stored), **totals,
                       "unreliable": sum(1 for d in stored if not d.get("_reliable")), "rejected": rejected[:_REASONS], "rejected_total": len(rejected)})
    folder.mkdir(parents=True, exist_ok=True)
    (folder / STATUS).write_text(json.dumps(status, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return status


def run_sources(names: Iterable[str], catalogue: List[Dict[str, Any]], db: Any, out_root: Path, now: datetime, window_days: int = DEFAULT_WINDOW_DAYS) -> Dict[str, Dict[str, Any]]:
    """Every source on its own: whatever one of them does, the others run and write theirs."""
    return {name: refresh_source(name, catalogue, db, out_root, now, window_days) for name in names}
