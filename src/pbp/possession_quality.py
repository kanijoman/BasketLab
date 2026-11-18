"""Per-team counts of the play-by-play (T2/T3/T1 made-attempted, rebounds, turnovers) to audit it against the box score.

Rebounds follow the rule of the possession tracker: offensive when the rebounding team is the one that missed the last
shot. For FEB the official box score does not credit team rebounds (lines without a player), so they are not counted;
FBCYL carries its own offensive/defensive label.
"""
from __future__ import annotations

from typing import Dict, Iterable, List

from .game_events import game_events

QUALITY_METRICS = ("T2M", "T2A", "T3M", "T3A", "T1M", "T1A", "RebO", "RebD", "TOV")
_SHOT_KEYS = {"fg2": ("T2M", "T2A"), "fg3": ("T3M", "T3A"), "ft": ("T1M", "T1A")}


def count_quality_pbp_metrics(game_data: Dict, is_fbcyl: bool, team_ids: List[str]) -> Dict[str, Dict[str, int]]:
    """Count per-team quality metrics from the play-by-play events."""
    return count_quality_events(game_events(game_data, is_fbcyl), is_fbcyl, team_ids)


def count_quality_events(events: Iterable, is_fbcyl: bool, team_ids: List[str], use_labels: bool = False) -> Dict[str, Dict[str, int]]:
    """The same counts over the events given (the reconciliation of the external sources passes them without the lines the table deleted, #884). With ``use_labels`` a rebound line that says whether it is
    offensive or defensive (FIBA's ``REBOTE OFENSIVO``) is counted as it says and the rule of the tracker only decides the lines that do not (FEB's): an event written late can put a rebound before the missed shot
    it follows, which breaks the inference but not the label (#887). Without it nothing changes for FEB and FBCYL."""
    counts = {tid: {metric: 0 for metric in QUALITY_METRICS} for tid in team_ids}
    last_miss = None
    for ev in sorted(events, key=lambda e: (e.elapsed, e.num)):
        team = counts.get(ev.team_id)
        if team is None:
            continue
        if ev.kind in _SHOT_KEYS:
            made_key, attempt_key = _SHOT_KEYS[ev.kind]
            team[attempt_key] += 1
            team[made_key] += 1 if ev.made else 0
            last_miss = None if ev.made and ev.kind != "ft" else (ev.team_id if not ev.made else last_miss)
        elif ev.kind == "rebound":
            if not is_fbcyl and ev.player_id is None:
                last_miss = None
                continue
            label = _offensive(ev.text) if use_labels and not is_fbcyl else None
            offensive = _offensive(ev.text) if is_fbcyl else (label if label is not None else last_miss == ev.team_id)
            if offensive is not None and (is_fbcyl or label is not None or last_miss is not None):
                team["RebO" if offensive else "RebD"] += 1
            last_miss = None
        elif ev.kind == "turnover":
            team["TOV"] += 1
    return counts


def _offensive(label: str):
    low = label.lower()
    return True if "ofensivo" in low else False if "defensivo" in low else None
