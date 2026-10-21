"""Structured data of the competition of each published collection (issue #438, epic #435).

The app listed and filtered matches parsing the name of the collection. The index now carries ``competition: {key, label, competition,
group, season, level, gender}`` per entry: names come from the scrape metadata (``COLLECTION_META``), ``level``/``gender``/``clubs`` from the
``competitions`` catalog of ``config/package_publish.json`` (matched by competition name, case and punctuation ignored). ``clubs`` are the
clubs whose packages are prepared in that competition (not published). "De interés" teams are NOT here: the user marks them in the app.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

GENDERS = ("M", "F")


def _norm(name: str) -> str:
    from src.scraper.schedule_client import normalize_name

    return normalize_name(name)


def normalize_catalog(entries: Optional[Iterable[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    """Validated ``competitions`` entries of the config (``ValueError`` naming the position of a bad one)."""
    out: List[Dict[str, Any]] = []
    for i, raw in enumerate(entries or [], start=1):
        name = raw.get("competition")
        level, gender, clubs = raw.get("level"), raw.get("gender"), raw.get("clubs", [])
        if not name or not isinstance(name, str):
            raise ValueError(f"competitions entry #{i} lacks: competition")
        if level is not None and (isinstance(level, bool) or not isinstance(level, int)):
            raise ValueError(f"competitions entry #{i}: level must be an integer")
        if gender is not None and gender not in GENDERS:
            raise ValueError(f"competitions entry #{i}: gender must be one of {GENDERS}")
        if not isinstance(clubs, list):
            raise ValueError(f"competitions entry #{i}: clubs must be a list of team ids")
        out.append({"competition": name, "level": level, "gender": gender, "clubs": [str(c) for c in clubs]})
    return out


def _meta(db: Any, collection: str) -> Dict[str, Any]:
    try:
        return db.repository.connection.get_collection("COLLECTION_META").find_one({"_id": collection}) or {}
    except Exception:  # noqa: BLE001 - labels are optional: a database that cannot answer never stops the publication
        return {}


def competition_infos(db: Any, collections: Iterable[str], catalog: List[Dict[str, Any]], default_clubs: List[str]) -> Dict[str, Dict[str, Any]]:
    """``{collection: info}``; a collection without metadata is labelled with its own name and a competition not in the catalog has no level/gender."""
    by_name = {_norm(c["competition"]): c for c in catalog}
    out: Dict[str, Dict[str, Any]] = {}
    for collection in collections:
        meta = _meta(db, collection)
        competition = meta.get("competition_label") or collection
        group = meta.get("group_label") or ""
        entry = by_name.get(_norm(competition), {})
        out[collection] = {
            "key": collection, "label": f"{competition} · {group}" if group else competition, "competition": competition, "group": group,
            "season": meta.get("season_label") or "", "level": entry.get("level"), "gender": entry.get("gender"),
            "clubs": list(entry.get("clubs") or default_clubs),
        }
    return out


def public(info: Dict[str, Any]) -> Dict[str, Any]:
    """What goes in the index: everything but the clubs whose packages are prepared."""
    return {k: v for k, v in info.items() if k != "clubs"}
