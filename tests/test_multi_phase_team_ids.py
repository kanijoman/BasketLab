"""Multifase showed no team crests (27/10/2026): its rows did not carry the team id the crest is drawn from.

The FEB team pipelines group by the team id and leave it in ``_id``; TeamStatsService copies it to ``team_id`` for the web, MultiPhaseService
did not. And summing the phases seeded every number with 0, so a numeric id (FBCYL's ``teamIdExtern``, the players' ids) came out as 0.
"""
from typing import Dict, List
from unittest.mock import MagicMock

from src.services.multi_phase_service import MultiPhaseService


def test_multi_phase_rows_carry_the_team_id_of_the_team_stats_regression(smoke_api):
    """The real pipeline on the games of the web smoke: Multifase gives every team the id Equipo gives it (the crest of TeamCell)."""
    http, name = smoke_api
    teams = {r["team_name"]: r["team_id"] for r in http.get(f"/api/v1/teams/{name}").json()["team_stats"]}
    multi = http.get("/api/v1/multi/team-stats", params={"collections": name, "is_fbcyl": "false"}).json()
    assert teams and {r["team_name"]: r.get("team_id") for r in multi} == teams


def _phases(rows_by_collection: Dict[str, List[Dict]], players: Dict[str, List[Dict]] | None = None) -> MultiPhaseService:
    db = MagicMock()
    db.get_team_stats.side_effect = lambda coll, *a, **k: [dict(r) for r in rows_by_collection.get(coll, [])]
    db.get_player_stats.side_effect = lambda coll, *a, **k: [dict(r) for r in (players or {}).get(coll, [])]
    return MultiPhaseService(db, list(rows_by_collection))


def test_numeric_ids_survive_the_sum_of_the_phases_regression():
    """FBCYL rows as its pipeline gives them (``team_id`` = ``teamIdExtern``, a number) in a league phase and a play-off."""
    league = {"team_id": 41823, "team_name": "UNIVERSIDAD DE LEÓN", "games_played": 10, "points_scored": 650}
    playoff = {"team_id": 41823, "team_name": "UNIVERSIDAD DE LEÓN", "games_played": 2, "points_scored": 140}
    [row] = _phases({"FBCYL_LIGA": [league], "FBCYL_PLAYOFF": [playoff]}).get_combined_team_stats(is_fbcyl=True)
    assert row["team_id"] == 41823
    assert row["games_played"] == 12 and row["points_scored"] == 790          # the counts are still summed


def test_a_player_keeps_her_ids_across_the_phases_regression():
    """The player rows carry ``player_id`` and the ``team_id`` of her crest (the compact team column of the web)."""
    phase = {"player_id": 3315, "player_name": "P. VAQUERA", "team_id": 41823, "team_name": "UNIVERSIDAD DE LEÓN", "games_played": 5, "total_points": 60}
    players = {"A": [phase], "B": [dict(phase, games_played=3, total_points=30)]}
    [row] = _phases({"A": [], "B": []}, players).get_combined_player_stats(is_fbcyl=True)
    assert (row["player_id"], row["team_id"], row["games_played"]) == (3315, 41823, 8)
