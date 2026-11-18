"""The FIBA source (#887, D3b of epic #872): what the daily refresh of the external sources registers for ``fiba``.

For each entry of the catalogue (a FIBA event: ``fiba.event``) it asks the event for its games, keeps the FINISHED ones the archive does not have yet and reads the page of each with the polite client
(``fiba_client``), handing over the canonical document (``fiba_canonical``). A game that has been played never changes, so what is in ``known`` is not asked again and ``since`` does not matter.

* **A budget per run** (``budget``, shared by every entry of the run; and ``fiba.max_games`` per entry): the first load of an event is ~56 requests and of a season, hundreds. A run asks for at most that many
  games, at the pause of the client (one every 2 s), and the next day's run goes on where it stopped.
* **A game that cannot be had is skipped and said** (``notes``: the status of the run keeps them), never a reason to stop the rest. A site that changed its FORMAT is different: if NONE of the pages that came back can be
  read, the run fails (``FibaPageError``), so that the issue opens instead of a quiet empty archive.
* An event that cannot be listed fails the run (``FibaFetchError``): the archive stays as it was and the status keeps its last good run.
* The gender of the entry must be the one of the page: a woman's event under a men's entry is skipped, not published as the other sex.
"""
from __future__ import annotations

from typing import AbstractSet, Any, Dict, Iterator, List, Optional

from src.external.fiba_canonical import gender_of, to_canonical
from src.external.fiba_client import FibaClient, FibaFetchError, FibaNotFound
from src.external.fiba_page import FibaPageError
from src.market.canonical import source_id

DEFAULT_BUDGET = 300                           # games per run: ~10 minutes at one request every 2 s


class FibaSource:
    name = "fiba"
    refetch_filter = {"BOXSCORE.TEAM.PLAYER.birth": {"$exists": False}}          # games stored before the bio of the players was kept (#887, D3b-2) are asked for once more

    def __init__(self, client: FibaClient, budget: int = DEFAULT_BUDGET) -> None:
        self.client, self.remaining = client, budget
        self.notes: List[str] = []

    def fetch(self, entry: Dict[str, Any], since: Optional[str], known: AbstractSet[str]) -> Iterator[Dict[str, Any]]:
        event = entry["fiba"]["event"]
        cap = min(self.remaining, entry["fiba"].get("max_games") or self.remaining)
        todo = [g for g in self.client.event_games(event) if g["finished"] and source_id("fiba", g["game_id"]) not in known][:cap]
        failed_format = read = 0
        last_format: Optional[FibaPageError] = None
        for listed in todo:
            self.remaining -= 1
            try:
                game = self.client.game(event, listed["slug"])
            except FibaNotFound:
                self.notes.append(f"{listed['slug']}: not found")
                continue
            except FibaFetchError as error:
                self.notes.append(f"{listed['slug']}: {error}")
                continue
            except FibaPageError as error:
                failed_format += 1
                last_format = error
                self.notes.append(f"{listed['slug']}: format: {error}")
                continue
            read += 1
            try:
                page_gender = gender_of(game["competition"])
            except ValueError as error:
                self.notes.append(f"{listed['slug']}: {error}")
                continue
            if page_gender != entry["gender"]:
                self.notes.append(f"{listed['slug']}: gender: the page says {game['competition']['gender']}, the entry {entry['gender']}")
                continue
            yield to_canonical(game)
        if failed_format and not read and last_format is not None:
            raise last_format                                              # none of the pages that could be asked for could be read: the site changed, it is not a quiet empty run
