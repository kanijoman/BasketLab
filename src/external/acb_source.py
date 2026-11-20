"""The ACB source (#886, D2i of epic #872): what the daily refresh of the external sources registers for ``acb``.

For each entry of the catalogue (an edition of a competition: ``acb.edition_id``) it asks the API for the clubs and for the calendar of each one, keeps the FINISHED games the archive does not have yet and, for each,
reads the box and the play by play of the match centre and the page of every player who took part (his bio and the shots of his season), handing over the canonical document (``acb_canonical``). A game that has
been played never changes, so what is in ``known`` is not asked again and ``since`` does not matter.

* **A budget of requests per run**, the one of the client (``max_requests``, retries included): when it is spent the run stops cleanly and says so, and the next day's run goes on where this one stopped. The
  calendar costs one request per club every run (19 for the Liga Endesa); a game, two pages and the pages of its players not seen yet in the run.
* **A player is asked once per run** (his bio and the shots of the season of the game): the shots page has the whole season, so every game of the run uses it. The bio is asked for who played; the shots, for who
  took a field goal in the game (there is nothing to place for the rest).
* **A page that cannot be had is skipped and said** (``notes``), never a reason to stop the rest: a game without its pages is asked again the next run, a game whose player has no page comes without his bio and
  **without a shot chart** (a chart with some of the shots would make every zone look different, ``acb_canonical``). A site that changed its FORMAT is different: if NONE of the games it asked for could be read,
  the run fails (``AcbPageError``), so that the issue opens instead of a quiet empty archive.
* A game stored before a missing page came back is not asked for again: its bio and its chart stay as they were (a known limit, in the roadmap).
"""
from __future__ import annotations

from typing import AbstractSet, Any, Callable, Dict, Iterator, List, Optional, Tuple

from src.external.acb_canonical import FIELD_GOALS, to_canonical
from src.external.acb_client import AcbBudgetExhausted, AcbClient, AcbFetchError, AcbNotFound
from src.external.acb_page import AcbPageError, parse_game, parse_player, parse_shots
from src.market.canonical import source_id

DEFAULT_BUDGET = 900                         # requests per run: ~15 minutes at one request a second


class AcbSource:
    name = "acb"

    def __init__(self, client: AcbClient) -> None:
        self.client = client
        self.notes: List[str] = []
        self._bios: Dict[Tuple[int, int], Optional[Dict[str, Any]]] = {}
        self._shots: Dict[Tuple[int, int], Optional[List[Dict[str, Any]]]] = {}

    def _calendar(self, edition: int, competition: int) -> List[Dict[str, Any]]:
        matches: Dict[int, Dict[str, Any]] = {}
        for club in self.client.teams(edition, competition):
            for match in self.client.team_matches(club["clubId"], edition, competition):
                matches[match["id"]] = match
        return [matches[i] for i in sorted(matches)]

    def _players(self, game: Dict[str, Any], edition: int, competition: int = 1) -> Tuple[Dict[int, Dict[str, Any]], Dict[int, List[Dict[str, Any]]]]:
        """The bios and the shots of the players of the game (each page once per run). A page that cannot be had is said and its player goes without."""
        taking = {p["player_id"] for p in game["plays"] if p["type"] in FIELD_GOALS}
        bios: Dict[int, Dict[str, Any]] = {}
        shots: Dict[int, List[Dict[str, Any]]] = {}
        for side in ("home", "away"):
            for player in game[side]["players"]:
                if player["seconds"] <= 0 and player["id"] not in taking:
                    continue
                key = (player["id"], edition)
                names = (player.get("first_name") or "", player.get("last_name") or "", player["id"])
                if key not in self._bios:
                    self._bios[key] = self._ask(lambda: parse_player(self.client.player_page(*names, "temporada", edition)), f"player {player['name']}: bio")
                if self._bios[key]:
                    bios[player["id"]] = self._bios[key]
                if player["id"] in taking:
                    if key not in self._shots:
                        self._shots[key] = self._ask(lambda: parse_shots(self.client.player_page(*names, "zonas-de-tiro", edition))["shots"], f"player {player['name']}: shots")
                    if self._shots[key] is not None:
                        shots[player["id"]] = self._shots[key]
        return bios, shots

    def _ask(self, read: Callable[[], Any], what: str) -> Any:
        """The result of ``read``, or ``None`` and a note when the page cannot be had or read; the budget is not for here (it stops the run)."""
        try:
            return read()
        except AcbBudgetExhausted:
            raise
        except (AcbFetchError, AcbPageError) as error:
            self.notes.append(f"{what}: {error}")
            return None

    def fetch(self, entry: Dict[str, Any], since: Optional[str], known: AbstractSet[str]) -> Iterator[Dict[str, Any]]:
        edition, competition = entry["acb"]["edition_id"], entry["acb"]["competition_id"]
        try:
            calendar = self._calendar(edition, competition)
        except AcbBudgetExhausted as error:
            self.notes.append(f"budget: {error}")
            return
        cap = entry["acb"].get("max_games") or len(calendar)
        todo = [m for m in calendar if m.get("matchStatus") == "FINALIZED" and source_id("acb", m["id"]) not in known][:cap]
        failed_format = read = 0
        last_format: Optional[AcbPageError] = None
        for match in todo:
            home, away = match["homeTeam"]["fullName"], match["awayTeam"]["fullName"]
            try:
                game = parse_game(self.client.match_page(home, away, match["id"], "estadisticas"), self.client.match_page(home, away, match["id"], "jugadas"))
                bios, shots = self._players(game, edition, competition)
                doc = to_canonical(game, match, entry, bios=bios, shots=shots)
            except AcbBudgetExhausted as error:
                self.notes.append(f"budget: {error}")
                return
            except AcbNotFound:
                self.notes.append(f"{match['id']}: not found")
                continue
            except AcbFetchError as error:
                self.notes.append(f"{match['id']}: {error}")
                continue
            except AcbPageError as error:
                failed_format += 1
                last_format = error
                self.notes.append(f"{match['id']}: format: {error}")
                continue
            except ValueError as error:                                       # a game that is not finished or whose calendar line is of another: not converted, said
                self.notes.append(f"{match['id']}: {error}")
                continue
            read += 1
            yield doc
        if failed_format and not read and last_format is not None:
            raise last_format                                                  # none of the games that could be asked for could be read: the site changed, it is not a quiet empty run
