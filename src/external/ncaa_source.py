"""The NCAA source (#888, D4 of epic #872): what the daily refresh of the external sources registers for ``ncaa``.

For each entry of the catalogue (a conference, a season and a sex) it reads the scoreboards of the days of the season, keeps the FINISHED games that belong to its conference the archive does not have
yet and asks for each one, handing over the canonical document (``ncaa_canonical``).

* **Which conference owns a game** (decided on 23/11/2026): a game between two conferences is stored ONCE, in the competition of the HOME team; when the home team is not Division I, in the one of the
  visitor; a game with no Division I team belongs to nobody. The game is kept complete: its teams, the box of both and every play, with the conference each team played in that day.
* **The days**: the first time the whole season (from 25 October to 20 April, never beyond today); later ones from the date the refresh gives (the last good run minus the rewrite window). The scoreboard of
  a day is read ONCE per run for every conference of the same sex.
* **A budget of requests per run** (the client's): the first load of a season is thousands of games, so it goes by batches. When it is spent the source stops, keeps what it had and says it is NOT
  ``complete``: the refresh does not move the date the next run starts from, so no day is skipped; what is already stored is in ``known`` and is not asked for again.
* **A game that cannot be had is skipped and said** (``notes``), never a reason to stop the rest. A site that changed its FORMAT is different: if NONE of the games could be read the run fails
  (``NcaaPageError``), so that the issue opens instead of a quiet empty archive. A scoreboard that cannot be read stops the run (``NcaaFetchError``): it is not an empty day.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import AbstractSet, Any, Callable, Dict, Iterator, List, Optional, Tuple

from src.external.ncaa_canonical import to_canonical
from src.external.ncaa_client import NcaaBudgetExhausted, NcaaClient, NcaaFetchError, NcaaNotFound
from src.external.ncaa_page import NcaaPageError
from src.market.canonical import source_id

DEFAULT_BUDGET = 1200                          # requests per run: ~20 minutes at one request a second
SEASON_FIRST_DAY = (10, 25)                    # the exhibitions and the first games of the season
SEASON_LAST_DAY = (4, 20)                      # after the Final Four of both sexes


class NcaaSource:
    name = "ncaa"

    def __init__(self, client: NcaaClient, today: Optional[Callable[[], date]] = None) -> None:
        self.client, self.today = client, today or date.today
        self.notes: List[str] = []
        self.complete = True
        self._boards: Dict[Tuple[str, date], List[Dict[str, Any]]] = {}
        self._names: Dict[Tuple[str, int], Dict[str, str]] = {}

    @staticmethod
    def owner(game: Dict[str, Any]) -> Optional[str]:
        """The conference whose competition keeps the game: the one of the home team, or the visitor's when the home team is not Division I; ``None`` when neither is."""
        by_side = sorted(game["teams"], key=lambda t: not t["home"])          # the home team first
        return next((t["conference_id"] for t in by_side if t["conference_id"]), None)

    def _stop(self, error: Exception) -> None:
        if self.complete:                       # once per run: the entries after the first one only repeat it (#1073)
            self.notes.append(f"budget: {error}")
        self.complete = False

    def _board(self, sex: str, day: date) -> List[Dict[str, Any]]:
        if (sex, day) not in self._boards:
            self._boards[(sex, day)] = self.client.scoreboard(sex, day.isoformat())
        return self._boards[(sex, day)]

    def _conference_names(self, sex: str, season: int) -> Dict[str, str]:
        if (sex, season) not in self._names:
            try:
                self._names[(sex, season)] = {c["id"]: c["name"] for c in self.client.conferences(sex, season)}
            except NcaaBudgetExhausted:
                raise
            except NcaaFetchError as error:
                self.notes.append(f"conferences {sex} {season}: {error}")
                self._names[(sex, season)] = {}
        return self._names[(sex, season)]

    def fetch(self, entry: Dict[str, Any], since: Optional[str], known: AbstractSet[str]) -> Iterator[Dict[str, Any]]:
        sex, season, conference = entry["gender"], int(entry["season_value"]), entry["ncaa"]["conference_id"]
        try:
            names = self._conference_names(sex, season)
        except NcaaBudgetExhausted as error:
            self._stop(error)
            return
        day = date(season, *SEASON_FIRST_DAY)
        if since:
            day = max(day, date.fromisoformat(since))
        last = min(date(season + 1, *SEASON_LAST_DAY), self.today())
        failed_format = read = 0
        last_format: Optional[NcaaPageError] = None
        while day <= last:
            try:
                board = self._board(sex, day)
            except NcaaBudgetExhausted as error:
                self._stop(error)
                return
            for listed in board:
                if not listed["finished"] or self.owner(listed) != conference or source_id("ncaa", listed["game_id"]) in known:
                    continue
                try:
                    game = self.client.game(sex, listed["game_id"])
                except NcaaBudgetExhausted as error:
                    self._stop(error)
                    return
                except NcaaNotFound:
                    self.notes.append(f"{listed['game_id']}: not found")
                    continue
                except NcaaFetchError as error:
                    self.notes.append(f"{listed['game_id']}: {error}")
                    continue
                except NcaaPageError as error:
                    failed_format += 1
                    last_format = error
                    self.notes.append(f"{listed['game_id']}: format: {error}")
                    continue
                read += 1
                yield to_canonical(game, entry, names)
            day += timedelta(days=1)
        if failed_format and not read and last_format is not None:
            raise last_format                                              # none of the games that could be asked for could be read: the site changed, it is not a quiet empty run
