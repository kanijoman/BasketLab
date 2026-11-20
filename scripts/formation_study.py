"""The study of the formation index (#893, E3): ``python scripts/formation_study.py [--rows PICKLE] [--json OUT]``.

Reads the publication of ``talent-data`` as the web does (or a pickle of ``(rows, competitions)`` saved before), builds the senior observations and the graph of levels, and runs the validation of
``market.formation`` a promotion out at a time: the levels of the graph are fitted WITHOUT that season. Prints the error against the mean of those who made it, by group, and the coverage of the 80 % range.
Not run by the CI (network); the numbers go to ``docs/evaluaciones/``.
"""
import argparse
import json
import pickle
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "scripts")]

from src.market.equivalence import movements, observations, stayers  # noqa: E402
from src.market.equivalence_model import fit as fit_graph  # noqa: E402
from src.market.formation import formation_observations, leave_one_season_out, pairs  # noqa: E402
from src.market.formation_publish import levels_of, levels_without  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Study of the formation index")
    parser.add_argument("--rows", help="a pickle of (rows, competitions) instead of the network")
    parser.add_argument("--json", help="also write the numbers to this file")
    args = parser.parse_args()
    if args.rows:
        rows, competitions = pickle.load(open(args.rows, "rb"))
    else:
        from equivalence_pilot import load_rows
        rows, competitions = load_rows()
    senior, formation = observations(rows, competitions), formation_observations(rows, competitions)

    study = leave_one_season_out(formation, senior, levels_without(senior))
    print(f"formation observations {len(formation)}, senior {len(senior)}, pairs {len(pairs(formation, senior, levels_of(fit_graph(movements(senior), stayers(senior)))))}")
    f = lambda v: "-" if v is None else f"{v:.3f}"      # noqa: E731
    o = study["overall"]
    print(f"all   n={o['n']:>6}  error: mean of those who made it {f(o['mae_mean'])} | formation index {f(o['mae_model'])}  coverage {f(o['coverage'])} width {f(o['mean_width'])}")
    for group, s in study["per_group"].items():
        print(f"{group:<5} n={s['n']:>6}  error: mean {f(s['mae_mean'])} | index {f(s['mae_model'])}")
    if args.json:
        Path(args.json).write_text(json.dumps(study, indent=1, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
