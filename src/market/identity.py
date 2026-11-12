"""Person registry of Mercado (#873): one ``person_id`` per FEB ``idPlayer``, never merged by name.

Measured on the archive seed (1,833 FEB games, 2,158 ids): the id is stable across competitions and seasons (1,188 ids appear in
more than one collection) and only 13 ids carry more than one spelling of the name. That is why the person is anchored to the id
and the name is only an attribute: ScoutingFEB merged namesakes by exact name (``consolidate_identities.py``).

Input is any iterable of FEB game documents (``BOXSCORE.TEAM[].PLAYER[]``), read as a stream. Output is deterministic: it does not
depend on the order of the games.
"""
from __future__ import annotations

import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Set

PREFIX = "feb:"


def _strip(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", text.upper()) if not unicodedata.combining(c))


def name_key(name: str) -> str:
    """FEB writes ``X. SURNAME1 SURNAME2``: the key is the surnames, without accents, upper case and without the initial."""
    words = _strip(name or "").replace(".", " ").split()
    if words and len(words[0]) == 1:
        words = words[1:]
    return " ".join(words)


@dataclass
class Person:
    feb_id: str
    names: Counter = field(default_factory=Counter)             # raw name -> games
    teams: Set[str] = field(default_factory=set)                # team ids over the whole career
    collections: Set[str] = field(default_factory=set)
    games_by_collection: Counter = field(default_factory=Counter)
    games: Set[str] = field(default_factory=set)

    @property
    def person_id(self) -> str:
        return PREFIX + self.feb_id

    @property
    def display_name(self) -> str:
        """The most used spelling (ties: alphabetical), so the order of the games does not change it."""
        return min(self.names.items(), key=lambda kv: (-kv[1], kv[0]))[0] if self.names else ""


def _game_id(game: Dict[str, Any]) -> str:
    raw = game.get("_id")
    if isinstance(raw, dict):
        raw = next(iter(raw.values()), "")
    return str(raw)


def build_registry(games: Iterable[Dict[str, Any]]) -> Dict[str, Person]:
    registry: Dict[str, Person] = {}
    for game in games:
        gid = _game_id(game)
        collection = str(game.get("_collection") or game.get("_competition") or "")
        for team in (game.get("BOXSCORE") or {}).get("TEAM", []) or []:
            for player in team.get("PLAYER", []) or []:
                if not player.get("id"):
                    continue
                person = registry.setdefault(PREFIX + str(player["id"]), Person(str(player["id"])))
                if gid in person.games:
                    continue
                person.games.add(gid)
                person.names[str(player.get("name") or "")] += 1
                if team.get("id"):
                    person.teams.add(str(team["id"]))
                person.collections.add(collection)
                person.games_by_collection[collection] += 1
    return dict(sorted(registry.items()))


def _tokens(key: str) -> Set[str]:
    return {t for t in re.split(r"[\s\-]+", key) if t and t != "I"}


def name_conflicts(registry: Dict[str, Person]) -> List[str]:
    """Ids with spellings that share no surname word (a typo or a real surname change): they go to the review queue. A shortened or
    reordered spelling that keeps one surname (``COSTA VAZQUEZ`` / ``COSTA I VAZQUEZ``) is not a conflict."""
    out = []
    for person_id, person in registry.items():
        token_sets = [_tokens(name_key(n)) for n in person.names]
        if len(token_sets) > 1 and not set.intersection(*token_sets):
            out.append(person_id)
    return out
