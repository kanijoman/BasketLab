"""The normalised events of a game document (FEB lines or FBCYL moves), shared by the pbp modules."""
from __future__ import annotations

from typing import Dict, List

from src.live_core.events import Event, parse_line
from src.live_core.events_fbcyl import parse_moves

from .period_scheme import scheme_of


def game_events(game_data: Dict, is_fbcyl: bool) -> List[Event]:
    """Events in the order of the document (the consumers sort them by clock)."""
    if is_fbcyl:
        return parse_moves(game_data.get("moves") or [])
    lines = (game_data.get("PLAYBYPLAY") or {}).get("LINES") or []
    # the real feed always has a line number; without one the position in the list is the order
    numbered = [line if line.get("num") not in (None, "") else {**line, "num": str(i + 1)} for i, line in enumerate(lines)]
    numbered = _without_repeats(numbered)
    scheme = scheme_of(game_data)
    return [e for e in (parse_line(line, scheme) for line in numbered) if e is not None]


def _without_repeats(lines: List[Dict]) -> List[Dict]:
    """Drop the lines the feed repeats verbatim (game 2536129: same number, same second): they would be counted twice.
    Same number with different content is a correction of the feed and both lines stay."""
    seen, kept = set(), []
    for line in lines:
        key = tuple(sorted((k, str(v)) for k, v in line.items()))
        if key not in seen:
            seen.add(key)
            kept.append(line)
    return kept
