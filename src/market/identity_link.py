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

import re
import unicodedata
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

MIN_SHARED = 2
METHOD = "birth+name"
_PARTICLES = frozenset({"DE", "DEL", "LA", "LAS", "LOS", "EL", "Y", "I", "DA", "DO", "DOS", "DAS", "DI", "VAN", "VON", "DER", "LE", "AL", "BEN", "BIN"})
_MAX_CANDIDATES = 5


def _words(name: Any) -> Set[str]:
    """The words of a name that identify a person: without accents, upper case, hyphens and dots as spaces, no initials and no particles."""
    text = "".join(c for c in unicodedata.normalize("NFKD", str(name or "").upper()) if not unicodedata.combining(c))
    return {w for w in text.replace("-", " ").replace(".", " ").split() if len(w) > 1 and w not in _PARTICLES}


def external_players(docs: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """The players with minutes of canonical documents with a bio (``birth``), once each, sorted by id: ``{id, name, birth, nationality}`` and, where the source has it, ``full_name`` (ACB shows the name a player
    is known by and says the one of his papers, which is how FEB writes him: the link has the words of both, #886)."""
    found: Dict[str, Dict[str, Any]] = {}
    for doc in docs:
        for team in (doc.get("BOXSCORE") or {}).get("TEAM") or []:
            for player in team.get("PLAYER") or []:
                pid = str(player.get("id"))
                if pid not in found and player.get("birth") and player.get("name") and str(player.get("min") or "0") not in ("0", ""):
                    found[pid] = {"id": pid, "name": player["name"], "birth": player["birth"], "nationality": player.get("nationality"), **({"full_name": player["full_name"]} if player.get("full_name") else {})}
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
        words = _words(player.get("name")) | _words(player.get("full_name"))
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


# --- FBCYL <-> FEB (#978) ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
# FBCYL has no date of birth: the name key finds the candidates, the sex and the category of the player discard those that cannot be her, and the club or the full name with a birth that fits corroborates the
# only one left. Measured on the whole archive (docs/evaluaciones/2026-11-18_enlace-fiba-feb.md).
_GENERIC_CLUB_WORDS = frozenset({"CB", "CD", "AD", "BC", "CLUB", "BALONCESTO", "BASKET", "BASQUET", "BASKETBALL", "ESCUELA", "DEPORTIVO", "DEPORTIVA", "ASOCIACION", "SDC", "SD", "UD", "CAD", "JR", "FEM", "MASC", "FEMENINO", "MASCULINO"})
CLUB_MIN_SHARED = 2                                    # words of the club in common that corroborate (or every distinctive word of one of the two names)
AGE_LIMITS = {"U12": 12, "U14": 14, "U16": 16, "U18": 18}        # a U16 of the season that starts in S was born in S-15 or later (FEB's cadete championships: 14 or 15 years old); one year of tolerance
SENIOR_MIN_AGE = 13
CLUB_METHOD, BIRTH_METHOD, REVIEW_METHOD = "name+club", "name+birth", "name"


def _plain(text: Any) -> List[str]:
    """Upper case words without accents; every sign that is not a letter or a digit (dots, hyphens, quotes, commas) separates words."""
    stripped = "".join(c for c in unicodedata.normalize("NFKD", str(text or "").upper()) if not unicodedata.combining(c))
    return "".join(c if c.isalnum() else " " for c in stripped).split()


def _name_words(name: Any) -> List[str]:
    """The words of a person's name without the marks FBCYL writes before it in brackets (``(REF)``, ``(JUN)``)."""
    return _plain(re.sub(r"\([^)]*\)", " ", str(name or "")))


def name_key(name: Any) -> Optional[Tuple[str, Tuple[str, ...]]]:
    """``(initial, surnames)`` of ``V. IBAÑEZ BARREIRO`` or ``VIRGINIA IBAÑEZ BARREIRO`` (the two ways the leagues write a player), the same for both: the first word is the given name (its initial is kept) and the rest
    are the surnames, in their order (both federations write them the same way) and without particles. ``None`` with fewer than two words."""
    words = _name_words(name)
    if len(words) < 2:
        return None
    surnames = tuple(w for w in words[1:] if len(w) > 1 and w not in _PARTICLES)
    return (words[0][0], surnames) if surnames else None


def _full(name: Any) -> Optional[Tuple[str, ...]]:
    """The full name (given names and surnames, no particles) of a name written in full; ``None`` for ``V. SURNAME``."""
    words = _name_words(name)
    return tuple(w for w in words if w not in _PARTICLES) if len(words) >= 2 and len(words[0]) > 1 else None


def club_words(club: Any) -> Set[str]:
    """The words of a club name that identify it: no initials (``C.D.``), no particles and none of the words every club has (``BALONCESTO``, ``CLUB``...)."""
    return {w for w in _plain(club) if len(w) > 1 and w not in _PARTICLES and w not in _GENERIC_CLUB_WORDS}


def _club_match(mine: Iterable[str], theirs: Iterable[str]) -> List[str]:
    """The words that corroborate the club, of the pair of clubs with most: ``CLUB_MIN_SHARED`` in common, or every distinctive word of one of the two names in the other (``BALONCESTO LA FLECHA``); empty if none."""
    best: Set[str] = set()
    for a in map(club_words, mine):
        for b in map(club_words, theirs):
            shared = a & b
            if shared and (len(shared) >= CLUB_MIN_SHARED or shared in (a, b)) and len(shared) > len(best):
                best = shared
    return sorted(best)


def fbcyl_age_groups(catalogue: Iterable[Dict[str, Any]]) -> Dict[str, str]:
    """``{competition_id: U16 | U18 | senior}`` of the FBCYL entries of the catalogue: the age group of a ``formacion`` one and ``senior`` for the rest (Primera Nacional has no category)."""
    out = {}
    for entry in catalogue:
        fbcyl = entry.get("fbcyl") if entry.get("league") == "fbcyl" else None
        if isinstance(fbcyl, dict) and fbcyl.get("competition_id"):
            group = entry.get("age_group") if entry.get("category") == "formacion" else "senior"
            if group:
                out[str(fbcyl["competition_id"])] = group
    return out


def feb_genders(catalogue: Iterable[Dict[str, Any]]) -> Dict[str, str]:
    """``{competition: F | M}`` of the FEB entries of the catalogue (the ``_competition`` of their games)."""
    return {e["competition"]: e["gender"] for e in catalogue if e.get("league", "feb") == "feb" and e.get("gender") in ("F", "M")}


def _unwrapped(value: Any) -> Any:
    return next(iter(value.values())) if isinstance(value, dict) and value else value


def _season(value: Any) -> Optional[int]:
    text = str(_unwrapped(value) or "")
    return int(text) if text.isdigit() else None


def fbcyl_players(docs: Iterable[Dict[str, Any]], age_groups: Optional[Dict[str, str]] = None) -> List[Dict[str, Any]]:
    """The persons of FBCYL games (``stats.teams[].players[]``), one per ``uuid`` (the ``actorId`` changes in every game), sorted by id: ``{id: fbcyl:<uuid>, uuid, name, names, clubs, genders, age_groups,
    seasons}`` over every game (``age_groups``: ``fbcyl_age_groups`` of the catalogue). A player without ``uuid`` is left out."""
    found: Dict[str, Dict[str, Set[Any]]] = {}
    for doc in docs:
        group, season, gender = (age_groups or {}).get(str(_unwrapped(doc.get("_competition")))), _season(doc.get("_season")), doc.get("_gender")
        for team in ((doc.get("stats") or {}).get("teams")) or []:
            for player in team.get("players") or []:
                if not player.get("uuid") or not player.get("name"):
                    continue
                person = found.setdefault(str(player["uuid"]), {"names": set(), "clubs": set(), "genders": set(), "age_groups": set(), "seasons": set()})
                person["names"].add(" ".join(str(player["name"]).split()))
                for key, value in (("clubs", str(team.get("name") or "").strip()), ("genders", gender if gender in ("F", "M") else None), ("age_groups", group), ("seasons", season)):
                    if value:
                        person[key].add(value)
    return [{"id": f"fbcyl:{uuid}", "uuid": uuid, "name": sorted(p["names"])[0], **{k: sorted(v) for k, v in p.items()}} for uuid, p in sorted(found.items())]


def feb_persons(games: Iterable[Dict[str, Any]], rosters: Iterable[Dict[str, Any]] = (), genders: Optional[Dict[str, str]] = None) -> Dict[str, Dict[str, List[str]]]:
    """``{feb:<idPlayer>: {names, full_names, clubs, genders, births}}``: every spelling of the name and every club (``HEADER.TEAM[].name``) of the FEB boxes, the sex of their competitions (``feb_genders``) and
    the full name and date of birth of the FEB rosters (``run_roster_sweep.py``)."""
    persons: Dict[str, Dict[str, Set[str]]] = {}

    def person(pid: str) -> Dict[str, Set[str]]:
        return persons.setdefault(pid, {"names": set(), "full_names": set(), "clubs": set(), "genders": set(), "births": set()})

    for game in games:
        gender = (genders or {}).get(str(game.get("_competition") or ""))
        clubs = {str(t.get("id")): str(t.get("name") or "").strip() for t in (game.get("HEADER") or {}).get("TEAM") or []}
        for team in (game.get("BOXSCORE") or {}).get("TEAM") or []:
            for player in team.get("PLAYER") or []:
                if player.get("id") and player.get("name"):
                    data = person(f"feb:{player['id']}")
                    data["names"].add(str(player["name"]).strip())
                    for key, value in (("clubs", clubs.get(str(team.get("id")))), ("genders", gender)):
                        if value:
                            data[key].add(value)
    for row in rosters:
        if row.get("person_id"):
            data = person(str(row["person_id"]))
            for key, value in (("full_names", row.get("name")), ("births", row.get("birth"))):
                if value:
                    data[key].add(str(value))
    return {pid: {k: sorted(v) for k, v in data.items()} for pid, data in sorted(persons.items())}


def _age_fits(player: Dict[str, Any], births: Iterable[str]) -> Optional[bool]:
    """Whether a birth of the FEB person fits a category the player plays in a season (``None`` when the birth or the category is unknown): a youth category has an upper age by regulation, a senior one a minimum."""
    years = {int(b[:4]) for b in births if str(b)[:4].isdigit()}
    checks = [(group, season) for group in player.get("age_groups", []) for season in player.get("seasons", []) if group in AGE_LIMITS or group == "senior"]
    if not years or not checks:
        return None
    return any(any(y >= s - AGE_LIMITS[g] for y in years) if g in AGE_LIMITS else any(y <= s - SENIOR_MIN_AGE for y in years) for g, s in checks)


def _could_be(player: Dict[str, Any], person: Dict[str, List[str]]) -> bool:
    """The same sex (when both are known) and a birth that does not rule out the category of the player."""
    mine, theirs = set(player.get("genders", [])), set(person.get("genders", []))
    return (not mine or not theirs or bool(mine & theirs)) and _age_fits(player, person.get("births", [])) is not False


def _index(persons: Dict[str, Dict[str, List[str]]]) -> Dict[str, Any]:
    """The persons by name key, by the last two surnames (for a compound given name), by full name, and the full names FEB gives to persons with different dates of birth (homonyms: no evidence)."""
    index: Dict[str, Any] = {"key": {}, "suffix": {}, "full": {}}
    births: Dict[Tuple[str, ...], Set[str]] = {}
    for pid, data in persons.items():
        for name in [*data["names"], *data["full_names"]]:
            key = name_key(name)
            if key:
                index["key"].setdefault(key, set()).add(pid)
                if len(key[1]) >= 2:
                    index["suffix"].setdefault((key[0], key[1][-2:]), set()).add(pid)
        for full in filter(None, map(_full, data["full_names"])):
            index["full"].setdefault(full, set()).add(pid)
            births.setdefault(full, set()).update(data["births"])
    index["homonyms"] = {full for full, dates in births.items() if len(dates) > 1}
    return index


def _candidates(player: Dict[str, Any], index: Dict[str, Any]) -> Set[str]:
    found: Set[str] = set()
    for name in player.get("names") or [player.get("name")]:
        key, full = name_key(name), _full(name)
        if key:
            found |= index["key"].get(key, set())
            if len(key[1]) >= 3:                                              # FBCYL MARIA JOSE GARCIA LOPEZ is FEB's M. GARCIA LOPEZ
                found |= index["suffix"].get((key[0], key[1][-2:]), set())
        if full:
            found |= index["full"].get(full, set())
    return found


def _evidence(player: Dict[str, Any], person: Dict[str, List[str]], homonyms: Set[Tuple[str, ...]]) -> Optional[Tuple[str, List[str]]]:
    """What corroborates the only candidate: its club, or its full name (not one FEB repeats) with a birth that fits the category of the player."""
    shared = _club_match(player.get("clubs", []), person.get("clubs", []))
    if shared:
        return CLUB_METHOD, shared
    same = sorted(({_full(n) for n in player.get("names", [])} & {_full(n) for n in person.get("full_names", [])}) - homonyms - {None})
    return (BIRTH_METHOD, list(same[0])) if same and _age_fits(player, person.get("births", [])) else None


def link_fbcyl(persons: Dict[str, Dict[str, List[str]]], players: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """The links of FBCYL ``players`` (``fbcyl_players``) to FEB ``persons`` (``feb_persons``), sorted by external id. ``linked``: a single candidate that could be her (sex, category) and is corroborated by the
    club (``name+club``) or by the full name and the birth (``name+birth``). ``review``: several candidates, or one without evidence. A player with no candidate is not in the answer."""
    index = _index(persons)
    links: List[Dict[str, Any]] = []
    for player in sorted(players, key=lambda p: str(p["id"])):
        fits = sorted(c for c in _candidates(player, index) if _could_be(player, persons[c]))
        if not fits:
            continue
        evidence = _evidence(player, persons[fits[0]], index["homonyms"]) if len(fits) == 1 else None
        if evidence:
            links.append({"external": str(player["id"]), "status": "linked", "feb": fits[0], "method": evidence[0], "shared": evidence[1]})
        else:
            candidates = [{"feb": c, "shared": _club_match(player.get("clubs", []), persons[c].get("clubs", []))} for c in fits]
            links.append({"external": str(player["id"]), "status": "review", "feb": None, "method": REVIEW_METHOD, "shared": [], "candidates": candidates[:_MAX_CANDIDATES]})
    return links
