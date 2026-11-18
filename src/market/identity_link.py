"""The link of the players of an external source to the person of FEB (#885, D1; the D3c of #887).

A player of FIBA (and, later, of any source that carries a date of birth) is linked to a person of the FEB rosters when they have **the same date of birth AND at least two words of the name in common** (``MIN_SHARED``;
particles such as ``de la`` do not count) and there is a single candidate. The date alone corroborates nothing: measured on the real data 80 % of the foreigners share one with somebody in FEB by chance
(docs/evaluaciones/2026-11-18_enlace-fiba-feb.md), which is why ScoutingFEB's identity by name and FEB's by date are both refused here. Decided 18/11/2026:

* ``linked``: one person with the same birth and >= 2 words in common;
* ``review``: several persons fit, or the only fit has one word in common (the staff decides in the review queue, #895 onwards);
* nothing: a date of birth without a name in common never links.

Pure functions, no I/O. A person is its ``person_id`` (FEB rewrites the roster of every season: the same id in two rosters is one candidate) and the answer does not depend on the order of the inputs.
"""
from __future__ import annotations

import unicodedata
from typing import Any, Dict, Iterable, List, Set

MIN_SHARED = 2
METHOD = "birth+name"
_PARTICLES = frozenset({"DE", "DEL", "LA", "LAS", "LOS", "EL", "Y", "I", "DA", "DO", "DOS", "DAS", "DI", "VAN", "VON", "DER", "LE", "AL", "BEN", "BIN"})
_MAX_CANDIDATES = 5


def _words(name: Any) -> Set[str]:
    """The words of a name that identify a person: without accents, upper case, hyphens and dots as spaces, no initials and no particles."""
    text = "".join(c for c in unicodedata.normalize("NFKD", str(name or "").upper()) if not unicodedata.combining(c))
    return {w for w in text.replace("-", " ").replace(".", " ").split() if len(w) > 1 and w not in _PARTICLES}


def external_players(docs: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """The players with minutes of canonical documents with a bio (``birth``), once each, sorted by id: ``{id, name, birth, nationality}``."""
    found: Dict[str, Dict[str, Any]] = {}
    for doc in docs:
        for team in (doc.get("BOXSCORE") or {}).get("TEAM") or []:
            for player in team.get("PLAYER") or []:
                pid = str(player.get("id"))
                if pid not in found and player.get("birth") and player.get("name") and str(player.get("min") or "0") not in ("0", ""):
                    found[pid] = {"id": pid, "name": player["name"], "birth": player["birth"], "nationality": player.get("nationality")}
    return [found[k] for k in sorted(found)]


def _persons_by_birth(rows: Iterable[Dict[str, Any]]) -> Dict[str, Dict[str, Set[str]]]:
    """``{birth: {person_id: words of every name the person has been written with}}``."""
    out: Dict[str, Dict[str, Set[str]]] = {}
    for row in rows:
        if row.get("birth") and row.get("person_id"):
            out.setdefault(str(row["birth"]), {}).setdefault(str(row["person_id"]), set()).update(_words(row.get("name")))
    return out


def link_players(feb_rows: Iterable[Dict[str, Any]], players: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """The links of ``players`` to the persons of ``feb_rows`` (the roster rows of FEB: ``person_id``, ``name``, ``birth``), sorted by external id. A player with no candidate is not in the answer."""
    by_birth = _persons_by_birth(feb_rows)
    links: List[Dict[str, Any]] = []
    for player in sorted(players, key=lambda p: str(p["id"])):
        words = _words(player.get("name"))
        fits = []
        for person, theirs in sorted(by_birth.get(str(player.get("birth")), {}).items()):
            shared = sorted(words & theirs)
            if shared:
                fits.append({"feb": person, "shared": shared})
        strong = [f for f in fits if len(f["shared"]) >= MIN_SHARED]
        base = {"external": str(player["id"]), "method": METHOD, "birth": str(player["birth"])}
        if len(strong) == 1:
            links.append({**base, "status": "linked", "feb": strong[0]["feb"], "shared": strong[0]["shared"]})
        elif fits:
            links.append({**base, "status": "review", "feb": None, "shared": [], "candidates": sorted(fits, key=lambda f: (-len(f["shared"]), f["feb"]))[:_MAX_CANDIDATES]})
    return links
