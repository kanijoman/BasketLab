"""Packages of every match of the next round of a competition, in one compressed bundle (issues #286, #172).

One pass over the games of a competition feeds ONE ``SeasonAccumulator`` that tracks every team of the round, and each match gets its
package from it (``to_package`` changes nothing): the cost does not grow with the number of matches. Every match has a package from EACH of
its two teams, so any club can follow it; the default one comes first (the club's when it plays the match, the home team's otherwise). The packages of a round travel in one envelope (a single key derivation) with the
JSON compressed before it is encrypted; the index lists the bundles with a summary of their matches (no package inside), so the app lists
them without downloading anything.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence

from src.live_core.package import PreparationPackage

from .package_builder import SeasonAccumulator
from .package_sealing import as_sealer

ROUND_BUNDLE_VERSION = 1
ROUNDS_DIR = "rounds"

RosterSource = Callable[[Sequence[str]], Optional[Dict[str, Dict[str, Any]]]]


def round_file_name(collection: str, round_index: Any) -> str:
    return f"{ROUNDS_DIR}/{re.sub(r'[^A-Za-z0-9]+', '_', collection).strip('_')}__r{round_index}.bpkgz"


def _team_ids(matches: Iterable[Dict[str, Any]]) -> List[str]:
    return list(dict.fromkeys(str(m[side]["id"]) for m in matches for side in ("home", "away")))


def _perspectives(match: Dict[str, Any], club_team_id: Optional[str]) -> List[tuple]:
    """``[(own id, rival id), ...]``, the default one first: the club's when it plays the match, else the home team's."""
    home, away = str(match["home"]["id"]), str(match["away"]["id"])
    if club_team_id and str(club_team_id) == away:
        return [(away, home), (home, away)]
    return [(home, away), (away, home)]


class _Rosters:
    """The roster of each team asked once, however many matches it plays; a team that fails simply has none (issue #271)."""

    def __init__(self, source: Optional[RosterSource]) -> None:
        self._source, self._cache = source, {}

    def of(self, team_id: str) -> Optional[Dict[str, Dict[str, Any]]]:
        if self._source is None:
            return None
        if team_id not in self._cache:
            try:
                self._cache[team_id] = self._source([team_id]) or None
            except Exception:  # noqa: BLE001 - FEB's website must never stop a package
                self._cache[team_id] = None
        return self._cache[team_id]

    def both(self, own: str, rival: str) -> Optional[Dict[str, Dict[str, Any]]]:
        merged = {**(self.of(own) or {}), **(self.of(rival) or {})}
        return merged or None


def build_round_packages(
    games: Iterable[Dict[str, Any]], collection: str, season: str, matches: List[Dict[str, Any]],
    club_team_id: Optional[str] = None, created_at: Optional[str] = None, roster_source: Optional[RosterSource] = None,
    rule_config: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """``[{match, own_id, rival_id, is_club, default, package}]``, two per match (one from each team), from a single pass over ``games``."""
    acc = SeasonAccumulator(track=_team_ids(matches))
    for game in games:
        acc.add_game(game)
    rosters, built = _Rosters(roster_source), []
    for match in matches:
        meta = {k: match[k] for k in ("code", "start", "round", "home", "away")}
        plays = bool(club_team_id) and str(club_team_id) in (str(match["home"]["id"]), str(match["away"]["id"]))
        for i, (own, rival) in enumerate(_perspectives(match, club_team_id)):
            package = acc.to_package(collection, season, own, rival, {"match": meta}, created_at, roster=rosters.both(own, rival), rule_config=rule_config)
            built.append({"match": meta, "own_id": own, "rival_id": rival, "package": package, "is_club": plays, "default": i == 0})
    return built


def build_round_packages_from_db(handler: Any, collection: str, matches: List[Dict[str, Any]], club_team_id: Optional[str] = None,
                                 roster_source: Optional[RosterSource] = None, season: Optional[str] = None,
                                 rule_config: Optional[Dict[str, Any]] = None, level_of: Optional[Callable[[str], Optional[int]]] = None) -> List[Dict[str, Any]]:
    """``handler`` is a MongoDBHandler; the games are read one at a time (a game document is ~1 MB in memory)."""
    from .db_source import _counted, catalog_level_of, season_of
    from .game_sources import games_of_sources, source_collections

    mongo = handler.repository.connection.get_collection(collection)
    team_ids = _team_ids(matches)
    sources = source_collections(handler, collection, team_ids)    # the own collection + the other games of the teams of the round (#456)
    games = _counted(games_of_sources(handler, sources, team_ids, level_of or catalog_level_of(handler)), 0, None)
    return build_round_packages(games, collection, season or season_of(mongo, collection), matches, club_team_id,
                                roster_source=roster_source, rule_config=rule_config)


def _summary(built: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """One line per match: its default side (``own_id``) and every side that has a package (``own_ids``, the default one first)."""
    lines: Dict[str, Dict[str, Any]] = {}
    for b in built:
        code = b["match"]["code"]
        line = lines.setdefault(code, {"code": code, "start": b["match"]["start"], "home": b["match"]["home"], "away": b["match"]["away"],
                                       "own_id": b["own_id"], "is_club": b["is_club"], "own_ids": []})
        line["own_ids"].append(b["own_id"])
    return list(lines.values())


def bundle_plaintext(collection: str, round_index: Any, built: List[Dict[str, Any]]) -> str:
    """The JSON inside the envelope: the packages (as text, with their own checksum) and who each one is for."""
    return json.dumps({
        "v": ROUND_BUNDLE_VERSION, "collection": collection, "round": round_index,
        "matches": [{"match": b["match"], "own_id": b["own_id"], "rival_id": b["rival_id"], "is_club": b["is_club"],
                     "package": b["package"].dumps()} for b in built],      # an app that predates both sides finds the first one of a match: the default
    }, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def publish_rounds(out: Any, passphrase: Any, collection: str, round_index: Any, built: List[Dict[str, Any]],
                   club_team_id: Optional[str] = None, competition: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Write the bundle of a round and return its entry for the index (a summary of the matches, no packages)."""
    out = Path(out)
    file = round_file_name(collection, round_index)
    scopes = ([f"club:{club_team_id}"] if club_team_id else []) + [f"competicion:{collection}"]
    envelope, extra = as_sealer(passphrase).seal(bundle_plaintext(collection, round_index, built), scopes, compress=True)
    content = json.dumps(envelope, separators=(",", ":"))
    (out / ROUNDS_DIR).mkdir(parents=True, exist_ok=True)
    (out / file).write_text(content, encoding="utf-8")
    raw = content.encode("utf-8")
    return {
        "collection": collection, "round": round_index, "file": file, "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw),
        "club": any(b["is_club"] for b in built),
        "matches": _summary(built), **extra,
        **({"competition": competition} if competition else {}),
    }
