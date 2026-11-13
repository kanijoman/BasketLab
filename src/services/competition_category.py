"""The category of each competition (#914, epic #872): senior or formación, and for formación its age group, normalised once.

The catalogue (``config/competitions.json``) says it with ``category`` (``"formacion"``; absent is senior), ``age_group`` (``U14`` infantil, ``U16`` cadete, ``U18`` júnior, ``U20`` with no
Spanish equivalent: no match is forced) and ``label`` (the name people read, which the youth codes of FEB do not have: ``C ESP CLUBES JR FEM``). The browser's selector and Talent read them from
the manifests, not from the name of the competition. Whatever a source writes that is not in the table has no age group: it is never guessed (``juvenil`` is not ``júnior``).
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, Iterable, List, Optional

CATEGORIES = ("senior", "formacion")
AGE_GROUPS: Dict[str, Optional[str]] = {"U14": "Infantil", "U16": "Cadete", "U18": "Júnior", "U20": None}      # code -> its Spanish name (U20 has none)
_ALIASES = {"u14": "U14", "sub14": "U14", "infantil": "U14", "inf": "U14", "u16": "U16", "sub16": "U16", "cadete": "U16", "cad": "U16",
            "u18": "U18", "sub18": "U18", "junior": "U18", "jr": "U18", "u20": "U20", "sub20": "U20"}


def _plain(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c)).lower())


def normalize_age_group(value: Any) -> Optional[str]:
    """``U14``, ``U16``, ``U18`` or ``U20`` for every way the sources write them (``sub-16``, ``Cadete``, ``JR``, ``Júnior``…); ``None`` for anything else."""
    return _ALIASES.get(_plain(value)) if isinstance(value, str) else None


def check_category(where: str, raw: Dict[str, Any]) -> Dict[str, Any]:
    """The category fields of a catalogue entry, validated and normalised (``age_group`` to its code): ``ValueError`` names the entry and the field. A youth entry needs both its age group and its name."""
    category, age, label = raw.get("category"), raw.get("age_group"), raw.get("label")
    if category is not None and category not in CATEGORIES:
        raise ValueError(f"{where}: category must be one of {CATEGORIES}, not {category!r}")
    if label is not None and (not isinstance(label, str) or not label.strip()):
        raise ValueError(f"{where}: label must be a text")
    if age is not None and category != "formacion":
        raise ValueError(f"{where}: age_group only goes with category \"formacion\"")
    if category != "formacion":
        return {}
    code = normalize_age_group(age)
    if code is None:
        raise ValueError(f"{where}: a formacion entry needs an age_group of {tuple(AGE_GROUPS)} (or its Spanish name), not {age!r}")
    if label is None:
        raise ValueError(f"{where}: a formacion entry needs its label (the name people read)")
    return {"age_group": code}


def competition_in(name: str) -> str:
    """``C_ESP_CLUBES_JR_FEM_2024_2025_PRIMERA_FASE_A`` -> ``C_ESP_CLUBES_JR_FEM``: what comes before the first year of the collection name."""
    parts: List[str] = []
    for part in name.split("_"):
        if re.match(r"^\d{4}$", part):
            break
        parts.append(part)
    return "_".join(parts)


def category_facts(entry: Dict[str, Any]) -> Dict[str, Any]:
    """``{category, age_group?, label?}`` of one catalogue entry (a competition without ``category`` is senior)."""
    out: Dict[str, Any] = {"category": entry.get("category", "senior")}
    if entry.get("age_group"):
        out["age_group"] = entry["age_group"]
    if entry.get("label"):
        out["label"] = entry["label"]
    return out


def category_of_competition(label: str, catalogue: List[Dict[str, Any]]) -> Dict[str, Any]:
    """The facts of the FEB competition with this label (``L.F.-2``, ``CE SSAA Cadete Fem.``: accents and punctuation do not count), ``{}`` when the catalogue does not have it."""
    key = _plain(label)
    return next((category_facts(e) for e in catalogue if e["league"] == "feb" and _plain(e["competition"]) == key), {})


def competition_categories(names: Iterable[str], catalogue: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """``{collection: {category, age_group?, label?}}`` of the collections whose competition is in the catalogue (every season and phase of it, paused entries too); the rest are left out, never guessed."""
    from src.database import get_collection_name

    by_name: Dict[str, Dict[str, Any]] = {}
    for entry in catalogue:
        key = _plain(entry["competition"]) if entry["league"] == "feb" else get_collection_name(f"FBCYL_{entry['competition']}", entry["season_value"], "")
        by_name.setdefault(key, category_facts(entry))
    out: Dict[str, Dict[str, Any]] = {}
    for name in names:
        found = by_name.get(name) or by_name.get(_plain(competition_in(name)))
        if found:
            out[name] = dict(found)
    return out
