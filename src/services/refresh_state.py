"""What the refresh remembers between runs (#924): which collections are CLOSED and which matches keep failing.

A refresh used to check EVERY active collection EVERY time (about 27 requests and 2.5 MB each, ~3.7 s from the runner) even when nothing could have changed, and to ask again for a match
that fails on every run. Thresholds (the user's, 13/11/2026):

* a collection is CLOSED when its last game is more than ``CLOSED_AFTER_DAYS`` old and it was up to date at its last check; it is checked again every ``RECHECK_CLOSED_EVERY_DAYS``
  days, not on every run (the current season, and anything with a recent or missing game, is checked every time);
* a match that fails is asked again until it has failed ``MAX_ATTEMPTS`` times over at least ``MIN_DAYS_BEFORE_UNAVAILABLE`` days; then it is «unavailable» and asked once every
  ``REVIEW_UNAVAILABLE_EVERY_DAYS`` days; if it ever arrives it is stored and forgotten here.

The state is ``{"checked": day, "last_game": day, "failed": {code: {n, first, last, why, unavailable}}}`` in the ``refresh`` field of ``COLLECTION_META``: it travels in the archive, so it is saved with
DAYS (never times: a time would change the archive on every refresh) and always in the same order. A network failure never closes a collection.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional

META = "COLLECTION_META"
CLOSED_AFTER_DAYS = 14
RECHECK_CLOSED_EVERY_DAYS = 7
MAX_ATTEMPTS = 20
MIN_DAYS_BEFORE_UNAVAILABLE = 7
REVIEW_UNAVAILABLE_EVERY_DAYS = 30
_WHY = 120


def _day(value: Any) -> Optional[date]:
    """A day from ``2026-11-13`` or from an ISO datetime (``2026-11-13T14:00``), or None."""
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def is_closed(state: Optional[Dict[str, Any]], today: date) -> bool:
    """True when the last game is more than ``CLOSED_AFTER_DAYS`` old and the last check was less than ``RECHECK_CLOSED_EVERY_DAYS`` ago; without both dates, never."""
    state = state or {}
    last, checked = _day(state.get("last_game")), _day(state.get("checked"))
    if last is None or checked is None:
        return False
    return (today - last).days > CLOSED_AFTER_DAYS and 0 <= (today - checked).days < RECHECK_CLOSED_EVERY_DAYS


def record_check(state: Dict[str, Any], up_to_date: Optional[bool], last_game: Any, today: date) -> Dict[str, Any]:
    """After a check: closes the collection if it is up to date and its last game is old, opens it otherwise. The failed matches are not touched."""
    day = _day(last_game)
    if up_to_date is True and day is not None and (today - day).days > CLOSED_AFTER_DAYS:
        state["checked"], state["last_game"] = today.isoformat(), day.isoformat()
    else:
        state.pop("checked", None)
        state.pop("last_game", None)
    return state


def should_ask(state: Optional[Dict[str, Any]], code: Any, today: date) -> bool:
    """False only for an unavailable match that was asked less than ``REVIEW_UNAVAILABLE_EVERY_DAYS`` ago."""
    entry = ((state or {}).get("failed") or {}).get(str(code))
    if not entry or not entry.get("unavailable"):
        return True
    last = _day(entry.get("last"))
    return last is None or (today - last).days >= REVIEW_UNAVAILABLE_EVERY_DAYS


def record_failure(state: Dict[str, Any], code: Any, why: str, today: date) -> Dict[str, Any]:
    """One more failed attempt for a match; it becomes unavailable after ``MAX_ATTEMPTS`` over ``MIN_DAYS_BEFORE_UNAVAILABLE`` days (and stays so, asked once a month)."""
    failed = state.setdefault("failed", {})
    entry = failed.get(str(code)) or {"n": 0, "first": today.isoformat()}
    entry["n"] = int(entry.get("n", 0)) + 1
    entry["last"] = today.isoformat()
    entry["why"] = str(why)[:_WHY]
    first = _day(entry.get("first")) or today
    entry["unavailable"] = bool(entry.get("unavailable")) or (entry["n"] >= MAX_ATTEMPTS and (today - first).days >= MIN_DAYS_BEFORE_UNAVAILABLE)
    if not entry["unavailable"]:
        entry.pop("unavailable")
    failed[str(code)] = entry
    return state


def record_success(state: Dict[str, Any], code: Any) -> Dict[str, Any]:
    """A match that arrived: no more memory of its failures."""
    failed = state.get("failed")
    if failed and str(code) in failed:
        del failed[str(code)]
        if not failed:
            del state["failed"]
    return state


def unavailable_codes(state: Optional[Dict[str, Any]]) -> List[str]:
    return sorted(c for c, e in ((state or {}).get("failed") or {}).items() if e.get("unavailable"))


def _canonical(state: Dict[str, Any]) -> Dict[str, Any]:
    """The state in a fixed order and without empty parts: the same bytes whatever the order it was built in."""
    out: Dict[str, Any] = {}
    for key in ("checked", "last_game"):
        if state.get(key):
            out[key] = state[key]
    failed = state.get("failed") or {}
    if failed:
        out["failed"] = {code: {k: failed[code][k] for k in ("n", "first", "last", "why", "unavailable") if k in failed[code]} for code in sorted(failed)}
    return out


def load_state(db: Any, collection: str) -> Dict[str, Any]:
    doc = db.repository.connection.get_collection(META).find_one({"_id": collection}, {"refresh": 1}) or {}
    return dict(doc.get("refresh") or {})


def save_state(db: Any, collection: str, state: Dict[str, Any]) -> None:
    """Write the state in ``COLLECTION_META`` (only when it changed; an empty one removes the field and never creates a document)."""
    meta = db.repository.connection.get_collection(META)
    wanted = _canonical(state)
    stored = (meta.find_one({"_id": collection}, {"refresh": 1}) or {}).get("refresh") or {}
    if stored == wanted and list(stored) == list(wanted):
        return
    if wanted:
        meta.update_one({"_id": collection}, {"$set": {"refresh": wanted}}, upsert=True)
    elif meta.find_one({"_id": collection}) is not None:
        meta.update_one({"_id": collection}, {"$unset": {"refresh": ""}})
