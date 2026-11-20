"""The study of the age curve (#892, E2): ``python scripts/age_curve_study.py [--json OUT]``.

Reads the publication of ``talent-data`` as the web does (the open key of the beta is in its manifest), builds the pairs of a player who stays in a competition one and two seasons later and runs the validation
of ``market.age_curve`` (a season out at a time) against only shrinking by the reliability, overall and by age group. Not run by the CI (network); the numbers go to ``docs/evaluaciones/``.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "scripts")]

from equivalence_pilot import load_rows  # noqa: E402
from src.market.age_curve import births_of, fit, leave_one_season_out, pairs  # noqa: E402
from src.market.equivalence import AXES, observations  # noqa: E402


def line(name, s):
    f = lambda v: "-" if v is None else f"{v:.3f}"      # noqa: E731
    return f"  {name:<8} n={s['n']:>6}  error: only reliability {f(s['mae_rho_only'])} | with age {f(s['mae_model'])}" + (f"  coverage {f(s['coverage'])} width {f(s['mean_width'])}" if "coverage" in s else "")


def main() -> None:
    parser = argparse.ArgumentParser(description="Study of the age curve")
    parser.add_argument("--json", help="also write the numbers to this file")
    args = parser.parse_args()
    rows, competitions = load_rows()
    obs = observations(rows, competitions)
    births = births_of(rows)
    print(f"observations {len(obs)}, persons with birth {len(births)}")
    report = {}
    for horizon in (1, 2):
        found = pairs(obs, births, horizon)
        study = leave_one_season_out(found)
        report[f"h{horizon}"] = study
        print(f"\n== {horizon} season(s) ahead: {len(found)} pairs ==")
        print(line("all", study["overall"]))
        for group, s in study["per_age_group"].items():
            print(line(group, s))
        if horizon == 1:
            model = fit(found)
            for sex in sorted(model.rho):
                print(f"  curve {sex} (mean of the axes, z): " + " ".join(f"{a}:{sum(model.effect_at(sex, i, a) for i in range(len(AXES))) / len(AXES):+.2f}" for a in (16, 18, 20, 22, 25, 28, 30, 33)))
    if args.json:
        Path(args.json).write_text(json.dumps(report, indent=1, ensure_ascii=False, default=str), encoding="utf-8")


if __name__ == "__main__":
    main()
