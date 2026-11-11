"""Capture the REAL competitions the browser forecast is tested on (#847, #848): ``python scripts/capture_forecast_fixtures.py``.

Reads the local database (read only) and, for the calendar, the federation, and writes ``tests/fixtures/forecast/<name>.json.gz``: the team rows of a competition exactly as the exporter
publishes them (``export_collection``, without the player rows) plus its gender, and the calendar of one competition of the current season as it was that day. The fixtures are real so that
the tests play the situations of a real season (an early season, a complete one, a tie in FBCYL, results the archive does not have yet), not a dict that could describe an unreachable state.
"""
from __future__ import annotations

import gzip
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

OUT = ROOT / "tests" / "fixtures" / "forecast"
# (file, collection, gender): a complete men's season, an early women's season and an early FBCYL group
COMPETITIONS = [("primera_feb_2025_2026", "PRIMERA_FEB_2025_2026_Liga_Regular_Único", "M"),
                ("lf_challenge_2026_2027", "LF_CHALLENGE_2026_2027_Liga_Regular_Único", "F"),
                ("fbcyl_a1_2026", "FBCYL_1ª_FASE-GRUPO_A-1_2026_", "F")]
CALENDAR = ("lf_challenge_2026_2027.calendar", "LF_CHALLENGE_2026_2027_Liga_Regular_Único")


def _write(name: str, payload: dict) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with gzip.open(OUT / f"{name}.json.gz", "wt", encoding="utf-8", compresslevel=9) as f:
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"), default=str)


def main() -> int:
    from src.api import deps
    from src.local_data.calendar_export import CalendarSource, export_calendar
    from src.local_data.export import export_collection

    handler = deps._create_handler()
    db = handler.connection.client["BASKETBALL"]
    for file, collection, gender in COMPETITIONS:
        payload = export_collection(db[collection], collection)
        payload.pop("player_rows", None)
        _write(file, {**payload, "gender": gender})
        print(f"{file}: {payload['games']} games, {len(payload['team_rows'])} rows")
    file, collection = CALENDAR
    calendar = export_calendar(CalendarSource(), handler, collection)
    if calendar is None:
        print("the calendar could not be read", file=sys.stderr)
        return 1
    _write(file, calendar)
    print(f"{file}: {calendar['games']} matches")
    return 0


if __name__ == "__main__":
    sys.exit(main())
