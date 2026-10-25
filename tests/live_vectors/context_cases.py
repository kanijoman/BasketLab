"""Vector cases of the FIBA timeout budget and the game context (issue #239); imported by ``generate.py``."""

from builders import pad_to_score
from live_helpers import OWN, RIVAL

REGULATION = 2400


def elapsed_of(period, remaining):
    start = 600 * (period - 1) if period <= 4 else 2400 + 300 * (period - 5)
    return start + (600 if period <= 4 else 300) - remaining


def ctx_snap(period, remaining, margin=0, own_to=(), rival_to=(), log=None, pf=0):
    """A snapshot with a score, timeouts given as (period, remaining) and, optionally, an own player with ``pf`` fouls."""
    team = lambda to: {"name": "x", "fouls_game": 0, "timeouts": [elapsed_of(p, r) for p, r in to],  # noqa: E731
                       "fouls_by_period": {}, "stats": {}}
    players = {"x": {"name": "Ana", "team_id": OWN, "on_court": True, "minutes": 0, "stint": 0, "pf": pf, "pts": 0,
                     "pf_by_period": {}}} if pf else {}
    score = {OWN: 60 + margin, RIVAL: 60}
    return {"period": period, "remaining": remaining, "elapsed": elapsed_of(period, remaining), "last_num": 1,
            "score": score, "teams": {OWN: team(own_to), RIVAL: team(rival_to)},
            "players": players, "log": pad_to_score(log or [], score)}


def context_cases(case):
    """``case(fn, args)`` builder of generate.py -> the cases of ``timeouts.state``, ``context.phase`` and sequences."""
    out = []
    budgets = [
        ctx_snap(1, 600), ctx_snap(2, 100, own_to=[(1, 300)]), ctx_snap(2, 100, own_to=[(1, 300), (2, 400)]),
        ctx_snap(3, 600, own_to=[(1, 300), (2, 400)]), ctx_snap(3, 300, own_to=[(3, 400)]),
        ctx_snap(4, 130), ctx_snap(4, 120), ctx_snap(4, 60, own_to=[(4, 110)]), ctx_snap(4, 60, own_to=[(4, 110), (4, 90)]),
        ctx_snap(4, 60, own_to=[(3, 300), (4, 500)], rival_to=[(4, 100)]), ctx_snap(5, 300), ctx_snap(5, 100, own_to=[(5, 200)]),
        ctx_snap(6, 300, own_to=[(5, 200)]), ctx_snap(3, 480, own_to=[(3, 500)], rival_to=[(3, 400)]),
    ]
    for s in budgets:
        for team in (OWN, RIVAL, "nobody"):
            out.append(case("timeouts.state", {"snapshot": s, "team": team}))
    phases = [(4, 479, 20), (4, 480, 25), (4, 100, -19), (4, 240, 6), (4, 241, 2), (4, 100, 7), (3, 100, 30), (5, 300, 0),
              (5, 200, 10), (4, 100, -22), (2, 300, -30)]
    for period, remaining, margin in phases:
        for cfg in (None, {"decided_margin": 10, "close_margin": 2, "close_remaining_s": 60}):
            out.append(case("context.phase", {"snapshot": ctx_snap(period, remaining, margin), "own": OWN, "rival": RIVAL,
                                              "config": cfg}))
    out.append(case("context.phase", {"snapshot": ctx_snap(4, 100, 30), "own": OWN, "rival": None, "config": None}))
    run = [[2000, RIVAL, "pts", 3], [2040, RIVAL, "pts", 2], [2090, RIVAL, "pts", 3]]
    later = [[2300, RIVAL, "pts", 3], [2340, RIVAL, "pts", 2], [2390, RIVAL, "pts", 3]]
    turnovers = [[2100 + 20 * i, OWN, "tov", 1] for i in range(4)]
    sequences = {
        # decided, then the game reopens, then decided again after the re-arm
        "decided": [ctx_snap(4, 300, -22, log=run), ctx_snap(4, 290, -22, log=run), ctx_snap(4, 250, -9, log=run),
                    ctx_snap(4, 0, -22, log=later)],
        # closing stretch: a 3rd foul and a turnover streak go up one level; the 4th foul is already critical
        "close": [ctx_snap(3, 100, 2, pf=2), ctx_snap(4, 200, 2, pf=3, log=turnovers), ctx_snap(4, 150, 3, pf=4, log=turnovers)],
    }
    for snaps in sequences.values():
        out.append(case("advice.sequence", {"own": OWN, "rival": RIVAL, "snapshots": snaps}))
        out.append(case("advice.sequence", {"own": OWN, "rival": RIVAL, "snapshots": snaps,
                                            "config": {"rules_off": ["game_context"]}}))
    return out
