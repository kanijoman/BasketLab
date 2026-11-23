"""Capture the real answers of ESPN that the tests of the NCAA source read (#888, D4): ``python scripts/capture_ncaa_fixtures.py``.

Writes ``tests/fixtures/ncaa/*.json.gz``. The list of conferences of a season is kept as it comes. The standings of a season (6,7 MB each, mostly logos, links and stats nobody reads) are cut to what
``src/external/ncaa_page`` reads: the conferences and, in each, the id and name of its teams. Two seasons on purpose: 2025/26 and 2026/27, between which 27 teams changed conference (the realignments of
the summer of 2026), the real case #966 asks for. ESPN answers 403 to a user agent that names a bot: the plain ``Mozilla/5.0`` is what the client sends too.
"""
import gzip
import json
import sys
import urllib.request
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "ncaa"
SITE = "https://site.api.espn.com/apis/site/v2/sports/basketball/{sex}-college-basketball"
STANDINGS = "https://site.api.espn.com/apis/v2/sports/basketball/{sex}-college-basketball/standings?group=50&level=2&season={season}"
SEASONS = (2026, 2027)                       # the ESPN season is the year it ends in: 2026 is 2025/26


def get(url: str) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    return json.loads(urllib.request.urlopen(request, timeout=60).read().decode("utf-8"))


def trimmed_standings(data: dict) -> dict:
    return {"children": [{"id": c["id"], "name": c["name"], "abbreviation": c.get("abbreviation"), "shortName": c.get("shortName"), "isConference": c.get("isConference"),
                          "standings": {"entries": [{"team": {"id": e["team"]["id"], "displayName": e["team"]["displayName"]}} for e in c["standings"]["entries"]]}}
                         for c in data["children"]]}


def write(name: str, data: dict) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{name}.json.gz").write_bytes(gzip.compress(json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8"), mtime=0))


def main() -> int:
    for sex in ("mens", "womens"):
        for season in SEASONS:
            write(f"conferences_{sex}_{season}", get(SITE.format(sex=sex) + f"/scoreboard/conferences?season={season}"))
            write(f"standings_{sex}_{season}", trimmed_standings(get(STANDINGS.format(sex=sex, season=season))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
