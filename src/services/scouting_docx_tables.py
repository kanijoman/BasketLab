"""The tables of a player's page of the individual scouting, as data (#717, 17b).

What each table says (columns, text of the cells, quartile fill) is decided here and not while python-docx draws it, so the browser, which makes the same document, can be held to the
very same rules by vectors (``tests/local_vectors/scouting_docx_vectors.py``). The fills are the Excel-like tones the document always used.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from src.services._scouting_docx_helpers import quartile_fill
from src.services._scouting_formatters import fmt_min, safe

# (header, key, kind, reversed): kind is "min" (MM:SS), "pct" (one decimal and %) or "num"; reversed: a lower value is better (turnovers, fouls, defensive rating)
AVERAGES: List[Tuple[str, str, str, bool]] = [
    ("PJ", "games_played", "num", False), ("MIN", "minutes_per_game", "min", False), ("PTS", "points_per_game", "num", False),
    ("TL%", "fg1_percentage", "pct", False), ("T2%", "fg2_percentage", "pct", False), ("T3%", "fg3_percentage", "pct", False),
    ("RO", "offensive_rebounds_per_game", "num", False), ("RD", "defensive_rebounds_per_game", "num", False), ("RT", "rebounds_per_game", "num", False),
    ("AST", "assists_per_game", "num", False), ("ROB", "steals_per_game", "num", False), ("BP", "turnovers_per_game", "num", True),
    ("TAP", "blocks_per_game", "num", False), ("FP", "fouls_per_game", "num", True), ("VAL", "valoracion_per_game", "num", False),
]
ADVANCED: List[Tuple[str, str, str, bool]] = [
    ("TS%", "true_shooting", "pct", False), ("eFG%", "efg_percentage", "pct", False), ("3PAr", "three_point_rate", "pct", False), ("FTr", "free_throw_rate", "pct", False),
    ("ORB%", "orb_pct", "pct", False), ("DRB%", "drb_pct", "pct", False), ("AST%", "ast_pct", "pct", False), ("TO%", "tov_pct_adv", "pct", True),
    ("ROB%", "stl_pct", "pct", False), ("TAP%", "blk_pct", "pct", False), ("USG%", "usage_pct", "pct", False), ("ORtg", "orating", "num", False),
    ("DRtg", "drating", "num", True), ("NetRtg", "net_rtg", "num", False),
]
TOTALS_HEADERS = [column[0] for column in AVERAGES]
JOINER = "\u2060/\u2060"       # a word-joiner around the slash: Word does not break "10/14" there


def _text(value: Any, kind: str) -> str:
    if kind == "min":
        return fmt_min(value)
    return safe(value, suffix="%") if kind == "pct" else safe(value)


def _coloured(player: Dict[str, Any], players: List[Dict[str, Any]], columns: List[Tuple[str, str, str, bool]]) -> Dict[str, Any]:
    """One row of ``text`` and quartile ``fill`` (``None`` for no colour) per column, the player against the whole league."""
    cells = []
    for _header, key, kind, lower_is_better in columns:
        cells.append({"text": _text(player.get(key), kind), "fill": quartile_fill(player.get(key), [p.get(key) for p in players], reverse=lower_is_better)})
    return {"headers": [column[0] for column in columns], "cells": cells}


def _totals(player: Dict[str, Any]) -> List[str]:
    def n(key: str) -> str:
        return str(player.get(key) or 0)

    def made(key: str) -> str:
        return f"{n(f'total_{key}m')}{JOINER}{n(f'total_{key}a')}"

    return [n("games_played"), fmt_min(player.get("total_minutes", 0) or 0), n("total_pts"), made("p1"), made("p2"), made("p3"), n("total_ro"), n("total_rd"), n("total_rt"),
            n("total_assist"), n("total_st"), n("total_to"), n("total_bs"), n("total_pf"), n("total_val")]


def player_tables(player: Dict[str, Any], players: List[Dict[str, Any]]) -> Dict[str, Any]:
    """The three tables of the page of ``player`` (``players``: everyone of the competition, who the colours are measured against)."""
    return {"averages": _coloured(player, players, AVERAGES), "totals": {"headers": TOTALS_HEADERS, "cells": _totals(player)}, "advanced": _coloured(player, players, ADVANCED)}
