"""Study of the models behind the win probability and its levers (issue #567): does a model with more information beat the one in the app?

``python scripts/wp_model_study.py collect --out samples.pkl DIR [DIR ...]`` replays the finished games of each folder (ONE season of ONE competition per folder: every folder has its own priors) and
keeps, at a cut every 5 minutes and from both sides, what the engine knows: score, clock, the team stats of both teams, fouls, timeouts, the last five minutes and the package baselines.
``python scripts/wp_model_study.py fit samples.pkl`` compares, with cross-validation BY GAME (a game never is in train and test), the structural model of the app with logistic and boosted models that
read more, and prints the contribution of each group of variables (the base of the levers). ``persistence`` (do the stats of the game predict the next five minutes?),
``collect-lineups`` + ``individual`` (ratings of the players on court), ``benchmark`` (other families: Bayesian state-space prior, boosting, neural network) and ``structural``
(the model of the app calibrated per family of competitions, with the Bayesian prior). Research tool, not part of the product: it needs scikit-learn and scipy.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

ROOT = Path(__file__).resolve().parents[1]
for extra in (ROOT, ROOT / "src", Path(__file__).resolve().parent):
    sys.path.insert(0, str(extra))

from wp_study.families import benchmark, structural  # noqa: E402
from wp_study.players import collect_lineups, individual  # noqa: E402
from wp_study.rotation import reliability as rotation_reliability, report as rotation_report  # noqa: E402
from wp_study.samples import collect  # noqa: E402
from wp_study.team import fit, persistence  # noqa: E402


def main(argv: Sequence[str] = None) -> int:
    parser = argparse.ArgumentParser(description="Study of the models of the win probability (#567)")
    sub = parser.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("collect")
    c.add_argument("--out", required=True)
    c.add_argument("folders", nargs="+")
    f = sub.add_parser("fit")
    f.add_argument("samples")
    q = sub.add_parser("persistence")
    q.add_argument("samples")
    cl = sub.add_parser("collect-lineups")
    cl.add_argument("--out", required=True)
    cl.add_argument("folders", nargs="+")
    st = sub.add_parser("structural")
    st.add_argument("samples", nargs="+")
    bm = sub.add_parser("benchmark")
    bm.add_argument("samples", nargs="+")
    ind = sub.add_parser("individual")
    ind.add_argument("samples")
    ind.add_argument("lineups")
    rot = sub.add_parser("rotation")
    rot.add_argument("lineups")
    rot.add_argument("--men", action="store_true")
    args = parser.parse_args(argv)
    if args.cmd == "collect":
        collect(args.folders, args.out)
    elif args.cmd == "collect-lineups":
        collect_lineups(args.folders, args.out)
    elif args.cmd == "structural":
        print(structural(args.samples))
    elif args.cmd == "benchmark":
        print(benchmark(args.samples))
    elif args.cmd == "individual":
        print(individual(args.samples, args.lineups))
    elif args.cmd == "rotation":
        print(rotation_report(args.lineups, women=not args.men))
        print()
        print(rotation_reliability(args.lineups, women=not args.men))
    elif args.cmd == "persistence":
        print(persistence(args.samples))
    else:
        print(fit(args.samples))
    return 0


if __name__ == "__main__":
    sys.exit(main())
