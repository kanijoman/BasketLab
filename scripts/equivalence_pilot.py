"""Exploratory pilot of the equivalence estimator (#891, before E1b): ``python scripts/equivalence_pilot.py [--person feb:2099031 ...]``.

Reads the publication of ``talent-data`` as the web does (the open key of the beta is in its manifest: ~1.5 minutes, 93 competitions) and, with the movements of ``market.equivalence`` (E1a), fits for each pair of
neighbouring levels the model of the design (``docs/evaluaciones/2026-11-20_grafo-equivalencias-891.md``)::

    z_B = rho_s * z_A + (theta_B - theta_A)        rho_s: the reliability of the axis, from the stayers; theta_B - theta_A: the shift of level, from the movers in both directions

Prints (1) the leave-one-PERSON-out validation of each pair (the error against two baselines and the coverage of the 80 % interval) and (2) for each ``--person`` the prediction of every change of competition of
his career, WITHOUT him in the fit, against what he did. It is a probe, not the estimator: E1b will do this with tests, the graph of all the competitions and the walk-forward study. Not run by the CI.
"""
import argparse
import base64
import collections
import json
import statistics as st
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path
from statistics import NormalDist

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT)]

from src.live_prep.package_scopes import open_sealed  # noqa: E402
from src.market.equivalence import AXES, movements, observations, stayers  # noqa: E402

BASE = "https://raw.githubusercontent.com/kanijoman/BasketLab/talent-data/"
EDGES = [("F|feb|L.F.-2", "F|feb|LF CHALLENGE"), ("F|feb|LF CHALLENGE", "F|feb|LF ENDESA"), ("M|feb|SEGUNDA FEB", "M|feb|PRIMERA FEB"), ("M|feb|TERCERA FEB", "M|feb|SEGUNDA FEB")]
Z80 = 1.2816                                    # the half width of an 80 % interval, in standard deviations
NORMAL = NormalDist()


def load_rows():
    """The rows of every competition of ``talent-data`` (``comp`` is the key of the competition) and the competitions."""
    manifest = json.loads(urllib.request.urlopen(BASE + "index.json", timeout=60).read())
    key = base64.b64decode(manifest["open_key"])
    rows = []
    for entry in manifest["competitions"]:
        env = json.loads(urllib.request.urlopen(BASE + urllib.parse.quote(entry["file"]), timeout=60).read())
        data = json.loads(open_sealed(env, entry["wraps"], {"abierto": key}))
        rows.extend({**r, "comp": entry["key"]} for r in (data["rows"] if isinstance(data, dict) else data))
        time.sleep(0.3)
    return rows, {e["key"]: e for e in manifest["competitions"]}


def correlation(pairs):
    xs, ys = zip(*pairs)
    mx, my, sx, sy = st.mean(xs), st.mean(ys), st.pstdev(xs), st.pstdev(ys)
    return sum((a - mx) * (b - my) for a, b in pairs) / (len(pairs) * sx * sy) if sx and sy and len(pairs) > 5 else None


class Pilot:
    def __init__(self, rows, competitions):
        self.obs = observations(rows, competitions)
        self.moves, self.stay = movements(self.obs), stayers(self.obs)

    def fit(self, a, b, exclude=None):
        """``(rho, shift, sigma, movers up, movers down)`` for the pair ``a -> b`` without the person ``exclude``: sigma is the spread of what the model does not explain."""
        rho = [correlation([(s.z_from[i], s.z_to[i]) for s in self.stay if s.from_node in (a, b) and s.person != exclude]) for i in range(len(AXES))]
        up = [m for m in self.moves if (m.from_node, m.to_node) == (a, b) and m.person != exclude]
        down = [m for m in self.moves if (m.from_node, m.to_node) == (b, a) and m.person != exclude]
        shift, sigma = [], []
        for i in range(len(AXES)):
            y = [m.z_to[i] - rho[i] * m.z_from[i] for m in up] + [-(m.z_to[i] - rho[i] * m.z_from[i]) for m in down]
            d = st.mean(y)
            shift.append(d)
            sigma.append(st.pstdev([v - d for v in y]))
        return rho, shift, sigma, len(up), len(down)

    def predict(self, z_from, a, b, exclude=None):
        """The z expected in ``b`` of a player with ``z_from`` in ``a``, with the pair fitted in whichever order the data has it."""
        if (a, b) in EDGES:
            rho, shift, sigma, n1, n2 = self.fit(a, b, exclude)
            sign = 1
        elif (b, a) in EDGES:
            rho, shift, sigma, n1, n2 = self.fit(b, a, exclude)
            sign = -1
        else:
            return None
        return [rho[i] * z_from[i] + sign * shift[i] for i in range(len(AXES))], sigma, n1 + n2, rho

    def validate(self):
        for a, b in EDGES:
            err, cover, n = collections.defaultdict(list), [], 0
            for m in self.moves:
                if {m.from_node, m.to_node} != {a, b}:
                    continue
                got = self.predict(m.z_from, m.from_node, m.to_node, exclude=m.person)
                if got is None or got[2] < 20 or any(r is None for r in got[3]):
                    continue
                pred, sigma, _, rho = got
                n += 1
                for i in range(len(AXES)):
                    err["identity"].append(abs(m.z_to[i] - m.z_from[i]))
                    err["rho only"].append(abs(m.z_to[i] - rho[i] * m.z_from[i]))
                    err["model"].append(abs(m.z_to[i] - pred[i]))
                    cover.append(abs(m.z_to[i] - pred[i]) <= Z80 * sigma[i])
            if n:
                print("%s <-> %s: %d movers; mean error of z: identity %.2f | rho only %.2f | model %.2f; the 80%% interval holds %.0f%%" % (
                    a.split("|")[2], b.split("|")[2], n, st.mean(err["identity"]), st.mean(err["rho only"]), st.mean(err["model"]), 100 * st.mean(cover)))

    def career(self, person):
        mine = sorted((o for o in self.obs if o.person == person), key=lambda o: (o.season, o.node))
        for o in mine:
            print("  %d %s, %d min: %s" % (o.season, o.node.split("|")[2], o.minutes // 60, " ".join("%s%+.1f" % (a, v) for a, v in zip(AXES, o.z))))
        for first in mine:
            for second in mine:
                if second.season - first.season != 1 or first.node == second.node or first.node.split("|")[0] != second.node.split("|")[0]:
                    continue
                got = self.predict(first.z, first.node, second.node, exclude=person)
                if got is None:
                    print("  %d %s -> %d %s: no pair of this pilot" % (first.season, first.node.split("|")[2], second.season, second.node.split("|")[2]))
                    continue
                pred, sigma, movers, _ = got
                inside = sum(abs(second.z[i] - pred[i]) <= Z80 * sigma[i] for i in range(len(AXES)))
                print("  %d %s -> %d %s (%d movers, without him): %d of 8 axes inside the 80%% interval" % (first.season, first.node.split("|")[2], second.season, second.node.split("|")[2], movers, inside))
                for i, axis in enumerate(AXES):
                    print("    %-4s from %+.2f, expected %+.2f (percentile %2d) in [%+.2f, %+.2f], real %+.2f (percentile %2d), error %.2f, error without translating %.2f" % (
                        axis, first.z[i], pred[i], 100 * NORMAL.cdf(pred[i]), pred[i] - Z80 * sigma[i], pred[i] + Z80 * sigma[i], second.z[i], 100 * NORMAL.cdf(second.z[i]),
                        abs(second.z[i] - pred[i]), abs(second.z[i] - first.z[i])))


def main() -> None:
    parser = argparse.ArgumentParser(description="Pilot of the equivalence estimator")
    parser.add_argument("--person", action="append", default=[], help="a person id of Talent (feb:...) whose career to predict, without him in the fit; repeatable")
    args = parser.parse_args()
    pilot = Pilot(*load_rows())
    print("observations %d, movements %d, stayers %d\n\nLeave-one-person-out, every pair:" % (len(pilot.obs), len(pilot.moves), len(pilot.stay)))
    pilot.validate()
    for person in args.person:
        print("\n%s" % person)
        pilot.career(person)


if __name__ == "__main__":
    main()
