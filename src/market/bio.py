"""The bio of a Talent player across sources (#910, epic #872): height in whole cm, a canonical position and a field-by-field merge with provenance.

FEB leaves height and position empty for most players, NCAA writes the height in feet and inches and ACB/FIBA may do the same; whatever cannot be read is ``None``, never a guess.
``merge_bio`` is what the external sources (ACB, FIBA, NCAA: D2-D4) will use once the identity says two records are one person; ``season_rows.attach_bio`` applies the same
field-by-field idea to the rosters of FEB (other teams and seasons of the same person).
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

SOURCE_PRIORITY = ("feb", "fiba", "acb", "ncaa")        # the first source that says a field wins; FEB is the one the identity is anchored to
HEIGHT_CONFLICT_CM = 3                                  # two sources further apart than this are flagged
HEIGHT_RANGE_CM = (120, 240)
_INCHES_RANGE = (48, 95)                                # 4'0" .. 7'11"
_METRES_RANGE = (1.2, 2.4)
_CM_PER_INCH = 2.54
_FEET_INCHES = re.compile(r"""^(\d)\s*(?:'|’|′|-|ft\.?|feet)\s*(?:(\d{1,2})\s*(?:"|”|″|in\.?|inches)?)?$""")
_NUMBER = re.compile(r"^(\d+(?:[.,]\d+)?)\s*(cm|m|in|\")?$")


def _cm(value: float) -> Optional[int]:
    cm = round(value)
    return cm if HEIGHT_RANGE_CM[0] <= cm <= HEIGHT_RANGE_CM[1] else None


def _from_number(number: float, unit: Optional[str]) -> Optional[int]:
    if unit == "cm" or (unit is None and HEIGHT_RANGE_CM[0] <= number <= HEIGHT_RANGE_CM[1]):
        return _cm(number)
    if unit == "m" or (unit is None and _METRES_RANGE[0] <= number <= _METRES_RANGE[1]):
        return _cm(number * 100)
    if unit in ("in", '"') or (unit is None and _INCHES_RANGE[0] <= number <= _INCHES_RANGE[1]):
        return _cm(number * _CM_PER_INCH)
    return None


def normalize_height(value: Any) -> Optional[int]:
    """Whole cm of a height written as cm (``190``, ``"190 cm"``), metres (``"1,90"``), feet and inches (``"6-7"``, ``6'7"``, ``"6 ft 7 in"``) or total inches (``79``), else ``None``.

    The ranges do not overlap (inches 48-95, metres 1.2-2.4, cm 120-240), so a bare number is read without asking its unit; a value outside them is ``None``."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return _from_number(float(value), None) if value == value else None
    if not isinstance(value, str):
        return None
    text = value.strip().lower()
    feet = _FEET_INCHES.match(text)
    if feet:
        return _cm((int(feet.group(1)) * 12 + int(feet.group(2) or 0)) * _CM_PER_INCH) if int(feet.group(2) or 0) < 12 else None
    plain = _NUMBER.match(text)
    return _from_number(float(plain.group(1).replace(",", ".")), plain.group(2)) if plain else None


def _key(text: Any) -> str:
    if not isinstance(text, str):
        return ""
    plain = "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))
    return " ".join(plain.casefold().split())


_FINE = {"base": "Base", "pg": "Base", "point guard": "Base", "escolta": "Escolta", "sg": "Escolta", "shooting guard": "Escolta",
         "alero": "Alero", "sf": "Alero", "small forward": "Alero", "ala-pivot": "Ala-Pívot", "a-pivot": "Ala-Pívot", "ala pivot": "Ala-Pívot", "pf": "Ala-Pívot",
         "power forward": "Ala-Pívot", "pivot": "Pívot", "c": "Pívot", "center": "Pívot", "centre": "Pívot"}
_GROUP_OF_FINE = {"Base": "G", "Escolta": "G", "Alero": "F", "Ala-Pívot": "F", "Pívot": "C"}
_COARSE = {"g": "G", "guard": "G", "f": "F", "forward": "F"}


def canonical_position(value: Any) -> Optional[str]:
    """``Base``, ``Escolta``, ``Alero``, ``Ala-Pívot`` or ``Pívot`` for what FEB, ACB, FIBA and NCAA write (``A-Pívot``, ``PG``, ``Center``…); ``None`` when the text does not say it
    exactly (``G``, ``G-F``, ``Entrenador``)."""
    return _FINE.get(_key(value))


def _token_group(token: str) -> Optional[str]:
    return _COARSE.get(token) or _GROUP_OF_FINE.get(_FINE.get(token, ""))


def position_group(value: Any) -> Optional[str]:
    """``G`` (guard), ``F`` (forward) or ``C`` (centre): the coarse position every source can say (NCAA's ``G``, ``F``). A combination (``G-F``, ``F/C``) is its first group."""
    key = _key(value)
    if not key:
        return None
    if key in _FINE or key in _COARSE:
        return _token_group(key)
    parts = [p for p in re.split(r"[/\-\s]+", key) if p]
    groups = [_token_group(p) for p in parts]
    return groups[0] if parts and all(groups) else None


FIELDS = ("birth", "height", "position", "position_group", "nationality")


def _priority(candidate: Mapping[str, Any]) -> Tuple[int, str]:
    source = str(candidate.get("source") or "")
    return (SOURCE_PRIORITY.index(source) if source in SOURCE_PRIORITY else len(SOURCE_PRIORITY), source)


def _text(value: Any) -> Optional[str]:
    return value.strip() or None if isinstance(value, str) else None


def _read(candidate: Mapping[str, Any]) -> Dict[str, Any]:
    return {"birth": _text(candidate.get("birth")), "height": normalize_height(candidate.get("height")), "position": canonical_position(candidate.get("position")),
            "position_group": position_group(candidate.get("position")), "nationality": _text(candidate.get("nationality"))}


def _conflicts(values: List[Dict[str, Any]]) -> List[str]:
    heights = [v["height"] for v in values if v["height"] is not None]
    births = {v["birth"] for v in values if v["birth"]}
    groups = {v["position_group"] for v in values if v["position_group"]}
    found = [("birth", len(births) > 1), ("height", bool(heights) and max(heights) - min(heights) > HEIGHT_CONFLICT_CM), ("position", len(groups) > 1)]
    return [name for name, bad in found if bad]


def merge_bio(candidates: Iterable[Mapping[str, Any]]) -> Dict[str, Any]:
    """One bio out of what several sources say of the same person, FIELD BY FIELD: the first source of ``SOURCE_PRIORITY`` that says a field wins, an empty field takes the next one's.

    Each candidate is ``{source, birth, height, position, nationality}`` in the source's own writing. Returns the fields (height in cm, position canonical, ``position_group``), ``bio_src``
    (the source of each field that has a value) and ``bio_conflict`` (``birth`` if the dates differ, ``height`` if they are more than ``HEIGHT_CONFLICT_CM`` apart, ``position`` if the
    groups differ): the winner is kept and the conflict is for a human to look at."""
    ordered = sorted(candidates, key=_priority)
    values = [_read(c) for c in ordered]
    merged: Dict[str, Any] = {}
    sources: Dict[str, str] = {}
    for field in FIELDS:
        pick = next(((v[field], c) for v, c in zip(values, ordered) if v[field] is not None), (None, None))
        merged[field] = pick[0]
        if pick[1] is not None:
            sources[field] = str(pick[1].get("source"))
    return {**merged, "bio_src": sources, "bio_conflict": _conflicts(values)}
