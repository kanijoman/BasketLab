"""The FBCYL youth competitions in the catalogue (#920, epic #872): which of the autonomic competitions of fbcyl.es go to ``config/competitions.json``, and how they are named.

Decided by the user (13/11/2026) after the spike #915 (docs/evaluaciones/2026-11-13_formacion-fbcyl-fiba.md): only the **autonomic** competitions (the ``FBCYL`` territory of the site, ``territorial=1``),
**from cadete upwards and the senior ones**, men and women. Infantil, provincial, escolar, minibásket and menores are out. The text of a group is not unique (every category has a «3ª FASE - TÍTULO»), and the collection is named after it, so the entry's ``competition`` ends in ``G<id of the group>``: unique, and never
four digits (the selector would read them as a year); what people read is ``label`` and ``group_label``. The names of the categories change from one season to the next
(``1ªDIV.-CAD.FEM.AUT.``, ``1ªDIV. - CAD. FEM. AUT.``), so they are read by what they say; what is not recognised is reported and left out, never guessed. Pure: the network is in ``run_fbcyl_catalogue.py``.
"""
from __future__ import annotations

import json
import re
import time
import unicodedata
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

TERRITORY = "1"                                   # «FBCYL» in the territories of the site: the autonomic competitions

_EXCLUDED = re.compile(r"MINI|BENJAM|ALEV|PREMINI|3X3|\bINF\b|INFANTIL")
_CADETE = re.compile(r"\bCAD\b|CADETE")
_JUNIOR = re.compile(r"JUNIOR|\bJUN\b")
_SENIOR = re.compile(r"SENIOR|\bDIV(?:ISION)?\.? (?:MASCULINA|FEMENINA)\b")
_DIVISION = re.compile(r"\b([12])A\s*DIV")


def _plain(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", text or "") if not unicodedata.combining(c)).upper()


def classify_category(text: str) -> Tuple[str, Optional[str]]:
    """``("senior", None)``, ``("formacion", "U16")`` (cadete), ``("formacion", "U18")`` (júnior), ``("excluded", None)`` (infantil, minibásket and smaller, 3x3) or ``("unknown", None)``."""
    plain = _plain(text)
    if not plain.strip():
        return ("unknown", None)
    if _EXCLUDED.search(plain):
        return ("excluded", None)
    if _CADETE.search(plain):
        return ("formacion", "U16")
    if _JUNIOR.search(plain):
        return ("formacion", "U18")
    if _SENIOR.search(plain):
        return ("senior", None)
    return ("unknown", None)


def category_label(text: str, gender: str) -> str:
    """The name people read of a category: ``1ª División cadete femenino``, ``Liga UEMC júnior masculino``, ``1ª División masculina``, ``Sénior FBCYL femenino``."""
    plain = _plain(text)
    level = "cadete" if _CADETE.search(plain) else "júnior" if _JUNIOR.search(plain) else None
    division = _DIVISION.search(plain)
    if "UEMC" in plain:
        base = "Liga UEMC"
    elif "SENIOR" in plain:
        base = "Sénior FBCYL"
    elif division:
        base = f"{division.group(1)}ª División"
    else:
        return text.strip()
    feminine = division is not None and level is None                  # «1ª División masculina», but «cadete masculino» and «Sénior FBCYL femenino»
    word = ("masculina" if feminine else "masculino") if gender == "M" else ("femenina" if feminine else "femenino")
    return " ".join(p for p in (base, level, word) if p)


def is_tournament(group_text: str) -> bool:
    """A tournament of selections or clubs listed inside a category («Tº INTERNACIONAL SELECCIONES U16…»): not a league."""
    return bool(re.match(r"^T[º°]\s", (group_text or "").strip()))


def catalogue_entries(combos: Iterable[Dict[str, Any]], season: str, existing: Iterable[Dict[str, Any]], active: bool = True) -> Tuple[List[Dict[str, Any]], List[str]]:
    """``(new entries, unknown category texts)`` of one season.

    ``combos`` are the answers of the site: ``{season, gender, category, category_text, competitions: [{id, text}]}``. A group already in ``existing`` (by its id) is never added again, so running it
    twice adds nothing and never touches what is there. ``active=False`` adds the season paused: it is loaded in batches, as the youth championships of FEB."""
    known = {str((e.get("fbcyl") or {}).get("competition_id")) for e in existing if e.get("fbcyl")}
    entries: List[Dict[str, Any]] = []
    unknown: List[str] = []
    for combo in combos:
        if str(combo["season"]) != str(season):
            continue
        kind, age = classify_category(combo["category_text"])
        if kind == "unknown":
            if combo["category_text"] not in unknown:
                unknown.append(combo["category_text"])
            continue
        if kind == "excluded":
            continue
        label = category_label(combo["category_text"], combo["gender"])
        for group in combo["competitions"]:
            text = " ".join(group["text"].split())                      # the site leaves double spaces in some names
            if is_tournament(text) or str(group["id"]) in known:
                continue
            entry: Dict[str, Any] = {"league": "fbcyl", "competition": f"{text} G{group['id']}", "season_label": str(season), "season_value": str(season), "active": active,
                                     "note": f"{label}, {text}", "category": kind, "label": label, "group_label": text,
                                     "fbcyl": {"competition_id": str(group["id"]), "category": str(combo["category"]), "gender": combo["gender"], "territory": TERRITORY}}
            if age:
                entry["age_group"] = age
            entries.append(entry)
            known.add(str(group["id"]))
    return entries, unknown


GENDERS = ("M", "F", "X")
PAUSE_S = 1.0


def fetch_combos(scraper: Any, season: str, sleep: Callable[[float], None] = time.sleep) -> List[Dict[str, Any]]:
    """The categories and groups of the autonomic territory of one season, as ``catalogue_entries`` reads them. ``scraper`` is ``FBCYLWebScraper``; one second between requests."""
    combos: List[Dict[str, Any]] = []
    for gender in GENDERS:
        categories = scraper.fetch_categories_ajax(str(season), gender, TERRITORY)
        sleep(PAUSE_S)
        for text, value in categories:
            groups = scraper.fetch_competitions_ajax(value, gender, TERRITORY)
            sleep(PAUSE_S)
            combos.append({"season": str(season), "gender": gender, "category": value, "category_text": text, "competitions": [{"id": gid, "text": gtext} for gtext, gid in groups]})
    return combos


def update_catalogue_file(path: Any, combos: List[Dict[str, Any]], seasons: Dict[str, bool]) -> Dict[str, Any]:
    """Add the groups of ``seasons`` (``{season: active}``) to the catalogue file and leave everything else as it is: the file is only written if something was added, in the format it already has."""
    path = Path(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    entries = data["competitions"]
    added: List[Dict[str, Any]] = []
    unknown: List[str] = []
    for season, active in seasons.items():
        new, missing = catalogue_entries(combos, season, entries + added, active=active)
        added += new
        unknown += [u for u in missing if u not in unknown]
    if added:
        data["competitions"] = entries + added
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return {"added": len(added), "paused_added": sum(1 for e in added if not e["active"]), "unknown": unknown}
