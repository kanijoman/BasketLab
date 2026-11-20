"""Capture REAL ACB pages as fixtures (#886): ``python scripts/capture_acb_fixtures.py``.

Saves under ``tests/fixtures/acb``: the data chunks of the match centre (``live.acb.com``) of two games (``<id>.<tab>.flight.gz``), of the page of a player (``player.<tab>.flight.gz``) and the answers
of the calendar API (``team-matches.json``, ``teams.json``). One request every 2 s and a generic user agent that names no project. The key of the API is the one that the public JavaScript of
acb.com ships to every browser: it is read from there on each run (as a browser does) and is NEVER written anywhere, so none of the fixtures has it. Not run by the CI: the tests read what is committed.
The legal risk of using ACB is open (docs/evaluaciones/2026-11-20_acb-spike-886.md): run it only with the approval of the project owner.
"""
import gzip
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT)]

from src.external.acb_page import extract_flight  # noqa: E402

OUT = ROOT / "tests" / "fixtures" / "acb"
USER_AGENT = "Mozilla/5.0 (compatible; basketball-research-bot/1.0)"
PAUSE_S = 2.0
GAMES = [("real-madrid-vs-unicaja-105383", ("jugadas", "estadisticas")), ("barca-vs-valencia-basket-club-18665", ("jugadas",))]       # 2026/27 and 2019/20
PLAYER = "amine-noua-30001137"
_last = [0.0]


def get(url: str, key: str = "") -> bytes:
    wait = PAUSE_S - (time.monotonic() - _last[0])
    if wait > 0:
        time.sleep(wait)
    _last[0] = time.monotonic()
    headers = {"User-Agent": USER_AGENT, **({"X-APIKEY": key, "Accept": "application/json"} if key else {})}
    return urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=40).read()


def api_key() -> str:
    html = get("https://acb.com/es/liga/equipos/real-madrid-9/partidos?editionId=91").decode("utf-8", "replace")
    for path in sorted(set(re.findall(r"/_next/static/chunks/[A-Za-z0-9_\-\.]+\.js", html))):
        found = re.search(r'apiKey:"([0-9a-f\-]{36})"', get("https://acb.com" + path).decode("utf-8", "replace"))
        if found:
            return found.group(1)
    raise SystemExit("the key was not found in the JavaScript of the site: the format changed")


def save(name: str, flight: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_bytes(gzip.compress(flight.encode("utf-8"), mtime=0))
    print("saved", name, len(flight))


def main() -> None:
    for slug, tabs in GAMES:
        for tab in tabs:
            save(f"{slug.rsplit('-', 1)[1]}.{tab}.flight.gz", extract_flight(get(f"https://live.acb.com/partidos/{slug}/{tab}").decode("utf-8", "replace")))
    for tab in ("temporada", "zonas-de-tiro"):
        save(f"player.{tab}.flight.gz", extract_flight(get(f"https://acb.com/es/liga/jugadores/{PLAYER}/{tab}").decode("utf-8", "replace")))
    key = api_key()
    for name, path in (("team-matches.json", "/api/seasondata/TeamProfile/team-matches?clubId=9&competitionId=1&editionId=91"), ("teams.json", "/api/seasondata/TeamProfile/teams?competitionId=1&editionId=91")):
        (OUT / name).write_text(json.dumps(json.loads(get("https://api2.acb.com" + path, key)), ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
        print("saved", name)


if __name__ == "__main__":
    main()
