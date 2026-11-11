"""The gender of each competition for the manifest (#843): the browser picks the win probability calibrated for its family (``live_core.config.WP_BY_GENDER``) with it.

Read from what already says it, never from a new list: a FEB collection by the label of its competition in ``COLLECTION_META`` (``competition_info.competition_infos``, the catalogue of the packages)
or, without metadata, by the competition in the name of the collection (``L_F_-2_2025_2026_...`` is ``L.F.-2``); a FBCYL one by the ``_gender`` its games carry or, without it, by the entry of its group
in the catalogue (paused entries too: an older season is still read). A competition that says nothing is left out, and the browser uses the neutral defaults.
"""
from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List

from src.live_prep.competition_info import GENDERS, competition_infos
from src.utils.collection_utils import is_fbcyl

_YEAR = re.compile(r"^\d{4}$")


def _competition_in(name: str) -> str:
    """``L_F_-2_2025_2026_Liga_Regular_B`` -> ``L_F_-2``: what comes before the first year of the collection name."""
    parts: List[str] = []
    for part in name.split("_"):
        if _YEAR.match(part):
            break
        parts.append(part)
    return "_".join(parts)


def _feb(handler: Any, names: List[str], catalogue: List[Dict[str, Any]]) -> Dict[str, str]:
    from src.scraper.schedule_client import normalize_name
    from src.services.competition_catalogue import package_catalog

    catalog = package_catalog(catalogue)
    said = {c: i.get("gender") for c, i in competition_infos(handler, names, catalog, []).items()}
    by_name = {normalize_name(c["competition"]): c.get("gender") for c in catalog}
    found = {c: said[c] or by_name.get(normalize_name(_competition_in(c))) for c in names}
    return {c: g for c, g in found.items() if g in GENDERS}


def _fbcyl(handler: Any, names: List[str], catalogue: List[Dict[str, Any]]) -> Dict[str, str]:
    from src.database import get_collection_name

    db = handler.connection.client["BASKETBALL"]
    of_group = {get_collection_name(f"FBCYL_{e['competition']}", e["season_value"], ""): e["fbcyl"].get("gender") for e in catalogue if e.get("league") == "fbcyl"}
    found: Dict[str, str] = {}
    for name in names:
        game = db[name].find_one({"_gender": {"$in": list(GENDERS)}}, {"_gender": 1}) or {}
        gender = game.get("_gender") or of_group.get(name)
        if gender in GENDERS:
            found[name] = gender
    return found


def competition_genders(handler: Any, names: Iterable[str], catalogue: List[Dict[str, Any]]) -> Dict[str, str]:
    """``{collection: "F"|"M"}`` of the competitions that say it; ``catalogue`` is ``competition_catalogue.load_catalogue``."""
    names = list(names)
    return {**_feb(handler, [n for n in names if not is_fbcyl(n)], catalogue), **_fbcyl(handler, [n for n in names if is_fbcyl(n)], catalogue)}
