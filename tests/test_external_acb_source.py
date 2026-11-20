"""The ACB source (#886, D2i of epic #872): what the daily refresh registers for ``acb``.

It is the real ``AcbClient`` (the pauses and the budget are the client's) over a fake network that serves the REAL pages of ``tests/fixtures/acb``: the clubs and the calendar of the 2026/27 Liga Endesa (the
calendar of Real Madrid, 8 games played), the real box and play by play of Real Madrid - Unicaja (105383) and the real bio and shots of Amine Noua. What the fixtures do not have is a 404, as on the site for a
game that is not there; the pages of the other players are built from the real play by play of the game (the shots) and the real names (the bio), so the complete case can be seen.
"""
import gzip
import json
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

import pytest

from db_helpers import new_mock_db

from src.external import registry
from src.external.acb_client import API_BASE, AcbClient
from src.external.acb_page import parse_game
from src.external.acb_source import DEFAULT_BUDGET, AcbSource
from src.external.refresh import refresh_source
from src.services.competition_catalogue import load_catalogue

FIX = Path(__file__).resolve().parent / "fixtures" / "acb"
NOW = datetime(2026, 11, 20, 7, 0, tzinfo=timezone.utc)
NOUA = 30001137
NOT_FOUND = urllib.error.HTTPError("u", 404, "Not Found", {}, None)


def flight(name):
    return gzip.decompress((FIX / f"{name}.flight.gz").read_bytes()).decode("utf-8")


def html_of(text):
    return f"<html><script>self.__next_f.push([1,{json.dumps(text)}])</script></html>"


GAME = parse_game(flight("105383.estadisticas"), flight("105383.jugadas"))
PLAYERS = {p["id"]: p for side in ("home", "away") for p in GAME[side]["players"]}


def bio_flight(player, birth="01-01-1990"):
    return ('{"player":{"id":%d,"firstName":%s,"lastName":%s,"nickname":%s,"gameRole":%s},"birthDate":"%s","birthPlace":"X","birthCountry":"Y","nationality":"España","height":"1,95","playerNumber":%s}'
            % (player["id"], json.dumps(player["first_name"]), json.dumps(player["last_name"]), json.dumps(player["name"]), json.dumps(player["role"] or "Alero"), birth, json.dumps(int(player["number"]))))


def shots_flight(player):
    """The season shots of a player: one per field goal of his in the real play by play, with coordinates that fall in the zones the real shots of Noua have."""
    spots = {93: (0, -615), 94: (246, -6836), 97: (2901, 2410), 98: (4548, 6074), 100: (0, -300), 533: (0, -300)}
    plays = sorted((p for p in GAME["plays"] if p["player_id"] == player["id"] and p["type"] in spots), key=lambda p: p["order"])
    shots = [{"id": i + 1, "matchId": 105383, "posX": spots[p["type"]][0], "posY": spots[p["type"]][1], "playType": p["type"], "made": p["type"] in (93, 94, 100), "points": 3 if p["type"] in (94, 98) else 2,
              "zone": "paint", "hexQ": 0, "hexR": 0} for i, p in enumerate(plays)]
    return '"seasonShots":' + json.dumps({"competitionId": 1, "editionId": 91, "phaseId": None, "attempts": len(shots), "made": sum(s["made"] for s in shots), "withoutCoordinates": 0, "shots": shots})


class Net:
    """The network: the clubs and the calendar of the real answers, the real pages of the game and of Noua and, if asked, a page for every other player. Everything else is a 404."""

    def __init__(self, everyone=False, calendar_of=None, games=("105383",)):
        self.requests, self.sleeps, self.now = [], [], 0.0
        teams = (FIX / "teams.json").read_text(encoding="utf-8")
        matches = (FIX / "team-matches.json").read_text(encoding="utf-8")
        club = json.loads(teams)["teams"][0]["latest"]["clubId"]
        self.pages = {f"{API_BASE}/api/seasondata/TeamProfile/teams?competitionId=1&editionId=91": teams,
                      f"{API_BASE}/api/seasondata/TeamProfile/team-matches?clubId=9&competitionId=1&editionId=91": calendar_of or matches}
        self.club = club
        if "105383" in games:
            base = "https://live.acb.com/partidos/real-madrid-vs-unicaja-105383"
            self.pages[f"{base}/estadisticas"] = html_of(flight("105383.estadisticas"))
            self.pages[f"{base}/jugadas"] = html_of(flight("105383.jugadas"))
        noua = PLAYERS[NOUA]
        self.pages[self.player_url(noua, "temporada")] = html_of(flight("player.temporada"))
        self.pages[self.player_url(noua, "zonas-de-tiro")] = html_of(flight("player.zonas-de-tiro"))
        if everyone:
            for pid, p in PLAYERS.items():
                if pid != NOUA:
                    self.pages[self.player_url(p, "temporada")] = html_of(bio_flight(p, f"{1 + pid % 28:02d}-{1 + pid % 12:02d}-{1990 + pid % 10}"))
                    self.pages[self.player_url(p, "zonas-de-tiro")] = html_of(shots_flight(p))

    @staticmethod
    def player_url(player, tab):
        from src.external.acb_client import player_url

        return player_url(player["first_name"], player["last_name"], player["id"], tab) + "?editionId=91"

    def fetch(self, url, headers):
        self.requests.append(url)
        if url in self.pages:
            return self.pages[url]
        if "/team-matches?" in url:
            return json.dumps({"matches": []})                                  # the other clubs: nothing in this fixture
        raise NOT_FOUND

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds

    def clock(self):
        return self.now

    def client(self, **kwargs):
        return AcbClient(fetch=self.fetch, sleep=self.sleep, clock=self.clock, api_key=lambda: "00000000-1111-2222-3333-444444444444", **kwargs)

    def asked(self, part):
        return [u for u in self.requests if part in u]


def entry(tmp_path, **over):
    raw = {"competition": "Liga Endesa", "season_label": "2026/2027", "season_value": "2026", "league": "acb", "division": "Liga Endesa", "gender": "M", "active": True,
           "acb": {"competition_id": 1, "edition_id": 91}, "label": "ACB Liga Endesa", **over}
    path = tmp_path / f"competitions-{len(list(tmp_path.glob('competitions-*.json')))}.json"
    path.write_text(json.dumps({"competitions": [raw]}), encoding="utf-8")
    return load_catalogue(path)


@pytest.fixture(autouse=True)
def clean_registry():
    saved = dict(registry.SOURCES)
    registry.SOURCES.clear()
    yield
    registry.SOURCES.clear()
    registry.SOURCES.update(saved)


def fetch(net, tmp_path, known=(), **client):
    source = AcbSource(net.client(**client))
    return source, list(source.fetch(entry(tmp_path)[0], None, frozenset(known)))


class TestTheGames:
    def test_it_reads_the_calendar_and_gives_the_finished_game_it_has_the_pages_of_as_the_canonical_document(self, tmp_path):
        net = Net()
        source, docs = fetch(net, tmp_path)
        assert [d["_id"] for d in docs] == ["acb:105383"] and docs[0]["_league"] == "acb" and docs[0]["HEADER"]["TEAM"][0]["pts"] == "89"
        assert len(net.asked("/teams?")) == 1 and len(net.asked("/team-matches?")) == 18                               # the clubs, and the calendar of each one

    def test_the_games_that_are_not_finished_are_not_asked_for_and_the_ones_without_pages_are_said_not_skipped_silently(self, tmp_path):
        net = Net()
        source, docs = fetch(net, tmp_path)
        asked = {u.split("/partidos/")[1].split("/")[0] for u in net.asked("live.acb.com")}
        assert len(asked) == 8                                                                                            # the 8 games played of the calendar, not the 26 to come
        assert len([n for n in source.notes if "not found" in n]) == 7                                                      # the other players' pages are 404 too: they are said apart

    def test_a_game_it_already_has_is_not_asked_for_again(self, tmp_path):
        net = Net()
        source, docs = fetch(net, tmp_path, known={"acb:105383"})
        assert docs == [] and not [u for u in net.asked("live.acb.com") if "105383" in u]

    def test_the_max_games_of_the_entry_caps_a_run(self, tmp_path):
        net = Net()
        source = AcbSource(net.client())
        docs = list(source.fetch(entry(tmp_path, acb={"competition_id": 1, "edition_id": 91, "max_games": 1})[0], None, frozenset()))
        assert len({u.split("/partidos/")[1].split("/")[0] for u in net.asked("live.acb.com")}) == 1 and len(docs) <= 1


class TestThePlayers:
    def test_the_bio_and_the_shots_are_asked_of_the_players_that_played_and_the_edition_of_the_game_goes_in_the_address(self, tmp_path):
        net = Net()
        fetch(net, tmp_path)
        pages = net.asked("/jugadores/")
        assert pages and all(u.endswith("?editionId=91") for u in pages)
        assert any("amine-noua-30001137/temporada" in u for u in pages) and any("amine-noua-30001137/zonas-de-tiro" in u for u in pages)
        assert not any("zonas-de-tiro" in u and PLAYERS_WITHOUT_SHOTS_IN(u) for u in pages)

    def test_what_the_players_pages_give_is_in_the_document_and_a_player_with_no_page_is_said(self, tmp_path):
        net = Net()
        source, docs = fetch(net, tmp_path)
        noua = next(p for t in docs[0]["BOXSCORE"]["TEAM"] for p in t["PLAYER"] if p["id"] == f"acb:{NOUA}")
        assert (noua["birth"], noua["height"]) == ("1997-02-07", "202")
        other = next(p for p in docs[0]["BOXSCORE"]["TEAM"][0]["PLAYER"])
        assert other["birth"] is None and other["position"]                                                              # no page: no bio, but the position of the box
        assert docs[0]["SHOTCHART"]["SHOTS"] == [] and any("player" in n for n in source.notes)                         # one player's shots do not make a chart

    def test_with_the_pages_of_every_player_the_game_has_a_complete_chart_its_bios_and_it_is_reliable(self, tmp_path):
        net = Net(everyone=True)
        source, docs = fetch(net, tmp_path)
        doc = docs[0]
        assert len(doc["SHOTCHART"]["SHOTS"]) == sum(1 for p in GAME["plays"] if p["type"] in (93, 94, 97, 98, 100, 533)) and all(p["birth"] for t in doc["BOXSCORE"]["TEAM"] for p in t["PLAYER"] if int(p["min"]) > 0)
        assert not [n for n in source.notes if "player" in n]

    def test_a_player_is_asked_once_per_run_whatever_the_games(self, tmp_path):
        net = Net(everyone=True)
        source = AcbSource(net.client())
        source._players(GAME, 91, 1)
        before = len(net.requests)
        source._players(GAME, 91, 1)
        assert len(net.requests) == before


class TestTheBudget:
    def test_a_run_that_spends_its_budget_stops_cleanly_and_says_so(self, tmp_path):
        net = Net(everyone=True)
        source, docs = fetch(net, tmp_path, max_requests=25)                                                              # the calendar alone is 19
        assert len(net.requests) <= 25 and docs == [] and any("budget" in n for n in source.notes)

    def test_the_default_budget_is_a_request_cap_of_the_client(self):
        from src.external import sources

        source = sources.default_source("acb", budget=40)
        assert isinstance(source, AcbSource) and source.client.max_requests == 40 and sources.default_source("acb").client.max_requests == DEFAULT_BUDGET


class TestTheFormat:
    def test_a_site_whose_pages_can_no_longer_be_read_is_a_failed_run_not_a_quiet_empty_one(self, tmp_path):
        net = Net()
        base = "https://live.acb.com/partidos/real-madrid-vs-unicaja-105383"
        net.pages[f"{base}/estadisticas"] = html_of('"statsByPeriods" "initialStatistics":{"matchFinished":true,"teamBoxscores":[]}')          # it has the data of a box, but not its shape
        from src.external.acb_page import AcbPageError

        with pytest.raises(AcbPageError, match="format"):
            fetch(net, tmp_path)


class TestTheRefresh:
    def test_the_daily_refresh_stores_the_game_marks_it_reliable_and_the_second_run_asks_for_no_game(self, tmp_path):
        net = Net(everyone=True)
        registry.register(AcbSource(net.client()))
        db = new_mock_db()
        catalogue = entry(tmp_path)
        status = refresh_source("acb", catalogue, db, tmp_path / "out", NOW)
        assert status["state"] == "ok" and status["games"] == 1 and status["new"] == 1 and status["unreliable"] == 0
        stored = db["ACB_Liga_Endesa_2026_"].find_one({"_id": "acb:105383"})
        assert stored["_reliable"] is True and len(stored["SHOTCHART"]["SHOTS"]) > 100
        before = len(net.asked("live.acb.com"))
        registry.SOURCES.clear()
        registry.register(AcbSource(net.client()))
        refresh_source("acb", catalogue, db, tmp_path / "out", NOW)
        assert len(net.asked("live.acb.com")) == before + 7                                                                 # only the 7 of the calendar that have no page (a 404 is asked again), not the stored one


def PLAYERS_WITHOUT_SHOTS_IN(url):
    """A player who never took a field goal in the game has no shots page asked (nothing to place)."""
    taken = {p["player_id"] for p in GAME["plays"] if p["type"] in (93, 94, 97, 98, 100, 533)}
    for pid, p in PLAYERS.items():
        if f"-{pid}/" in url:
            return pid not in taken
    return False
