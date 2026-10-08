"""Generate ``vectors.json``: inputs plus the results the Python reference produces.

Run from the repository root after any intended change of behaviour, then review the diff::

    python tests/live_vectors/generate.py
"""

import copy
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from live_helpers import ON_COURT, OWN, RIVAL, TABLE, player, snap  # noqa: E402
from src.live_core.profiles import DEFAULT_LEAGUE  # noqa: E402
from src.live_core.vectors import run_suite, unwrap_extended_json  # noqa: E402
from src.live_prep.package_builder import build_package  # noqa: E402

GAME = ROOT / "src" / "JSON_samples" / "feb_game.json"
OUT = Path(__file__).with_name("vectors.json")

STATS = dict(fg2m=5, fg2a=10, fg3m=2, fg3a=5, ftm=3, fta=4, orb=2, drb=6, tov=3, stl=1, ast=4, blk=1)
TEAM_A = dict(fg2m=20, fg2a=40, fg3m=6, fg3a=20, ftm=10, fta=14, orb=8, drb=25, tov=10, tov_team=1,
              stl=5, ast=12, blk=2, pts=62)
TEAM_B = dict(fg2m=18, fg2a=38, fg3m=5, fg3a=18, ftm=8, fta=10, orb=6, drb=20, tov=12, tov_team=0,
              stl=7, ast=10, blk=1, pts=53)
EMPTY = {k: 0 for k in STATS}


def line(action, text, **kw):
    base = {"num": "7", "quarter": "2", "time": "05:30", "idTeam": "T1", "idPlayer": "P1",
            "action": action, "text": text, "scoreA": None, "scoreB": None, "deleted": None}
    base.update(kw)
    return base


def case(fn, args):
    return {"fn": fn, "args": args}


def mk(period, elapsed, players):
    """A snapshot with exactly the given players (live_helpers.snap uses the shared roster)."""
    s = snap(period=period, elapsed=elapsed)
    s["players"] = players
    return s


def unit_cases():
    rng = random.Random(2026)
    cases = []
    # clock
    cases += [case("clock.elapsed_seconds", [p, r]) for p, r in
              [(1, 600), (1, 0), (2, 600), (3, 1), (4, 33), (4, 0), (5, 300), (5, 0), (6, 150)]]
    cases += [case("clock.parse_clock", [t]) for t in ["10:00", "00:33", "0:05", "FINAL", "", None, "ab:cd", "10"]]
    cases += [case("clock.period_and_remaining", [e]) for e in [-5, 0, 30, 599, 600, 2367, 2400, 2699, 2700, 3000]]
    # events
    lines = [
        line("subst", "(A) J. PEREZ: Sustitución (Entra a pista)"),
        line("subst", "(A) J. PEREZ: Sustituci�n (Sale de pista)"),
        line("shoot", "(A) X: TIRO DE 2 ANOTADO (Puntos: 10)"), line("shoot", "(A) X: TIRO DE 3 FALLADO"),
        line("fthrow", "(A) X: TIRO DE 1 ANOTADO (Puntos: 5)"), line("fthrow", "(A) X: TIRO DE 1 FALLADO"),
        line("foul", "(A) X: FALTA Personal (Faltas: 3. Faltas de equipo: 17). Tiros libres: 2"),
        line("foul", "(A) X: FALTA Antideportiva (Faltas: 2. Faltas de equipo: 4). Tiros libres: 2"),
        line("rebound", "(A) X: REBOTE (Rebotes: 3)"), line("lose", "(A) X: P�RDIDA (P�rdidas: 2)"),
        line("lose", "(A)  Equipo: P�RDIDA (P�rdidas: 1)", idPlayer=None),
        line("recovery", "(A) X: ROBO (Robos: 1)"), line("assist", "(A) X: ASISTENCIA (Asistencias: 4)"),
        line("blockshot", "(A) X: TAP�N (Tapones: 1)"), line("timeout", "(A) Tiempo muerto", idPlayer=None),
        line("period", "Comienzo del Cuarto 4", quarter="4", time="10:00", idTeam=None, idPlayer=None),
        line("period", "Fin del Cuarto 4", quarter="4", time="00:00", idTeam=None, idPlayer=None),
        line("shoot", "(A) X: TIRO DE 2 FALLADO", deleted="1"), line("weird", "???"),
        {"num": None, "action": "shoot"}, line("shoot", "(A) X: TIRO DE 2 FALLADO", time="FINAL"),
    ]
    cases += [case("events.parse_line", [ln]) for ln in lines]
    # fouls
    cases += [case("fouls.warn_threshold", [p]) for p in range(0, 8)]
    cases += [case("fouls.evaluate", ["p1", "Ana", pf, period, last])
              for pf in range(0, 7) for period in (1, 2, 3, 4, 5) for last in (0, 2)]
    # fatigue
    base = {"avg_stint": 360, "avg_min": 1500, "p90_min": 2000}
    cases += [case("fatigue.index", [stint, minutes, elapsed, b])
              for stint, minutes, elapsed, b in [
                  (300, 1200, 1200, base), (720, 1100, 1200, base), (840, 700, 900, None), (0, 100, 100, None),
                  (400, 500, 1200, base), (900, 1900, 1500, base), (720, 1100, 300, base), (0, 1900, 1500, {"avg_min": 1000})]]
    # four factors
    cases += [case("four_factors.possessions", [s]) for s in (TEAM_A, TEAM_B, EMPTY | {"tov_team": 0, "pts": 0})]
    cases += [case("four_factors.factors", [TEAM_A, TEAM_B]), case("four_factors.factors", [TEAM_B, TEAM_A]),
              case("four_factors.differentials", [TEAM_A, TEAM_B]),
              case("four_factors.differentials", [EMPTY | {"tov_team": 0, "pts": 0}, TEAM_B])]
    cases += [case("four_factors.shrink", a) for a in
              [[0.1, 0.02, 0, 40], [0.1, 0.02, 40, 40], [0.1, 0.02, 10000, 40], [0.0, 0.0, 0, 0]]]
    ff_snap = {"elapsed": 1200, "period": 3, "remaining": 0, "score": {"A": 40, "B": 45},
               "teams": {"A": {"stats": TEAM_A}, "B": {"stats": TEAM_B}}}
    cases += [case("four_factors.evaluate", [{"snapshot": ff_snap, "own": "A", "rival": "B"}][0] | {})
              if False else case("four_factors.evaluate", {"snapshot": ff_snap, "own": "A", "rival": "B"})]
    cases += [case("four_factors.evaluate", {
        "snapshot": {**ff_snap, "elapsed": e, "score": {"A": 30, "B": 28}}, "own": "A", "rival": "B",
        "baselines": {"four_factors_prior": {"efg": 0.03, "tov": -0.01, "orb": 0.02, "ftr": 0.0}, "pace_per_40": 72.0}})
        for e in (240, 1200, 2200, 2400)]
    # profiles
    cases += [case("profiles.raw_rates", [STATS, s]) for s in (1200, 2400, 90, 0)]
    rates = {m: 2.0 + i for i, m in enumerate(DEFAULT_LEAGUE)}
    cases += [case("profiles.shrink_rates", [rates, s, f, DEFAULT_LEAGUE]) for s, f in ((0, 0), (600, 30), (5000, 400))]
    cases += [case("profiles.z_scores", [rates, DEFAULT_LEAGUE])]
    z1 = {d: rng.uniform(-2, 2) for d in ("orb40", "drb40", "ast40", "blk40", "fg3a40", "fg2a40", "usage40")}
    z2 = {d: rng.uniform(-2, 2) for d in z1}
    cases += [case("profiles.role_distance", [z1, z2]), case("profiles.role_distance", [z1, z1])]
    cases += [case("profiles.impact_rates", [STATS, s]) for s in (1200, 0)]
    # zones
    pts = [(7.5, 1.8), (7.5, 0.6), (7.5, 4.5), (10.2, 1.8), (3.0, 3.0), (7.5, 6.9), (7.5, 10.0), (0.4, 1.0),
           (14.6, 1.0), (2.0, 8.0), (13.0, 8.0)] + [(rng.uniform(0, 15), rng.uniform(0, 14)) for _ in range(60)]
    cases += [case("zones.classify_fiba", [round(x, 6), round(y, 6)]) for x, y in pts]
    cases += [case("zones.feb_to_fiba", [round(rng.uniform(0, 100), 6), round(rng.uniform(0, 100), 6), rng.choice([0, 1])])
              for _ in range(30)]
    cases += [case("zones.family_totals", [{"left_corner_three": {"a": 6, "m": 4, "pts": 12},
                                            "right_corner_three": {"a": 2, "m": 1, "pts": 3},
                                            "restricted_area": {"a": 8, "m": 5, "pts": 10}, "bogus": {"a": 1}}])]
    # recommender
    s0 = snap()
    s_foul = snap(period=2, overrides={"b3": {"pf": 3}})
    s_tired = snap(elapsed=1500, overrides={"b2": {"minutes": 1900}})
    for s in (s0, s_foul, s_tired):
        for out in ("b1", "g1", "w1"):
            for lever in (None, "tov", "orb"):
                cases.append(case("recommender.suggest_swaps",
                                  {"own": OWN, "table": TABLE, "snapshot": s, "out": out, "lever": lever}))
        for lever in ("tov", "orb", "efg", "ftr", "def_reb"):
            cases.append(case("recommender.suggest_for_lever", {"own": OWN, "table": TABLE, "snapshot": s, "lever": lever}))
    # advice sequences (dedupe, re-arm, proposals, rival scouting)
    cases += advice_sequences()
    return cases


def advice_sequences():
    out = []
    pf_steps = [mk(p, 300 * p, {"x": player("g1", True, pf=pf)})
                for p, pf in [(1, 1), (1, 2), (1, 2), (2, 2), (2, 3), (2, 3), (3, 3), (3, 4), (4, 4), (4, 5)]]
    for s in pf_steps:
        s["players"]["x"]["name"], s["players"]["x"]["team_id"] = "Ana", OWN
    out.append(case("advice.sequence", {"own": OWN, "rival": RIVAL, "snapshots": pf_steps}))

    tired = [mk(2, e, {"p": player("g1", True, stint=s, minutes=m)})
             for e, s, m in [(1200, 720, 1100), (1210, 730, 1110), (1440, 960, 1400), (1500, 20, 1420)]]
    for s in tired:
        s["players"]["p"].update(name="Ana", team_id=OWN)
    out.append(case("advice.sequence", {"own": OWN, "rival": RIVAL, "snapshots": tired,
                                        "baselines": {"p": {"avg_stint": 360, "avg_min": 1500, "p90_min": 2000}}}))

    hot_stats = {k: 0 for k in STATS}
    rival_steps = []
    for e, minutes, pts, orb, zones in [
        (900, 300, 4, 1, {}),
        (1200, 840, 17, 4, {"left_corner_three": {"a": 6, "m": 4, "pts": 12}}),
        (1500, 960, 19, 4, {"left_corner_three": {"a": 7, "m": 5, "pts": 15},
                            "left_wing_three": {"a": 6, "m": 1, "pts": 3}, "right_wing_three": {"a": 6, "m": 1, "pts": 3},
                            "restricted_area": {"a": 4, "m": 2, "pts": 4}}),
    ]:
        s = mk(3, e, {"r1": {"name": "Rival Uno", "team_id": RIVAL, "on_court": True, "pf": 0,
                             "minutes": minutes, "stint": 300, "pts": pts, "pf_by_period": {},
                             "stats": {**hot_stats, "orb": orb}}})
        s["zones"] = {OWN: {}, RIVAL: zones}
        rival_steps.append(s)
    out.append(case("advice.sequence", {
        "own": OWN, "rival": RIVAL, "baselines": TABLE, "snapshots": rival_steps,
        "rival_baselines": {"r1": {"name": "Rival Uno", "impact40": {"pts": 14.0, "orb": 1.5, "stl": 1.4, "ast": 3.5, "fg3m": 1.7, "fta": 3.5}}},
        "zone_ref": {"rival": {"left_corner_three": {"a": 30, "m": 11, "pts": 33}}, "league": {}}}))

    ff = []
    for e, tov in [(600, 12), (1200, 22), (1260, 23), (1800, 24)]:
        s = snap(elapsed=e, period=2)
        team = {"name": "x", "fouls_game": 0, "timeouts": [], "fouls_by_period": {}}
        base = dict(fg2m=20, fg2a=40, fg3m=6, fg3a=20, ftm=10, fta=14, orb=8, drb=25, tov=10, tov_team=0,
                    stl=5, ast=12, blk=2, pts=0)
        s["teams"] = {OWN: {**team, "stats": {**base, "tov": tov}}, RIVAL: {**team, "stats": base}}
        s["score"] = {OWN: 40, RIVAL: 40}
        s["log"] = [[e - 30 * i, OWN, "tov", 1] for i in range(4)] if tov > 20 else []
        ff.append(s)
    out.append(case("advice.sequence", {"own": OWN, "rival": RIVAL, "baselines": TABLE, "snapshots": ff}))
    return out


def build_suite():
    game = unwrap_extended_json(json.loads(GAME.read_text(encoding="utf-8")))
    package = build_package([game], "FEB_VECTORS", "2025-2026", "982047", "981204", created_at="2026-01-01T00:00:00Z")
    suite = {
        "version": 1,
        "unit": unit_cases(),
        "engine": {"package": package.dumps(),
                   "checkpoints": [[1, 300], [1, 0], [2, 300], [2, 0], [3, 450], [3, 0], [4, 600], [4, 300], [4, 60], [4, 0]]},
    }
    expected = run_suite(copy.deepcopy(suite), game)
    return {**suite, "expected": expected}


def main():
    suite = build_suite()
    with open(OUT, "w", encoding="utf-8", newline="\n") as handle:  # same bytes on Windows and Linux
        handle.write(json.dumps(suite, sort_keys=True, indent=1, ensure_ascii=False) + "\n")
    kind = {}
    for c in suite["unit"]:
        kind[c["fn"].split(".")[0]] = kind.get(c["fn"].split(".")[0], 0) + 1
    print(f"wrote {OUT.relative_to(ROOT)}: {len(suite['unit'])} unit cases {kind}, "
          f"{len(suite['engine']['checkpoints'])} engine checkpoints, {OUT.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
