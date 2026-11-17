"""The canonical format of the external sources (#884, D0 of epic #872).

ACB, FIBA and NCAA games are converted, at ingestion, to the FEB document, so that no pipeline forks (the lesson of ``is_fbcyl``). The conversion of each source is its own block (D2 to D4); this
module is the contract they all meet and what proves it:

* ``_league`` is the source of the game (``acb``, ``fiba``, ``ncaa``) and every id (game, team, player) carries its prefix, ``ncaa:401``: an id of another source can never be taken for a FEB one (FEB ids
  are digits, never prefixed) nor linked to a person by chance;
* the length of a game depends on the source: NCAA men play two halves of 20 minutes, the rest four quarters of 10, and every overtime is 5 minutes;
* ``validate_game`` lists what is wrong with a document, without changing it.

Pure functions, no I/O. The height and the position of a person are normalised by ``bio``.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from src.live_prep.competition_info import GENDERS
from src.services.competition_catalogue import EXTERNAL_LEAGUES

STARTTIME = "%d-%m-%Y - %H:%M"
OVERTIME_MINUTES = 5


def source_id(source: str, raw: Any) -> str:
    """``ncaa:401``: the id of a game, team or player of an external source. An id that already has the prefix of its source is kept; one with another source's prefix is refused, never rewritten."""
    if source not in EXTERNAL_LEAGUES:
        raise ValueError(f"unknown source {source!r} (one of {EXTERNAL_LEAGUES})")
    text = "" if raw is None else str(raw).strip()
    if not text:
        raise ValueError("an id cannot be empty")
    found = split_source_id(text)
    if found is None:
        if ":" in text:
            raise ValueError(f"{text!r} has a prefix that is not a source of {EXTERNAL_LEAGUES}")
        return f"{source}:{text}"
    if found[0] != source:
        raise ValueError(f"{text!r} is an id of {found[0]}, not of {source}")
    return text


def split_source_id(text: Any) -> Optional[Tuple[str, str]]:
    """``("ncaa", "401")`` for ``ncaa:401``; ``None`` for a FEB id (digits), for an unknown prefix and for an empty id."""
    if not isinstance(text, str) or ":" not in text:
        return None
    source, _, raw = text.partition(":")
    return (source, raw) if source in EXTERNAL_LEAGUES and raw.strip() else None


@dataclass(frozen=True)
class PeriodScheme:
    """The regulation of a game: ``periods`` of ``minutes`` each and then overtimes of ``overtime_minutes``."""
    periods: int
    minutes: int
    overtime_minutes: int = OVERTIME_MINUTES


def period_scheme(source: str, gender: str) -> PeriodScheme:
    """NCAA men: two halves of 20 minutes; NCAA women (four quarters since 2015-16), FIBA and ACB: four quarters of 10."""
    if source not in EXTERNAL_LEAGUES:
        raise ValueError(f"unknown source {source!r} (one of {EXTERNAL_LEAGUES})")
    if gender not in GENDERS:
        raise ValueError(f"gender must be one of {GENDERS}, not {gender!r}")
    return PeriodScheme(2, 20) if (source, gender) == ("ncaa", "M") else PeriodScheme(4, 10)


def game_minutes(source: str, gender: str, periods_played: int) -> int:
    """The minutes of a game that lasted ``periods_played`` periods (regulation plus its overtimes): 40 or 45, 50…"""
    scheme = period_scheme(source, gender)
    if periods_played < scheme.periods:
        raise ValueError(f"a {source} game of {gender} has at least {scheme.periods} periods, not {periods_played}")
    return scheme.periods * scheme.minutes + (periods_played - scheme.periods) * scheme.overtime_minutes


def _check_id(problems: List[str], what: str, value: Any, source: str) -> None:
    found = split_source_id(value)
    if found is None or found[0] != source:
        problems.append(f"{what} id {value!r} does not carry the prefix of {source}")


def _check_header(problems: List[str], header: Dict[str, Any], source: str) -> List[str]:
    """The header: the start time and two teams with prefixed ids, a name and a numeric score. Returns the ids of the teams."""
    try:
        datetime.strptime(str(header.get("starttime")), STARTTIME)
    except ValueError:
        problems.append(f"HEADER.starttime {header.get('starttime')!r} is not {STARTTIME}")
    teams = header.get("TEAM") or []
    if len(teams) != 2:
        problems.append(f"HEADER.TEAM must have 2 teams, it has {len(teams)}")
    ids = []
    for team in teams:
        _check_id(problems, "team", team.get("id"), source)
        ids.append(team.get("id"))
        if not str(team.get("name") or "").strip():
            problems.append(f"team {team.get('id')!r} has no name")
        if not str(team.get("pts") if team.get("pts") is not None else "").strip().isdigit():
            problems.append(f"team {team.get('id')!r} pts {team.get('pts')!r} is not a number")
    return ids


def _check_lines(problems: List[str], doc: Dict[str, Any], source: str) -> None:
    """The team and the player of each play-by-play line carry the prefix too: without it nothing would be counted for that team (a reconciliation would see zeros) and no player could be linked."""
    bad: Dict[str, set] = {"idTeam": set(), "idPlayer": set()}
    for line in (doc.get("PLAYBYPLAY") or {}).get("LINES") or []:
        for key in bad:
            value = line.get(key)
            if value not in (None, "") and (split_source_id(value) or ("",))[0] != source:
                bad[key].add(str(value))
    for key, values in bad.items():
        if values:
            problems.append(f"play-by-play {key} {sorted(values)[:3]} does not carry the prefix of {source}")


def validate_game(doc: Dict[str, Any], gender: str) -> List[str]:
    """What is wrong with a canonical document of an external source (an empty list when it is fine). It does not change the document and gives the same answer every time."""
    if gender not in GENDERS:
        raise ValueError(f"gender must be one of {GENDERS}, not {gender!r}")
    problems: List[str] = []
    source = doc.get("_league")
    if source not in EXTERNAL_LEAGUES:
        return [f"_league must be one of {EXTERNAL_LEAGUES}, not {source!r}"]
    _check_id(problems, "game", doc.get("_id"), source)
    header = doc.get("HEADER") or {}
    header_ids = _check_header(problems, header, source)
    box = (doc.get("BOXSCORE") or {}).get("TEAM") or []
    for team in box:
        _check_id(problems, "box team", team.get("id"), source)
        if team.get("id") not in header_ids:
            problems.append(f"box team {team.get('id')!r} is not a team of the header")
        for player in team.get("PLAYER") or []:
            _check_id(problems, "player", player.get("id"), source)
    _check_lines(problems, doc, source)
    periods = len((header.get("QUARTERS") or {}).get("QUARTER") or [])
    regulation = period_scheme(source, gender).periods
    if periods < regulation:
        problems.append(f"periods: {periods} played, a {source} game of {gender} has at least {regulation}")
    return problems
