"""FEB live-feed recorder (issue #171).

Polls FEB's live endpoints (BoxScore, ShotChart, KeyFacts = play-by-play) during a match and stores
what they serve, with timing, so the live engine can be validated and replayed offline: real
``status`` values, refresh cadence, delay of events (``LogTimeUtc``), token life, and how the match
looks in the public calendar while it is being played.

Output directory (one per match)::

    meta.json          match code, settings and the final run summary
    polls.jsonl        one line per request: time, endpoint, HTTP status, ms, size, sha, changed, headers
    bodies/            gzip-compressed JSON of every response that CHANGED (not the repeats)
    calendar.jsonl     snapshots of the match's row in the calendar page

CLI: ``python -m src.live_prep.recorder record --match CODE [--start-at ISO] [--out DIR]`` and
``plan --watchlist FILE`` (which matches are about to start; used by the scheduled workflow).
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

# The scraper package imports some helpers un-prefixed (``utils...``): ``src`` must be on the path before
# it is imported (``python -m`` jobs in CI do not have pytest's configuration).
_SRC = str(Path(__file__).resolve().parents[1])
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

ENDPOINTS = {
    "boxscore": "https://intrafeb.feb.es/LiveStats.API/api/v1/BoxScore/{match_code}",
    "shotchart": "https://intrafeb.feb.es/LiveStats.API/api/v1/ShotChart/{match_code}",
    "keyfacts": "https://intrafeb.feb.es/LiveStats.API/api/v1/KeyFacts/{match_code}",
}
KEPT_HEADERS = ("date", "etag", "last-modified", "age", "cache-control", "content-length", "server")
FINISHED = "3"


@dataclass
class Response:
    status: int
    headers: Dict[str, str]
    body: bytes


def _kept(headers: Dict[str, str]) -> Dict[str, str]:
    return {k: v for k, v in headers.items() if k.lower() in KEPT_HEADERS}


class Recorder:
    def __init__(
        self,
        match_code: str,
        out_dir: Path,
        get: Callable[[str, str], Response],
        token: Callable[..., Optional[str]],
        *,
        interval: float = 10.0,
        pre_start_s: float = 300.0,
        not_started_interval: float = 60.0,
        max_minutes: float = 210.0,
        tail_polls: int = 3,
        skip_if_finished: bool = False,
        calendar_row: Optional[Callable[[str], Optional[Dict[str, Any]]]] = None,
        calendar_every_s: float = 60.0,
        now: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
        utcnow: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self.code, self.out = match_code, Path(out_dir)
        self._get, self._token = get, token
        self.interval, self.pre_start_s, self.not_started_interval = interval, pre_start_s, not_started_interval
        self.max_minutes, self.tail_polls, self.skip_if_finished = max_minutes, tail_polls, skip_if_finished
        self._calendar_row, self.calendar_every_s = calendar_row, calendar_every_s
        self._now, self._sleep, self._utcnow = now, sleep, utcnow
        self._last_sha: Dict[str, str] = {}
        self._seq = 0
        self._token_value: Optional[str] = None
        self._last_calendar = -1e18
        self.summary: Dict[str, Any] = {"polls": 0, "bodies_saved": 0, "errors": 0, "token_renewals": 0,
                                        "finished": False, "reason": None}

    # -- files --------------------------------------------------------------------------

    def _append(self, name: str, record: Dict[str, Any]) -> None:
        with open(self.out / name, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")

    def _save_body(self, endpoint: str, sha: str, body: bytes) -> None:
        folder = self.out / "bodies"
        folder.mkdir(parents=True, exist_ok=True)
        self._seq += 1
        (folder / f"{self._seq:05d}-{endpoint}-{sha[:8]}.json.gz").write_bytes(gzip.compress(body))
        self.summary["bodies_saved"] += 1

    # -- one request ---------------------------------------------------------------------

    def _request(self, endpoint: str) -> Optional[Response]:
        url = ENDPOINTS[endpoint].format(match_code=self.code)
        started = self._now()
        record: Dict[str, Any] = {"t": self._utcnow().isoformat(), "mono": round(started, 3), "endpoint": endpoint}
        try:
            if self._token_value is None:
                self._token_value = self._token(self.code)
            response = self._get(url, self._token_value)
            if response.status == 401:  # token expired: renew once and retry
                self._token_value = self._token(self.code, force=True)
                self.summary["token_renewals"] += 1
                record["renewed_token"] = True
                response = self._get(url, self._token_value)
        except Exception as exc:  # noqa: BLE001 - network hiccups are data too
            record.update(status=None, error=f"{type(exc).__name__}: {exc}", ms=round((self._now() - started) * 1000))
            self.summary["errors"] += 1
            self._append("polls.jsonl", record)
            self.summary["polls"] += 1
            return None
        sha = hashlib.sha256(response.body).hexdigest()
        changed = response.status == 200 and self._last_sha.get(endpoint) != sha
        record.update(status=response.status, ms=round((self._now() - started) * 1000), size=len(response.body),
                      sha=sha[:16], changed=changed, headers=_kept(response.headers))
        if response.status == 200:
            self._last_sha[endpoint] = sha
            if changed:
                self._save_body(endpoint, sha, response.body)
        self._annotate(endpoint, response, record)
        self._append("polls.jsonl", record)
        self.summary["polls"] += 1
        return response

    @staticmethod
    def _annotate(endpoint: str, response: Response, record: Dict[str, Any]) -> None:
        """Quick facts that make the poll log readable without opening the bodies.

        Every endpoint answers with the same skeleton (HEADER, PLAYBYPLAY, SHOTCHART, ...) with only
        its own section filled, so the facts are read wherever they appear.
        """
        if response.status != 200:
            return
        try:
            doc = json.loads(response.body)
        except ValueError:
            return
        if not isinstance(doc, dict):
            return
        status = (doc.get("HEADER") or {}).get("status")
        if status is not None:
            record["game_status"] = str(status)
        lines = (doc.get("PLAYBYPLAY") or {}).get("LINES") or []
        if lines:
            record["pbp_lines"] = len(lines)
            stamps = [ln.get("LogTimeUtc") for ln in lines if isinstance(ln, dict) and ln.get("LogTimeUtc")]
            if stamps:
                record["last_log_utc"] = max(stamps)
        shots = (doc.get("SHOTCHART") or {}).get("SHOTS") if isinstance(doc.get("SHOTCHART"), dict) else None
        if shots:
            record["shots"] = len(shots)

    # -- main loop -------------------------------------------------------------------------

    def _wait_for_start(self, start_at: Optional[datetime]) -> None:
        if start_at is None:
            return
        target = start_at - timedelta(seconds=self.pre_start_s)
        while True:
            remaining = (target - self._utcnow()).total_seconds()
            if remaining <= 0:
                return
            self._sleep(min(remaining, 600.0))

    def _maybe_calendar(self) -> None:
        if self._calendar_row is None or self._now() - self._last_calendar < self.calendar_every_s:
            return
        self._last_calendar = self._now()
        try:
            row = self._calendar_row(self.code)
        except Exception as exc:  # noqa: BLE001
            row = {"error": str(exc)}
        self._append("calendar.jsonl", {"t": self._utcnow().isoformat(), "row": row})

    def run(self, start_at: Optional[datetime] = None) -> Dict[str, Any]:
        self.out.mkdir(parents=True, exist_ok=True)
        meta = {"match_code": self.code, "interval_s": self.interval, "max_minutes": self.max_minutes,
                "start_at": start_at.isoformat() if start_at else None, "started_utc": self._utcnow().isoformat()}
        self._wait_for_start(start_at)
        if self.skip_if_finished and self._already_finished():
            self.summary.update(finished=True, reason="already_finished")
            return self._close(meta)
        began = self._now()
        tail_left = None
        while True:
            self._maybe_calendar()
            box = self._request("boxscore")
            if box is not None and box.status == 200:
                game_status = json.loads(box.body).get("HEADER", {}).get("status") if box.body else None
                self.summary["game_status"] = str(game_status)
                self._request("shotchart")
                self._request("keyfacts")
                if str(game_status) == FINISHED:
                    self.summary["finished"] = True
                    tail_left = self.tail_polls if tail_left is None else tail_left
                    if tail_left <= 0:
                        self.summary["reason"] = "finished"
                        break
                    tail_left -= 1
            if (self._now() - began) / 60 >= self.max_minutes:
                self.summary["reason"] = "time_limit"
                break
            waiting = box is not None and box.status == 404
            self._sleep(self.not_started_interval if waiting else self.interval)
        return self._close(meta)

    def _already_finished(self) -> bool:
        """One look at the match without recording anything (a queued run after the match ended)."""
        try:
            response = self._get(ENDPOINTS["boxscore"].format(match_code=self.code), self._token(self.code))
            doc = json.loads(response.body) if response.status == 200 and response.body else {}
            return str((doc.get("HEADER") or {}).get("status")) == FINISHED
        except Exception:  # noqa: BLE001 - when in doubt, record
            return False

    def _close(self, meta: Dict[str, Any]) -> Dict[str, Any]:
        self.summary.pop("game_status", None)
        meta["result"] = self.summary
        meta["ended_utc"] = self._utcnow().isoformat()
        (self.out / "meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
        return self.summary


# --- planning: which matches to record right now -------------------------------------------------

PLAN_BEFORE = timedelta(minutes=45)   # start recording up to 45 min before kick-off ...
PLAN_AFTER = timedelta(minutes=30)    # ... and still accept a late scheduler run 30 min after it


def _madrid_to_utc(local_iso: str) -> datetime:
    from zoneinfo import ZoneInfo

    return datetime.fromisoformat(local_iso).replace(tzinfo=ZoneInfo("Europe/Madrid")).astimezone(timezone.utc)


def plan(watch: Dict[str, Any], now: datetime, fetch_calendar: Callable[[str], list], match_status: Callable[[str], str],
         extra_codes: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """Matches of the watchlist that should be recorded now (kick-off within the window, or live).

    ``watch``: ``{"calendar": URL, "matches": [codes], "teams": [ids]}``. Kick-off times come from the
    calendar (Madrid local time). Codes in ``extra_codes`` (manual runs) are recorded immediately.
    """
    out: List[Dict[str, Any]] = [{"code": str(c), "start_at": None, "label": str(c)} for c in extra_codes or []]
    try:
        calendar = fetch_calendar(watch["calendar"])
    except Exception:  # noqa: BLE001 - no calendar, no start times: the next scheduled run tries again
        return out
    codes, teams = set(map(str, watch.get("matches", []))), set(map(str, watch.get("teams", [])))
    for m in calendar:
        if m.code not in codes and not any(m.involves(t) for t in teams):
            continue
        label = f"{m.home_name.strip()} - {m.away_name.strip()}"
        if m.kind == "scheduled" and m.start:
            start = _madrid_to_utc(m.start)
            if start - PLAN_BEFORE <= now <= start + PLAN_AFTER:
                out.append({"code": m.code, "start_at": start.isoformat(), "label": label})
        elif m.kind == "result" and match_status(m.code) == "live":
            out.append({"code": m.code, "start_at": None, "label": label})
    seen, unique = set(), []
    for item in out:
        if item["code"] not in seen:
            seen.add(item["code"])
            unique.append(item)
    return unique


# --- real adapters + CLI ------------------------------------------------------------------------------

def http_get(url: str, token: str) -> Response:
    import requests

    from src.scraper.constants import DEFAULT_HEADERS

    r = requests.get(url, headers={**DEFAULT_HEADERS, "Authorization": f"Bearer {token}"}, timeout=20)
    return Response(r.status_code, dict(r.headers), r.content)


def make_token_provider() -> Callable[..., Optional[str]]:
    import requests

    from src.scraper.token_manager import TokenManager

    manager, session = TokenManager(), requests.Session()

    def token(code: str, force: bool = False) -> Optional[str]:
        if force:
            manager.invalidate_token(code)
        return manager.get_token(code, session)

    return token


def _calendar_row_provider(url: Optional[str], fetch_calendar) -> Optional[Callable[[str], Optional[Dict[str, Any]]]]:
    if not url:
        return None

    def row(code: str) -> Optional[Dict[str, Any]]:
        match = next((m for m in fetch_calendar(url) if m.code == code), None)
        return match.to_dict() if match else None

    return row


def main(argv: Optional[List[str]] = None, fetch_calendar=None, match_status=None, get=None, token=None) -> int:
    from src.scraper.schedule_client import feb_status, http_calendar

    fetch_calendar = fetch_calendar or http_calendar
    match_status = match_status or feb_status
    parser = argparse.ArgumentParser(description="FEB live-feed recorder")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_plan = sub.add_parser("plan", help="print the matches to record now as a GitHub Actions matrix")
    p_plan.add_argument("--watchlist", required=True)
    p_plan.add_argument("--now", help="ISO time (UTC) instead of the current time (tests)")
    p_plan.add_argument("--extra", action="append", default=[], help="match code to record immediately (repeatable)")
    p_rec = sub.add_parser("record", help="record one match")
    p_rec.add_argument("--match", required=True)
    p_rec.add_argument("--start-at", help="ISO kick-off time (UTC); polling is quiet until 5 min before")
    p_rec.add_argument("--out", default="recordings")
    p_rec.add_argument("--calendar", help="calendar URL to snapshot the match row")
    p_rec.add_argument("--interval", type=float, default=10.0)
    p_rec.add_argument("--max-minutes", type=float, default=210.0)
    p_rec.add_argument("--skip-if-finished", action="store_true")
    args = parser.parse_args(argv)

    if args.cmd == "plan":
        now = datetime.fromisoformat(args.now) if args.now else datetime.now(timezone.utc)
        watch = json.loads(Path(args.watchlist).read_text(encoding="utf-8"))
        include = plan(watch, now, fetch_calendar, match_status, args.extra)
        print(json.dumps({"include": include}))
        return 0

    start_at = datetime.fromisoformat(args.start_at) if args.start_at else None
    rec = Recorder(args.match, Path(args.out) / args.match, get or http_get, token or make_token_provider(),
                   interval=args.interval, max_minutes=args.max_minutes, skip_if_finished=args.skip_if_finished,
                   calendar_row=_calendar_row_provider(args.calendar, fetch_calendar))
    result = rec.run(start_at)
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())

