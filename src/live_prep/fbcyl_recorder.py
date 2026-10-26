"""FBCYL live recorder (issue #444, spike of the epic #435): does FBCYL publish a match WHILE it is played?

The calendar of a group (ESB API, Base64) has a row per match: ``state`` (0 to play, 1 played), ``isLive``, ``matchDay`` (kick-off, Madrid), ``matchStartedHour`` and
a ``universallyid`` that exists once the match has data. With it, ``getJsonWithMatchMoves`` (the play-by-play) and ``getJsonWithMatchStats`` answer. In eleven finished matches every
move is stamped within 12 s of the others, right after the end: this recorder watches the next one to prove whether anything is served during the game.

Output directory (one per match), the same layout as ``recorder.py``::

    meta.json       the match, the settings and the final run summary
    polls.jsonl     one line per request: time, endpoint, status, ms, size, sha, changed, headers, moves/period read from the body
    bodies/         gzip-compressed JSON of every response that CHANGED
    calendar.jsonl  the row of the match in the calendar, with the time, every minute

CLI: ``python -m src.live_prep.fbcyl_recorder plan --watchlist config/fbcyl_watchlist.json`` and ``record --group G --home ID --away ID``.
"""

from __future__ import annotations

import argparse
import base64
import gzip
import hashlib
import json
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .recorder import Response, _kept

API = "https://esb.optimalwayconsulting.com/fbcyl/1/jR4rgA5K6Chhh5vyfrxo9wTScdg2NT7K/FCBQWeb/getAllGamesByGrupWithMatchRecords/{group}/0"
STATS = "https://msstats.optimalwayconsulting.com/v1/fbcyl"
ENDPOINTS = {"moves": STATS + "/getJsonWithMatchMoves/{uuid}", "stats": STATS + "/getJsonWithMatchStats/{uuid}?currentSeason=true"}
KEPT_ROW = ("universallyid", "state", "isLive", "matchDay", "dayTime", "localScore", "visitorScore", "matchStartedHour", "idMatch")
PLAN_BEFORE, PLAN_AFTER = timedelta(hours=3), timedelta(hours=2)     # as the FEB recorder: a job launched up to 3 h ahead waits for the start


def calendar_rows(text: str) -> List[Dict[str, Any]]:
    """The matches of a group calendar answer (Base64 JSON), each with its ``round`` and ``round_date``; nothing when the answer is not a good one."""
    try:
        data = json.loads(base64.b64decode(text).decode("utf-8"))
        if data.get("result") != "OK":
            return []
        rounds = data["messageData"]["rounds"]
        return [with_round(m, number, r.get("date")) for number, r in rounds.items() for m in (r.get("matches") or {}).values()]
    except (ValueError, KeyError, TypeError, AttributeError):
        return []


def with_round(row: Dict[str, Any], number: str, date: Optional[str]) -> Dict[str, Any]:
    return {**row, "round": number, "round_date": date}


def _kick_off(row: Dict[str, Any]) -> Optional[datetime]:
    from zoneinfo import ZoneInfo

    day = row.get("matchDay")
    if not day:
        return None
    return datetime.fromisoformat(str(day)).replace(tzinfo=ZoneInfo("Europe/Madrid")).astimezone(timezone.utc)


def plan(watch: Dict[str, Any], now: datetime, fetch_rows: Callable[[str], List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    """The matches to record now: not played yet, with the kick-off close (or being played), of the watched teams (every team when none is named)."""
    teams = {str(t) for t in watch.get("teams") or []}
    out: List[Dict[str, Any]] = []
    for group in watch.get("groups") or []:
        try:
            rows = fetch_rows(str(group))
        except Exception:  # noqa: BLE001 - one unreachable group must not hide the others
            continue
        for row in rows:
            if teams and not ({str(row.get("idLocalTeam")), str(row.get("idVisitorTeam"))} & teams):
                continue
            start = _kick_off(row)
            live = bool(row.get("isLive"))
            near = start is not None and start - PLAN_BEFORE <= now <= start + PLAN_AFTER
            if str(row.get("state")) == "0" and (near or live) or (live and str(row.get("state")) != "1"):
                out.append({"key": f"{group}-{row.get('idLocalTeam')}-{row.get('idVisitorTeam')}", "group": str(group), "home_id": str(row["idLocalTeam"]),
                            "away_id": str(row["idVisitorTeam"]), "start_at": start.isoformat() if start else None,
                            "label": f"{str(row.get('nameLocalTeam')).strip()} - {str(row.get('nameVisitorTeam')).strip()}"})
    return out


class FbcylRecorder:
    def __init__(self, group: str, home_id: str, away_id: str, out_dir: Path, get: Callable[[str], Response], *, interval: float = 10.0, calendar_every_s: float = 60.0,
                 max_minutes: float = 170.0, max_wait_minutes: float = 180.0, tail_polls: int = 3, skip_if_finished: bool = False,
                 now: Callable[[], float] = time.monotonic, sleep: Callable[[float], None] = time.sleep,
                 utcnow: Callable[[], datetime] = lambda: datetime.now(timezone.utc)) -> None:
        self.group, self.home, self.away, self.out, self._get = group, str(home_id), str(away_id), Path(out_dir), get
        self.interval, self.calendar_every_s, self.max_minutes, self.max_wait_minutes = interval, calendar_every_s, max_minutes, max_wait_minutes
        self.tail_polls, self.skip_if_finished, self._now, self._sleep, self._utcnow = tail_polls, skip_if_finished, now, sleep, utcnow
        self._sha: Dict[str, str] = {}
        self._seq = 0
        self.summary: Dict[str, Any] = {"polls": 0, "bodies_saved": 0, "errors": 0, "finished": False, "reason": None, "uuid": None}

    # -- files -------------------------------------------------------------------------------------

    def _append(self, name: str, record: Dict[str, Any]) -> None:
        with open(self.out / name, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")

    def _save(self, endpoint: str, sha: str, body: bytes) -> None:
        folder = self.out / "bodies"
        folder.mkdir(parents=True, exist_ok=True)
        self._seq += 1
        (folder / f"{self._seq:05d}-{endpoint}-{sha[:8]}.json.gz").write_bytes(gzip.compress(body))
        self.summary["bodies_saved"] += 1

    # -- the calendar --------------------------------------------------------------------------------

    def _row(self) -> Optional[Dict[str, Any]]:
        try:
            response = self._get(API.format(group=self.group))
            rows = calendar_rows(response.body.decode("utf-8", "replace")) if response.status == 200 else []
        except Exception as exc:  # noqa: BLE001
            self._append("calendar.jsonl", {"t": self._utcnow().isoformat(), "error": f"{type(exc).__name__}: {exc}"})
            return None
        row = next((r for r in rows if str(r.get("idLocalTeam")) == self.home and str(r.get("idVisitorTeam")) == self.away), None)
        self._append("calendar.jsonl", {"t": self._utcnow().isoformat(), "row": {k: row.get(k) for k in KEPT_ROW} if row else None})
        return row

    # -- one endpoint --------------------------------------------------------------------------------

    def _poll(self, endpoint: str, uuid: str) -> None:
        started = self._now()
        record: Dict[str, Any] = {"t": self._utcnow().isoformat(), "mono": round(started, 3), "endpoint": endpoint}
        try:
            response = self._get(ENDPOINTS[endpoint].format(uuid=uuid))
        except Exception as exc:  # noqa: BLE001 - network hiccups are data too
            record.update(status=None, error=f"{type(exc).__name__}: {exc}")
            self.summary["errors"] += 1
        else:
            sha = hashlib.sha256(response.body).hexdigest()
            changed = response.status == 200 and self._sha.get(endpoint) != sha
            record.update(status=response.status, ms=round((self._now() - started) * 1000), size=len(response.body), sha=sha[:16], changed=changed, headers=_kept(response.headers))
            if response.status == 200:
                self._sha[endpoint] = sha
                if changed:
                    self._save(endpoint, sha, response.body)
                record.update(self._facts(endpoint, response.body))
        self._append("polls.jsonl", record)
        self.summary["polls"] += 1

    @staticmethod
    def _facts(endpoint: str, body: bytes) -> Dict[str, Any]:
        """What makes a poll readable without opening its body: how many moves, which period."""
        try:
            doc = json.loads(body)
        except ValueError:
            return {}
        if endpoint == "moves" and isinstance(doc, list):
            return {"n_moves": len(doc), "last_period": doc[-1].get("period") if doc and isinstance(doc[-1], dict) else None}
        if endpoint == "stats" and isinstance(doc, dict):
            return {"period": doc.get("period"), "stats_time": doc.get("time"), "n_moves": len(doc.get("moves") or [])}
        return {}

    # -- the run -------------------------------------------------------------------------------------

    def run(self) -> Dict[str, Any]:
        self.out.mkdir(parents=True, exist_ok=True)
        meta = {"group": self.group, "home_id": self.home, "away_id": self.away, "interval_s": self.interval, "started_utc": self._utcnow().isoformat()}
        uuid = self._wait_for_the_match()
        if uuid:
            self._record(uuid)
        meta.update(result=self.summary, ended_utc=self._utcnow().isoformat())
        (self.out / "meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
        return self.summary

    def _wait_for_the_match(self) -> Optional[str]:
        """Watches the calendar until the match has an id; None (with the reason) when it was already played or never starts."""
        began, first = self._now(), True
        while True:
            row = self._row()
            if row and first and self.skip_if_finished and str(row.get("state")) == "1":
                self.summary.update(finished=True, reason="already_finished")
                return None
            first = False
            if row and row.get("universallyid"):
                self.summary["uuid"] = row["universallyid"]
                return row["universallyid"]
            if (self._now() - began) / 60 >= self.max_wait_minutes:
                self.summary["reason"] = "never_started"
                return None
            self._sleep(self.calendar_every_s)

    def _record(self, uuid: str) -> None:
        began, last_calendar, tail = self._now(), self._now(), None
        while True:
            self._poll("moves", uuid)
            self._poll("stats", uuid)
            if self._now() - last_calendar >= self.calendar_every_s:
                last_calendar = self._now()
                row = self._row()
                if row and str(row.get("state")) == "1":
                    self.summary["finished"] = True
                    tail = self.tail_polls if tail is None else tail
            if tail is not None:
                if tail <= 0:
                    self.summary["reason"] = "finished"
                    return
                tail -= 1
            if (self._now() - began) / 60 >= self.max_minutes:
                self.summary["reason"] = "time_limit"
                return
            self._sleep(self.interval)


# --- real adapters + CLI --------------------------------------------------------------------------------------

def http_get(url: str) -> Response:
    import requests

    r = requests.get(url, timeout=20)
    return Response(r.status_code, dict(r.headers), r.content)


def main(argv: Optional[List[str]] = None, get: Optional[Callable[[str], Response]] = None) -> int:
    get = get or http_get
    parser = argparse.ArgumentParser(description="FBCYL live recorder (spike #444)")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_plan = sub.add_parser("plan", help="print the matches to record now as a GitHub Actions matrix")
    p_plan.add_argument("--watchlist", required=True)
    p_plan.add_argument("--now", help="ISO time (UTC) instead of the current time (tests)")
    p_rec = sub.add_parser("record", help="record one match")
    p_rec.add_argument("--group", required=True)
    p_rec.add_argument("--home", required=True)
    p_rec.add_argument("--away", required=True)
    p_rec.add_argument("--out", default="recordings")
    p_rec.add_argument("--interval", type=float, default=10.0)
    p_rec.add_argument("--max-minutes", type=float, default=170.0)
    p_rec.add_argument("--max-wait-minutes", type=float, default=180.0)
    p_rec.add_argument("--skip-if-finished", action="store_true")
    args = parser.parse_args(argv)

    if args.cmd == "plan":
        now = datetime.fromisoformat(args.now) if args.now else datetime.now(timezone.utc)
        watch = json.loads(Path(args.watchlist).read_text(encoding="utf-8"))
        print(json.dumps({"include": plan(watch, now, lambda group: calendar_rows(get(API.format(group=group)).body.decode("utf-8", "replace")))}))
        return 0
    recorder = FbcylRecorder(args.group, args.home, args.away, Path(args.out) / f"fbcyl-{args.group}-{args.home}-{args.away}", get, interval=args.interval,
                             max_minutes=args.max_minutes, max_wait_minutes=args.max_wait_minutes, skip_if_finished=args.skip_if_finished)
    print(json.dumps(recorder.run()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
