"""Shared synthetic roster for recommender / advice-proposal tests (3 archetypes)."""

from src.live_core.profiles import METRICS

OWN, RIVAL = "T1", "T2"


def z(**kw):
    base = {m: 0.0 for m in METRICS}
    base.update(kw)
    return base


GUARD = dict(ast40=2.0, fg3a40=1.5, orb40=-1.0, drb40=-0.8, blk40=-0.5, usage40=0.5)
BIG = dict(orb40=2.0, drb40=1.8, blk40=1.5, fg2a40=1.0, ast40=-1.0, fg3a40=-1.2)
WING = dict(fg3a40=1.0, fg2a40=0.5, drb40=0.3, ast40=0.2)

TABLE = {
    "g1": {"name": "Guard Uno", "z": z(**GUARD, tov40=2.0), "avg_min": 1500, "p90_min": 2000, "avg_stint": 420},
    "g2": {"name": "Guard Dos", "z": z(**{**GUARD, "ast40": 1.6}, tov40=-1.0), "avg_min": 1200, "p90_min": 1800},
    "g3": {"name": "Guard Tres", "z": z(**{**GUARD, "fg3a40": 1.2}, tov40=1.5), "avg_min": 900, "p90_min": 1500},
    "w1": {"name": "Ala Uno", "z": z(**WING), "avg_min": 1400, "p90_min": 1900},
    "w2": {"name": "Ala Dos", "z": z(**{**WING, "fg3a40": 1.2}), "avg_min": 900, "p90_min": 1500},
    "b1": {"name": "Pivot Uno", "z": z(**BIG, tov40=0.5), "avg_min": 1400, "p90_min": 1900},
    "b2": {"name": "Pivot Dos", "z": z(**{**BIG, "orb40": 1.6}, tov40=-0.5, efg=0.8), "avg_min": 1000, "p90_min": 1600},
    "b3": {"name": "Pivot Tres", "z": z(**{**BIG, "orb40": 1.0, "drb40": 1.0}, tov40=0.2), "avg_min": 600, "p90_min": 1200},
}
ON_COURT = ["g1", "w1", "w2", "b1", "g3"]


def player(pid, on_court, pf=0, minutes=0, stint=0):
    return {"name": TABLE[pid]["name"], "team_id": OWN, "on_court": on_court, "pf": pf,
            "minutes": minutes, "stint": stint, "pts": 0, "pf_by_period": {}}


def snap(period=2, elapsed=900, overrides=None):
    players = {pid: player(pid, pid in ON_COURT) for pid in TABLE}
    for pid, changes in (overrides or {}).items():
        players[pid].update(changes)
    return {"period": period, "elapsed": elapsed, "remaining": 0, "players": players,
            "teams": {}, "score": {}, "log": []}
