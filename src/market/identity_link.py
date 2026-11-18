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
from typing import Any, Dict, FrozenSet, Iterable, List, Optional, Set, Tuple

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


# --- FBCYL <-> FEB (#978): FBCYL carries no date of birth, so the link is by name key and club ---------------------------------------------------------------------------------------------------------------
_GENERIC_CLUB_WORDS = frozenset({"CB", "CD", "AD", "BC", "CLUB", "BALONCESTO", "BASKET", "BASQUET", "BASKETBALL", "ESCUELA", "DEPORTIVO", "DEPORTIVA", "ASOCIACION", "SDC", "SD", "UD", "CAD", "JR", "FEM", "MASC", "FEMENINO", "MASCULINO"})
CLUB_MIN_SHARED = 2                                    # words of the club in common that corroborate a person with the same name key
FBCYL_METHOD = "name+club"


def _plain(text: Any) -> List[str]:
    stripped = "".join(c for c in unicodedata.normalize("NFKD", str(text or "").upper()) if not unicodedata.combining(c))
    return stripped.replace("-", " ").replace(".", " ").replace(",", " ").split()


def name_key(name: Any) -> Optional[Tuple[str, FrozenSet[str]]]:
    """``(initial, surnames)`` of ``V. IBAÑEZ BARREIRO`` or ``VIRGINIA IBAÑEZ BARREIRO`` (the two ways the leagues write a player), the same for both: the first word is the given name (its initial is kept) and the rest
    are the surnames, without particles. A given name with several words (``MARIA JOSE``) gives another key than FEB's initial form: a link missed, never a wrong one. ``None`` with fewer than two words."""
    words = _plain(name)
    if len(words) < 2:
        return None
    surnames = frozenset(w for w in words[1:] if len(w) > 1 and w not in _PARTICLES)
    return (words[0][0], surnames) if surnames else None


def club_words(club: Any) -> Set[str]:
    """The words of a club name that identify it: no initials (``C.D.``), no particles and none of the words every club has (``BALONCESTO``, ``CLUB``...)."""
    return {w for w in _plain(club) if len(w) > 1 and w not in _PARTICLES and w not in _GENERIC_CLUB_WORDS}


def _unwrapped(value: Any) -> Any:
    return next(iter(value.values())) if isinstance(value, dict) and value else value


def fbcyl_players(docs: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """The players of FBCYL games (``stats.teams[].players[]``) once each, sorted by id: ``{id: fbcyl:<actorId>, name, team (the club), season, gender}``."""
    found: Dict[str, Dict[str, Any]] = {}
    for doc in docs:
        for team in ((doc.get("stats") or {}).get("teams")) or []:
            for player in team.get("players") or []:
                actor = _unwrapped(player.get("actorId"))
                if actor in (None, "") or not player.get("name"):
                    continue
                found.setdefault(f"fbcyl:{actor}", {"id": f"fbcyl:{actor}", "name": player["name"], "team": team.get("name") or "", "season": doc.get("_season"), "gender": doc.get("_gender")})
    return [found[k] for k in sorted(found)]


def feb_persons(games: Iterable[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """``{feb:<idPlayer>: {names, clubs}}`` of the FEB boxes: every spelling of the name and every club (``HEADER.TEAM[].name``) the person has been in."""
    persons: Dict[str, Dict[str, Any]] = {}
    for game in games:
        clubs = {str(t.get("id")): str(t.get("name") or "").strip() for t in (game.get("HEADER") or {}).get("TEAM") or []}
        for team in (game.get("BOXSCORE") or {}).get("TEAM") or []:
            for player in team.get("PLAYER") or []:
                if player.get("id") and player.get("name"):
                    person = persons.setdefault(f"feb:{player['id']}", {"names": set(), "clubs": set()})
                    person["names"].add(str(player["name"]))
                    if clubs.get(str(team.get("id"))):
                        person["clubs"].add(clubs[str(team.get("id"))])
    return dict(sorted(persons.items()))


def link_fbcyl(persons: Dict[str, Dict[str, Any]], players: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """The links of FBCYL ``players`` to the FEB ``persons``, sorted by external id. ``linked``: a single person has the name key AND a club with at least ``CLUB_MIN_SHARED`` words in common with the club of the
    player. ``review``: the key has several persons, or one without the club. A key nobody has is not in the answer."""
    by_key: Dict[Tuple[str, FrozenSet[str]], List[str]] = {}
    for person, data in persons.items():
        for key in {k for k in (name_key(n) for n in data["names"]) if k}:
            by_key.setdefault(key, []).append(person)
    links: List[Dict[str, Any]] = []
    for player in sorted(players, key=lambda p: str(p["id"])):
        key = name_key(player.get("name"))
        candidates = sorted(by_key.get(key, [])) if key else []
        if not candidates:
            continue
        mine = club_words(player.get("team"))
        fits = [{"feb": c, "shared": sorted(max((mine & club_words(club) for club in persons[c]["clubs"]), key=len, default=set()))} for c in candidates]
        base = {"external": str(player["id"]), "method": FBCYL_METHOD}
        if len(fits) == 1 and len(fits[0]["shared"]) >= CLUB_MIN_SHARED:
            links.append({**base, "status": "linked", "feb": fits[0]["feb"], "shared": fits[0]["shared"]})
        else:
            links.append({**base, "status": "review", "feb": None, "shared": [], "candidates": fits[:_MAX_CANDIDATES]})
    return links
