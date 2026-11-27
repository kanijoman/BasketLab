"""The reference vector of the team formulas (#1153): inputs and the value each formula must give, written with the TEXTBOOK expressions (Basketball Reference / Dean Oliver, the ones of CLAUDE.md),
independent of ``config/formulas.json`` so that the registry is checked against something that is not itself. ``python tests/formulas/generate.py`` rewrites ``tests/formulas/vector.json``;
``tests/test_formulas.py`` (Python) and ``frontend/src/lib/formulas.test.ts`` (TypeScript) both read it."""
import json
from pathlib import Path

FT = 0.44


def textbook(c):
    """Every team formula from the counters of a team and of its rival, ``None`` when its denominator is 0."""
    fga = c["fg2a"] + c["fg3a"]
    fgm = c["fg2m"] + c["fg3m"]

    def div(n, d, scale=100):
        return None if d <= 0 else n / d * scale                      # an empty or NEGATIVE denominator (an estimated count of possessions can be below 0) has no value

    ortg, drtg = div(c["points"], c["poss"]), div(c["points_against"], c["opp_poss"])
    return {
        "offensive_rating": ortg, "defensive_rating": drtg, "net_rating": None if ortg is None or drtg is None else ortg - drtg,
        "efg_percentage": div(fgm + 0.5 * c["fg3m"], fga),
        "turnover_rate": div(c["tov"], fga + FT * c["fta"] + c["tov"]),
        "offensive_rebound_rate": div(c["orb"], c["orb"] + c["opp_drb"]),
        "defensive_rebound_rate": div(c["drb"], c["drb"] + c["opp_orb"]),
        "free_throw_rate": div(c["fta"], fga),
        "three_point_rate": div(c["fg3a"], fga),
        "true_shooting": div(c["points"], 2 * (fga + FT * c["fta"])),
        "assist_fg_rate": div(c["ast"], fgm),
        "assist_rate": div(c["ast"], c["poss"]),
        "steal_rate": div(c["stl"], c["opp_poss"]),
        "block_rate": div(c["blk"], c["opp_poss"]),
    }


CASES = {
    "a real game-like season": dict(points=1520, points_against=1480, fg2m=310, fg2a=620, fg3m=120, fg3a=340, fta=260, ast=410, stl=140, blk=60, tov=270, orb=150, drb=520,
                                    opp_orb=140, opp_drb=500, poss=1480.5, opp_poss=1490.25),
    "one overtime game (real possessions)": dict(points=90, points_against=81, fg2m=20, fg2a=40, fg3m=8, fg3a=24, fta=18, ast=17, stl=8, blk=3, tov=13, orb=9, drb=28,
                                                  opp_orb=10, opp_drb=26, poss=90.0, opp_poss=81.0),
    "a team that never shot nor kept the ball": dict(points=0, points_against=10, fg2m=0, fg2a=0, fg3m=0, fg3a=0, fta=0, ast=0, stl=0, blk=0, tov=0, orb=0, drb=0,
                                                      opp_orb=0, opp_drb=0, poss=0, opp_poss=0),
    "no rival possessions": dict(points=50, points_against=0, fg2m=10, fg2a=20, fg3m=5, fg3a=15, fta=10, ast=8, stl=4, blk=2, tov=6, orb=5, drb=15,
                                 opp_orb=6, opp_drb=14, poss=55.5, opp_poss=0),
    "a game whose estimated possessions are negative": dict(points=4, points_against=2, fg2m=0, fg2a=0, fg3m=0, fg3a=0, fta=2, ast=0, stl=1, blk=0, tov=0, orb=1, drb=3,
                                                            opp_orb=0, opp_drb=0, poss=-0.12, opp_poss=-0.12),
    "the rebounds of a team without rival misses": dict(points=70, points_against=60, fg2m=20, fg2a=35, fg3m=6, fg3a=20, fta=12, ast=14, stl=7, blk=4, tov=11, orb=0, drb=0,
                                                         opp_orb=0, opp_drb=0, poss=70.0, opp_poss=68.0),
}


def build():
    return {"cases": [{"name": name, "counters": counters, "expected": textbook(counters)} for name, counters in CASES.items()]}


if __name__ == "__main__":
    out = Path(__file__).resolve().parent / "vector.json"
    out.write_text(json.dumps(build(), indent=1, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    print("wrote", out)
