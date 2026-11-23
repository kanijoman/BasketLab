"""Regenerate ``formation.json``: the parity vectors of the index of the formation (#893, E3c).

``formation`` and ``equivalences`` are the two documents built from the synthetic world of ``tests/test_market_formation_publish.py`` (two senior competitions of a sex, careers that move and players of the
formation who reach the senior game), ``cases`` are histories of formation with the estimate ``formation_publish.estimate_from_documents`` gives for a senior competition (``null`` included) and ``histories`` are
raw rows with what ``formation_observations`` makes of them. The browser port (``frontend/src/market/formation.ts``) must give the same numbers. ``python tests/local_vectors/generate_formation.py``;
``tests/test_market_vectors.py`` checks the file is current.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src"), str(ROOT / "tests")]

import test_market_formation_publish as world  # noqa: E402

from src.market.formation import formation_observations  # noqa: E402
from src.market.formation_publish import estimate_from_documents  # noqa: E402

OUT = Path(__file__).resolve().parent / "formation.json"
PERSONS = 40


def build() -> dict:
    rows, competitions, document, equivalences = world.ROWS, world.COMPETITIONS, world.DOC, world.EQ
    observed = formation_observations(rows, competitions)
    by_person = {}
    for o in observed:
        by_person.setdefault(o.person, []).append(o)
    nodes = sorted(equivalences["sexes"]["F"]["nodes"])
    cases, histories = [], []
    for index, person in enumerate(sorted(by_person)[:PERSONS]):
        history = by_person[person]
        for to in (nodes[index % len(nodes)], nodes[(index + 1) % len(nodes)], "F|feb|NO SUCH LEVEL"):
            result = estimate_from_documents(document, equivalences, history, to)
            cases.append({"history": [{"season": o.season, "group": o.group, "sex": o.sex, "minutes": o.minutes, "z": list(o.z)} for o in history], "to": to, "estimate": result})
        own = [r for r in rows if r["person_id"] == person]
        histories.append({"rows": [{k: r.get(k) for k in ("comp", "person_id", "linked_to", "minutes", "eligible", "pct")} for r in own],
                          "competitions": {k: {f: competitions[k].get(f) for f in ("competition", "league", "gender", "category", "age_group", "season")} for k in sorted({r["comp"] for r in own})},
                          "expected": [{"season": o.season, "group": o.group, "sex": o.sex, "minutes": o.minutes, "z": list(o.z)} for o in observed if o.person == person]})
    return {"formation": document, "equivalences": equivalences, "cases": cases, "histories": histories}


if __name__ == "__main__":
    OUT.write_text(json.dumps(build(), ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n", encoding="utf-8")
    print("wrote", OUT)
