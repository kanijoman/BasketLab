"""Regenerate ``equivalence.json``: the parity vectors of the estimator of equivalences (#891, E4 starts here).

``document`` is the ``equivalences`` document built from the real sample of rows (``tests/fixtures/talent_rows_movers.json.gz``) and ``cases`` are players' histories (observations of one person) with the
estimate ``equivalence_publish.estimate_from_document`` gives for a target competition, ``null`` included. The browser port (``frontend/src/market/equivalence.ts``) must give the same numbers.
``python tests/local_vectors/generate_equivalence.py``; ``tests/test_market_vectors.py`` checks the file is current.
"""
import gzip
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from src.market.equivalence import observations  # noqa: E402
from src.market.equivalence_publish import build_document, estimate_from_document  # noqa: E402

FIXTURE = ROOT / "tests" / "fixtures" / "talent_rows_movers.json.gz"
OUT = Path(__file__).resolve().parent / "equivalence.json"
PERSONS = 60                                                      # the first persons (sorted) with a graph node


def build() -> dict:
    data = json.loads(gzip.decompress(FIXTURE.read_bytes()).decode("utf-8"))
    document = build_document(data["rows"], data["competitions"])
    by_person = {}
    for o in observations(data["rows"], data["competitions"]):
        by_person.setdefault(o.person, []).append(o)
    nodes = sorted({n for part in document["sexes"].values() for n in part["nodes"]})
    cases = []
    for index, person in enumerate(sorted(by_person)[:PERSONS]):
        history = by_person[person]
        for to in (nodes[index % len(nodes)], nodes[(index + 2) % len(nodes)], "F|feb|NO SUCH LEVEL"):
            result = estimate_from_document(document, history, to)
            cases.append({"history": [{"node": o.node, "season": o.season, "minutes": o.minutes, "z": list(o.z)} for o in history], "to": to,
                          "estimate": None if result is None else [{k: v for k, v in r.items()} for r in result]})
    return {"document": document, "cases": cases}


if __name__ == "__main__":
    OUT.write_text(json.dumps(build(), ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n", encoding="utf-8")
    print("wrote", OUT)
