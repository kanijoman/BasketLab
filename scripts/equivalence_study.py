"""The study of the equivalence estimator (#891, E1b): ``python scripts/equivalence_study.py [--json OUT]``.

Reads the publication of ``talent-data`` as the web does (the open key of the beta is in its manifest: ~1.5 minutes), builds the movements (``market.equivalence``) and runs the validation of
``market.equivalence_study`` for each variant of the estimator: a season out at a time and, stricter, walk-forward over the last seasons. Prints the table of each variant (the error of the model against not
translating and against only shrinking, the coverage of the 80 % interval, its width) and the verdict of the design: the range can be shown only if the model beats the baselines AND its interval holds
about 80 %. Not run by the CI (it needs the network and takes a minute); the numbers go to ``docs/evaluaciones/``.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "scripts")]

from equivalence_pilot import load_rows  # noqa: E402
from src.market.equivalence import movements, observations, stayers  # noqa: E402
from src.market.equivalence_study import leave_one_season_out, verdict, walk_forward  # noqa: E402

VARIANTS = {"reliability (rho of the stayers)": {"slope": "reliability"}, "free slope (the movers' own)": {"slope": "free"}}


def line(name, summary):
    f = lambda v: "-" if v is None else f"{v:.3f}"      # noqa: E731
    return f"  {name:<34} n={summary['n']:>6}  error: not translating {f(summary['mae_identity'])} | rho only {f(summary['mae_rho_only'])} | model {f(summary['mae_model'])}  coverage {f(summary['coverage'])}  width {f(summary['mean_width'])}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Study of the equivalence estimator")
    parser.add_argument("--json", help="also write the numbers to this file")
    args = parser.parse_args()
    rows, competitions = load_rows()
    obs = observations(rows, {k: v for k, v in competitions.items()})
    moves, stay = movements(obs), stayers(obs)
    print(f"observations {len(obs)}, movements {len(moves)}, stayers {len(stay)}")
    seasons = sorted({m.to_season for m in moves})
    report = {}
    for name, options in VARIANTS.items():
        loso, forward = leave_one_season_out(moves, stay, **options), walk_forward(moves, stay, first=seasons[-2], **options)
        report[name] = {"leave_one_season_out": loso, "walk_forward": forward, "verdict": verdict(loso)}
        print(f"\n== {name} ==\nA season out at a time:")
        print(line("all", loso["overall"]))
        for edge, summary in loso["per_edge"].items():
            print(line(edge, summary))
        for axis, summary in loso["per_axis"].items():
            print(line("axis " + axis, summary))
        print(f"Walk-forward (only the past, from {seasons[-2]}):")
        print(line("all", forward["overall"]))
        print("Verdict:", verdict(loso))
    if args.json:
        Path(args.json).write_text(json.dumps(report, indent=1, ensure_ascii=False, default=str), encoding="utf-8")


if __name__ == "__main__":
    main()
