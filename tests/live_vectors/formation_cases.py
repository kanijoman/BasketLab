"""Vector cases of the illegal-lineup rule and the recommender constraint (issue #272); imported by ``generate.py``."""

from live_helpers import OWN, RIVAL, TABLE, snap

MARKS = {"f1": True, "f2": False, "f3": False, "f4": False, "f5": False, "f6": True, "f7": None}


def roster_of(marks, team=OWN):
    return {pid: {"team_id": team, "name": pid, "formacion": mark, "birth": None, "nationality": None,
                  "position": None, "dorsal": None, "height": None} for pid, mark in marks.items()}


def lineup_snap(on_court, elapsed, period=3):
    """Own players f1..f7 (the given ones on court) with the minimum of fields the engine reads."""
    players = {pid: {"name": pid, "team_id": OWN, "on_court": pid in on_court, "minutes": 0, "stint": 0, "pf": 0, "pts": 0,
                     "pf_by_period": {}} for pid in MARKS}
    team = {"name": "x", "fouls_game": 0, "timeouts": [], "fouls_by_period": {}, "stats": {}}
    return {"period": period, "remaining": 300, "elapsed": elapsed, "last_num": 1, "score": {OWN: 50, RIVAL: 48},
            "teams": {OWN: team, RIVAL: team}, "players": players, "log": []}


def formation_cases(case):
    out = []
    bad = ["f1", "f2", "f3", "f4", "f5"]                      # one formación player
    fixed = ["f1", "f6", "f3", "f4", "f5"]                    # two: legal
    doubtful = ["f1", "f7", "f3", "f4", "f5"]                 # 1 + one unknown: benefit of the doubt
    sequences = {
        "illegal then fixed": [lineup_snap(bad, 1500), lineup_snap(bad, 1510), lineup_snap(bad, 1520),
                               lineup_snap(fixed, 1530), lineup_snap(bad, 1540), lineup_snap(bad, 1750)],
        "substitution in progress": [lineup_snap(bad, 1500), lineup_snap(bad[:4], 1510), lineup_snap(bad, 1520),
                                     lineup_snap(bad, 1530)],
        "unknown player": [lineup_snap(doubtful, 1500), lineup_snap(doubtful, 1510), lineup_snap(doubtful, 1520)],
    }
    every_config = (None, {"formation_confirm_polls": 1}, {"formation_min_on_court": 0}, {"rules_off": ["formation_lineup"]})
    for name, snaps in sequences.items():
        for config in every_config if name == "illegal then fixed" else every_config[:2]:   # keep the file small
            out.append(case("advice.sequence", {"own": OWN, "rival": RIVAL, "snapshots": snaps,
                                                "roster": roster_of(MARKS), "config": config}))
    out.append(case("advice.sequence", {"own": OWN, "rival": RIVAL, "snapshots": sequences["illegal then fixed"]}))  # no roster

    # recommender: the swap must not leave fewer formación players than the minimum
    marks = {pid: False for pid in TABLE}
    for yes in ("g1", "w1"):
        marks[yes] = True
    for roster in (None, roster_of(marks), roster_of({**marks, "g2": True}), roster_of({**marks, "g2": None}),
                   roster_of({pid: True for pid in ("g1", "g2")} | {p: False for p in TABLE if p not in ("g1", "g2")})):
        for out_pid in ("g1", "b1", "w1"):
            out.append(case("recommender.suggest_swaps", {"own": OWN, "table": TABLE, "snapshot": snap(), "out": out_pid,
                                                          "lever": None, "roster": roster}))
        out.append(case("recommender.suggest_for_lever", {"own": OWN, "table": TABLE, "snapshot": snap(), "lever": "tov",
                                                          "roster": roster}))
    for min_on_court in (0, 1, 3):
        out.append(case("recommender.suggest_swaps", {"own": OWN, "table": TABLE, "snapshot": snap(), "out": "g1", "lever": None,
                                                      "roster": roster_of({**marks, "g2": True}),
                                                      "config": {"formation_min_on_court": min_on_court}}))
    return out
