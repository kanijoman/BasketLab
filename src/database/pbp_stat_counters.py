"""What the IN/OUT and the lineup calculators write to: the bucket of counters and the few ways of bumping it (issue #200, block 6 of #452).

A bucket holds the stats of a team and, prefixed ``opp_``, those of its rival, plus the points for and against. The two calculators read the same
play-by-play with rules that differ in small ways (which words count as a miss, which sources count a steal), so the RULES stay in each calculator;
what is shared is the bookkeeping, which they used to write out as an ``if is_team … else …`` pair for every counter.
"""
from typing import Dict, Iterable, Optional, Tuple, TypeVar

STAT_KEYS = ('fgm_2', 'fga_2', 'fgm_3', 'fga_3', 'ftm', 'fta', 'orb', 'drb', 'ast', 'stl', 'blk', 'tov', 'pf')

_SHOT_KEYS = {2: ('fga_2', 'fgm_2'), 3: ('fga_3', 'fgm_3'), 1: ('fta', 'ftm')}   # points of the shot → (attempts, makes)

T = TypeVar('T')


def empty_stats() -> Dict[str, int]:
    """A new bucket with every counter at zero."""
    stats = {'points_for': 0, 'points_against': 0}
    stats.update({key: 0 for key in STAT_KEYS})
    stats.update({f'opp_{key}': 0 for key in STAT_KEYS})
    return stats


def bump(stats: Dict[str, int], key: str, is_team: bool) -> None:
    """Add one to ``key`` of the team, or of its rival (``opp_`` + key)."""
    stats[key if is_team else f'opp_{key}'] += 1


def count_shot(stats: Dict[str, int], points: int, made: bool, is_team: bool) -> None:
    """A shot of 1, 2 or 3 points: always an attempt, and a make when it went in."""
    attempts, makes = _SHOT_KEYS[points]
    bump(stats, attempts, is_team)
    if made:
        bump(stats, makes, is_team)


def count_rebound(stats: Dict[str, int], offensive: bool, is_team: bool) -> None:
    bump(stats, 'orb' if offensive else 'drb', is_team)


def add_points(stats: Dict[str, int], points: int, is_team: bool) -> None:
    if points > 0:
        stats['points_for' if is_team else 'points_against'] += points


def first_match(text: str, table: Iterable[Tuple[Tuple[str, ...], T]]) -> Optional[T]:
    """The value of the first row of ``table`` with any of its phrases in ``text`` (rows are tried in order, like an ``elif`` chain)."""
    for phrases, value in table:
        if any(phrase in text for phrase in phrases):
            return value
    return None
