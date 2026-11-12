"""Competition and season of each collection (B2, #878): the unit of a Talent row.

Competitions are never mixed: LF Endesa is not LF Challenge, senior is not youth, FEB is not FBCYL. Only the phases and groups of the SAME competition and season are put
together (Tercera FEB has dozens of subgroups, the Copa has groups and play-offs; the two FBCYL groups of the Primera Nacional Femenina are groups of one competition too).

Where the answer comes from, in order: the scrape metadata of the collection (``COLLECTION_META``: the label of the competition as FEB writes it and the year the season starts in), the name of the
collection (``{competition}_{season label}_{group}``, sanitised, so ``L_F_-2``; the key normalises both the same way: ``lf2``) and, for FBCYL, which has no metadata, the catalogue
(``config/competitions.json``: category + territory + season is the competition, each group an entry). A collection that says nothing is returned in ``unknown`` and never guessed.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

_NAME = re.compile(r"^(?P<competition>.+?)_(?P<start>20\d\d)_(?P<end>20\d\d)_(?P<group>.*)$")


@dataclass(frozen=True)
class CompetitionSeason:
    key: str
    league: str                 # "feb" | "fbcyl"
    competition: str            # the label to show
    season: str                 # the year the season starts in: "2025" for 2025/2026
    season_label: str


@dataclass(frozen=True)
class Member:
    collection: str
    group: str


def _norm(text: str) -> str:
    from src.scraper.schedule_client import normalize_name

    return normalize_name(text)


def _fbcyl_index(catalogue: Iterable[Mapping[str, Any]]) -> Dict[str, Tuple[CompetitionSeason, str]]:
    """``{collection name: (competition, group label)}`` of the FBCYL entries of the catalogue, paused ones too: an older season is still read."""
    from src.database import get_collection_name

    index: Dict[str, Tuple[CompetitionSeason, str]] = {}
    for entry in catalogue:
        if entry.get("league") != "fbcyl":
            continue
        fbcyl, season = entry["fbcyl"], str(entry["season_value"])
        label = (entry.get("note") or "").split(",")[0].strip() or entry["competition"]       # "Primera Nacional Femenina, grupo A-1" -> the competition without its group
        competition = CompetitionSeason(f"fbcyl|{fbcyl['category']}-{fbcyl.get('territory', '0')}|{season}", "fbcyl", label, season, str(entry.get("season_label") or season))
        index[get_collection_name(f"FBCYL_{entry['competition']}", season, "")] = (competition, entry["competition"])
    return index


def _feb(collection: str, meta: Optional[Mapping[str, Any]]) -> Optional[Tuple[CompetitionSeason, str]]:
    meta = meta or {}
    named = _NAME.match(collection)
    label = meta.get("competition_label") or (named.group("competition").replace("_", " ") if named else None)
    season = str(meta.get("season_value") or (named.group("start") if named else "") or "")
    if not label or not season:
        return None
    season_label = str(meta.get("season_label") or (f"{named.group('start')}/{named.group('end')}" if named else season))
    group = meta.get("group_label") or (named.group("group").replace("_", " ") if named else "")
    return CompetitionSeason(f"feb|{_norm(label)}|{season}", "feb", label, season, season_label), group


def competitions_of(collections: Iterable[str], metas: Mapping[str, Mapping[str, Any]], catalogue: Iterable[Mapping[str, Any]]
                    ) -> Tuple[Dict[CompetitionSeason, List[Member]], List[str]]:
    """``({competition: [member, ...]}, unknown)``: both sorted (by key and by collection), so the order of the collections never changes a file."""
    fbcyl = _fbcyl_index(catalogue)
    found: Dict[CompetitionSeason, List[Member]] = {}
    unknown: List[str] = []
    for collection in sorted(set(collections)):
        hit = fbcyl.get(collection) if collection.startswith("FBCYL_") else _feb(collection, metas.get(collection))
        if hit is None:
            unknown.append(collection)
            continue
        competition, group = hit
        found.setdefault(competition, []).append(Member(collection, group))
    return dict(sorted(found.items(), key=lambda kv: kv[0].key)), unknown
