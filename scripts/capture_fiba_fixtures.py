"""Capture REAL FIBA game pages as fixtures (#887): ``python scripts/capture_fiba_fixtures.py EVENT/GAME [EVENT/GAME ...]`` (e.g. ``fiba-u18-eurobasket-2025/125809-FRA-AUT``).

Each page is downloaded from the public match centre of FIBA (one request every 2 s, an identifiable user agent, no key), its data chunks are joined (``fiba_page.extract_flight``) and saved as
``tests/fixtures/fiba/<gameId>.flight.gz`` (gzip without a timestamp: the file is byte-identical if the page is). ``--event EVENT`` saves the page of an event instead (the real example of a page with no game data).
Not run by the CI: the tests read what is committed. A page that comes back generic is retried (up to 4 times) and, if it persists, skipped with a message.
"""
import gzip
import re
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT)]

from src.external.fiba_page import FibaPageError, extract_flight  # noqa: E402

OUT = ROOT / "tests" / "fixtures" / "fiba"
USER_AGENT = "Mozilla/5.0 (compatible; basketball-research-bot/1.0)"      # generic: no name of the project goes to an outside service
PAUSE_S = 2


def fetch(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    return urllib.request.urlopen(request, timeout=40).read().decode("utf-8", "replace")


def save(name: str, flight: str) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{name}.flight.gz"
    path.write_bytes(gzip.compress(flight.encode("utf-8"), compresslevel=9, mtime=0))
    return path


def main(argv) -> int:
    if not argv:
        print(__doc__)
        return 2
    event_page = argv[0] == "--event"
    targets = argv[1:] if event_page else argv
    for target in targets:
        time.sleep(PAUSE_S)
        event, _, game = target.partition("/")
        url = f"https://www.fiba.basketball/en/events/{event}" + ("" if event_page else f"/games/{game}")
        for attempt in range(1, 5):
            try:
                flight = extract_flight(fetch(url))
            except (FibaPageError, OSError) as error:
                print(f"{target}: attempt {attempt} failed: {error}")
                time.sleep(PAUSE_S * attempt)
                continue
            if event_page or '"gameDetails"' in flight:
                name = re.sub(r"[^A-Za-z0-9_-]", "_", event) if event_page else game.split("-")[0]
                print(f"{target}: saved {save(name, flight).relative_to(ROOT)} ({len(flight) // 1024} KB of data)")
                break
            print(f"{target}: attempt {attempt} came back generic")
            time.sleep(PAUSE_S * attempt)
        else:
            print(f"{target}: SKIPPED, the page stayed generic")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
