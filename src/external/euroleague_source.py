"""The Euroleague source (#1038, D6a of epic #872): what the daily refresh of the external sources registers for ``euroleague``.

For each entry of the catalogue (a competition of the API, ``euroleague.competition``: ``E`` the EuroLeague, ``U`` the EuroCup or ``J`` the U18 Next Generation Tournament, and the year its season starts in) it
reads the calendar of its season, keeps the PLAYED games the archive does not have yet and, for each, asks for the box (with the bio of the players), the play by play and the shots (three requests), handing
over the canonical document (``euroleague_canonical``). A game that has been played never changes, so what is in ``known`` is not asked again and ``since`` does not matter.

* **The U18 tournaments** are many a season, each with a code of its own (``JTA25``): the entry of a season reads the calendar of every tournament that starts in that year. The code of a game restarts in each
  one, so the id of a game is ``euroleague:<season code>_<game code>`` (``euroleague:E2025_1``).
* **A budget of requests per run**, the one of the client (``max_requests``, retries included): when it is spent the run stops cleanly and says so (once, not once per entry), and the next day's run goes on
  where this one stopped. The first load of a season is about 1,200 requests, so it goes by batches. ``euroleague.max_games`` of an entry caps the games a run asks for of that competition.
* **A page that cannot be had is skipped and said** (``notes``), never a reason to stop the rest: the game is asked again the next run. A site that changed its FORMAT is different: if NONE of the games it asked
  for could be read, the run fails (``EuroleaguePageError``), so that the issue opens instead of a quiet empty archive.
"""
from __future__ import annotations

from typing import AbstractSet, Any, Dict, Iterator, List, Optional

from src.external.euroleague_canonical import to_canonical
from src.external.euroleague_client import EuroleagueBudgetExhausted, EuroleagueClient, EuroleagueFetchError, EuroleagueNotFound
from src.external.euroleague_page import EuroleaguePageError
from src.market.canonical import source_id

DEFAULT_BUDGET = 1300                        # requests per run: ~11 minutes at a request every half second, a little over a season of the EuroLeague


class EuroleagueSource:
    name = "euroleague"

    def __init__(self, client: EuroleagueClient) -> None:
        self.client = client
        self.notes: List[str] = []
        self.complete = True

    @staticmethod
    def game_id(line: Dict[str, Any]) -> str:
        """``euroleague:E2025_1``: the code of a game restarts in each season (and in each U18 tournament), so the id carries the season code."""
        return source_id("euroleague", f"{line['season_code']}_{line['game_code']}")

    def _stop(self, error: Exception) -> None:
        if self.complete:                       # once per run: the entries after the first one only repeat it
            self.notes.append(f"budget: {error}")
        self.complete = False

    def _seasons(self, entry: Dict[str, Any]) -> List[str]:
        """The codes of the seasons of the entry: ``E2025`` and ``U2025`` are one each; the U18 tournaments of a year are as many as the API lists."""
        code, year = entry["euroleague"]["competition"], int(entry["season_value"])
        if code != "J":
            return [f"{code}{year}"]
        return [s["code"] for s in self.client.seasons(code) if s["year"] == year]

    def _played(self, competition: str, season: str, known: AbstractSet[str]) -> List[Dict[str, Any]]:
        """The played games of a season the archive does not have; a season the API does not have says so and gives none."""
        try:
            calendar = self.client.games(competition, season)
        except EuroleagueBudgetExhausted:
            raise
        except EuroleagueNotFound:
            self.notes.append(f"{season}: not found")
            return []
        except EuroleagueFetchError as error:
            self.notes.append(f"{season}: {error}")
            return []
        return [g for g in calendar if g["played"] and self.game_id(g) not in known]

    def fetch(self, entry: Dict[str, Any], since: Optional[str], known: AbstractSet[str]) -> Iterator[Dict[str, Any]]:
        competition, cap = entry["euroleague"]["competition"], entry["euroleague"].get("max_games")
        failed_format = read = 0
        last_format: Optional[EuroleaguePageError] = None
        try:
            for season in self._seasons(entry):
                for line in self._played(competition, season, known):
                    if cap is not None and read >= cap:
                        return
                    try:
                        game = self.client.game(competition, line)
                    except EuroleagueBudgetExhausted:
                        raise
                    except EuroleagueNotFound:
                        self.notes.append(f"{self.game_id(line)}: not found")
                        continue
                    except EuroleagueFetchError as error:
                        self.notes.append(f"{self.game_id(line)}: {error}")
                        continue
                    except EuroleaguePageError as error:
                        failed_format += 1
                        last_format = error
                        self.notes.append(f"{self.game_id(line)}: format: {error}")
                        continue
                    read += 1
                    yield to_canonical(game, entry)
        except EuroleagueBudgetExhausted as error:
            self._stop(error)
            return
        if failed_format and not read and last_format is not None:
            raise last_format                                              # none of the games that could be asked for could be read: the site changed, it is not a quiet empty run
