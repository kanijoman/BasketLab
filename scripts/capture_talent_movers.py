"""Capture a REAL sample of the rows of Talent as a fixture (#891, E1a): ``python scripts/capture_talent_movers.py``.

Reads the publication of ``talent-data`` as the web does (the open key of the beta is in its manifest) and keeps, for a few hundred persons who moved between competitions or stayed in one, only what the
equivalence graph reads: the person, the competition (its family, sex, category and level), the season, whether the player played enough, his age, his minutes and his percentiles on the eight axes of the
radar. **No names and no birth dates**: only the ids that are already public in the published files. Saved as ``tests/fixtures/talent_rows_movers.json.gz`` (gzip without a timestamp: the same publication gives the
same bytes). Not run by the CI: the tests read what is committed.
"""
import base64
import gzip
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT)]

from src.live_prep.package_scopes import open_sealed  # noqa: E402

BASE = "https://raw.githubusercontent.com/kanijoman/BasketLab/talent-data/"
OUT = ROOT / "tests" / "fixtures" / "talent_rows_movers.json.gz"
AXES = ("pts", "ast", "orb", "drb", "stl", "blk", "efg", "tov")
SENIOR_FAMILIES = ("LF ENDESA", "LF CHALLENGE", "L.F.-2", "PRIMERA FEB", "SEGUNDA FEB", "TERCERA FEB", "LIGA U")
MOVERS_PER_PAIR = 45                    # persons kept for each pair of neighbouring competitions
STAYERS = 40                            # and persons who stayed in one for two seasons in a row
KEEP_COMPETITIONS = ("competition", "league", "gender", "category", "level", "season")


def get(url: str) -> bytes:
    return urllib.request.urlopen(url, timeout=60).read()


def main() -> None:
    manifest = json.loads(get(BASE + "index.json"))
    key = base64.b64decode(manifest["open_key"])
    competitions, rows = {}, []
    for entry in manifest["competitions"]:
        if entry.get("category") != "senior" or entry.get("league") != "feb":
            continue
        env = json.loads(get(BASE + urllib.parse.quote(entry["file"])))
        data = json.loads(open_sealed(env, entry["wraps"], {"abierto": key}))
        competitions[entry["key"]] = {k: entry.get(k) for k in KEEP_COMPETITIONS}
        for r in data["rows"] if isinstance(data, dict) else data:
            if r.get("eligible") and r.get("pct") and all(isinstance(r["pct"].get(a), (int, float)) for a in AXES):
                rows.append({"person_id": r["person_id"], "linked_to": r.get("linked_to"), "comp": entry["key"], "eligible": True, "age": r.get("age"), "minutes": r["minutes"], "pct": {a: r["pct"][a] for a in AXES}})
        time.sleep(0.2)
    family = lambda r: competitions[r["comp"]]["competition"]            # noqa: E731
    season = lambda r: int(competitions[r["comp"]]["season"])            # noqa: E731
    by_person = {}
    for r in rows:
        by_person.setdefault(r.get("linked_to") or r["person_id"], []).append(r)
    chosen = set()
    wanted = (("L.F.-2", "LF CHALLENGE"), ("LF CHALLENGE", "LF ENDESA"), ("SEGUNDA FEB", "PRIMERA FEB"), ("TERCERA FEB", "SEGUNDA FEB"), ("TERCERA FEB", "LIGA U"))
    for a, b in wanted:
        found = sorted(p for p, rs in by_person.items() if any(family(x) == a and family(y) == b and abs(season(x) - season(y)) == 1 for x in rs for y in rs))
        chosen.update(found[:MOVERS_PER_PAIR])
    stay = sorted(p for p, rs in by_person.items() if p not in chosen and any(family(x) == family(y) and season(y) - season(x) == 1 for x in rs for y in rs))
    chosen.update(stay[:STAYERS])
    keep = [r for p in sorted(chosen) for r in by_person[p]]
    keep.sort(key=lambda r: (r.get("linked_to") or r["person_id"], r["comp"], r["person_id"]))
    used = sorted({r["comp"] for r in keep})
    payload = {"captured": "talent-data, 20/11/2026", "competitions": {k: competitions[k] for k in used}, "rows": keep}
    OUT.write_bytes(gzip.compress(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8"), mtime=0))
    print("persons", len(chosen), "rows", len(keep), "competitions", len(used), "bytes", OUT.stat().st_size)


if __name__ == "__main__":
    main()
