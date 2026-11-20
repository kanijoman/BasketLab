"""The link of the players of ACB to the person of FEB (#886, D2h of epic #872): by the date of birth AND at least two words of the name, as FIBA's (``identity_link.link_players``), over the REAL game of
``tests/fixtures/acb`` (Real Madrid - Unicaja, 23 players).

ACB writes the players with the name they are known by («Facu Campazzo», «Edy Tavares») and FEB with the one of their papers («FACUNDO CAMPAZZO», «WALTER TAVARES»): the page of the player also says his first
name and surname, and the canonical document carries both (``name`` and ``full_name``) so that the link has the words of each. The birth dates are made up for the test (the page of a player is one request per
player and the fixture has Noua's only); the names, and the way ACB and FEB write them, are the real ones.
"""
import gzip
import json
import unicodedata
from pathlib import Path

import pytest

from src.external.acb_canonical import to_canonical
from src.external.acb_page import parse_game, parse_player
from src.market.identity_link import external_players, link_players

FIX = Path(__file__).resolve().parent / "fixtures" / "acb"
ENTRY = {"competition": "Liga Endesa", "season_value": "2026", "season_label": "2026/2027", "league": "acb", "gender": "M", "acb": {"competition_id": 1, "edition_id": 91}}


def flight(name):
    return gzip.decompress((FIX / f"{name}.flight.gz").read_bytes()).decode("utf-8")


def plain(text):
    return "".join(c for c in unicodedata.normalize("NFKD", text.upper()) if not unicodedata.combining(c))


@pytest.fixture(scope="module")
def game():
    return parse_game(flight("105383.estadisticas"), flight("105383.jugadas"))


@pytest.fixture(scope="module")
def players(game):
    return [p for side in ("home", "away") for p in game[side]["players"]]


@pytest.fixture(scope="module")
def doc(game, players):
    match = next(m for m in json.loads((FIX / "team-matches.json").read_text(encoding="utf-8"))["matches"] if m["id"] == 105383)
    bios = {p["id"]: {"birth": f"{1990 + i % 12}-{1 + i % 12:02d}-{1 + i:02d}", "height_cm": 190 + i, "nationality": "España"} for i, p in enumerate(players)}
    bios[30001137] = parse_player(flight("player.temporada"))                         # Noua's is the real one
    return to_canonical(game, match, ENTRY, bios=bios)


def feb_rows(players, doc, name_of):
    """The roster rows FEB would have for these players: the same birth, the name written FEB's way."""
    births = {p["id"]: p["birth"] for t in doc["BOXSCORE"]["TEAM"] for p in t["PLAYER"]}
    return [{"person_id": f"feb:{900 + i}", "name": name_of(p), "birth": births[f"acb:{p['id']}"]} for i, p in enumerate(players)]


class TestTheNames:
    def test_the_document_carries_the_name_acb_shows_and_the_one_of_the_page_of_the_player(self, doc):
        campazzo = next(p for t in doc["BOXSCORE"]["TEAM"] for p in t["PLAYER"] if p["name"] == "Facu Campazzo")
        assert campazzo["full_name"] == "Facundo Campazzo"
        assert all(p["full_name"] for t in doc["BOXSCORE"]["TEAM"] for p in t["PLAYER"])

    def test_the_players_with_a_birth_are_the_ones_to_link_and_they_carry_both_names(self, doc):
        found = external_players([doc])
        assert len(found) == 23 and all(p["id"].startswith("acb:") and p["birth"] and p["full_name"] for p in found)


class TestTheLink:
    def test_every_player_whose_name_in_feb_is_his_papers_name_is_linked_to_his_own_person(self, players, doc):
        rows = feb_rows(players, doc, lambda p: plain(f"{p['first_name']} {p['last_name']}"))
        links = {l["external"]: l for l in link_players(rows, external_players([doc]))}
        assert len(links) == 23 and all(l["status"] == "linked" for l in links.values())
        assert all(links[f"acb:{p['id']}"]["feb"] == r["person_id"] for p, r in zip(players, rows))

    def test_the_name_acb_shows_is_enough_when_it_shares_two_words_with_feb_and_the_papers_name_when_it_does_not(self, players, doc):
        """«Facu Campazzo» against «FACUNDO CAMPAZZO» shares one word: only the first name of the page makes it two."""
        campazzo = next(p for p in players if p["name"] == "Facu Campazzo")
        rows = [{"person_id": "feb:1", "name": "FACUNDO CAMPAZZO", "birth": next(q["birth"] for t in doc["BOXSCORE"]["TEAM"] for q in t["PLAYER"] if q["id"] == f"acb:{campazzo['id']}")}]
        only_nickname = [{**p, "full_name": None} for p in external_players([doc]) if p["id"] == f"acb:{campazzo['id']}"]
        assert link_players(rows, only_nickname)[0]["status"] == "review"
        assert link_players(rows, [p for p in external_players([doc]) if p["id"] == f"acb:{campazzo['id']}"])[0]["status"] == "linked"

    def test_a_player_with_the_same_birth_as_another_person_of_feb_but_no_name_in_common_is_not_linked(self, players, doc):
        row = [{"person_id": "feb:1", "name": "JUAN PEREZ GARCIA", "birth": next(q["birth"] for t in doc["BOXSCORE"]["TEAM"] for q in t["PLAYER"] if q["id"] == f"acb:{players[0]['id']}")}]
        assert link_players(row, external_players([doc])) == []

    def test_two_persons_of_feb_that_fit_go_to_review_and_not_to_a_guess(self, players, doc):
        first = players[0]
        birth = next(q["birth"] for t in doc["BOXSCORE"]["TEAM"] for q in t["PLAYER"] if q["id"] == f"acb:{first['id']}")
        name = plain(f"{first['first_name']} {first['last_name']}")
        rows = [{"person_id": "feb:1", "name": name, "birth": birth}, {"person_id": "feb:2", "name": name, "birth": birth}]
        link = next(l for l in link_players(rows, external_players([doc])) if l["external"] == f"acb:{first['id']}")
        assert link["status"] == "review" and {c["feb"] for c in link["candidates"]} == {"feb:1", "feb:2"}

    def test_the_answer_does_not_depend_on_the_order_of_the_players_or_of_the_rows(self, players, doc):
        rows = feb_rows(players, doc, lambda p: plain(f"{p['first_name']} {p['last_name']}"))
        assert link_players(list(reversed(rows)), list(reversed(external_players([doc])))) == link_players(rows, external_players([doc]))


class TestTheCommand:
    """``run_identity_links.py --source acb``: the same command as FIBA's over the archive of ACB (``acb/*.jsonl.gz`` of the external archive) and the FEB rosters."""

    @pytest.fixture()
    def ext(self, tmp_path, players, doc):
        from src.market.roster_store import write_season

        (tmp_path / "acb").mkdir()
        with gzip.open(tmp_path / "acb" / "ACB_Liga_Endesa_2026_.jsonl.gz", "wt", encoding="utf-8") as handle:
            handle.write(json.dumps(doc) + "\n")
        rows = [{**row, "season": "2025", "team_id": "1", "nationality": "ESPAÑA"} for row in feb_rows(players[:5], doc, lambda p: plain(f"{p['first_name']} {p['last_name']}"))]
        write_season(tmp_path / "rosters", "2025", rows, teams=["1"])
        return tmp_path

    def test_it_writes_the_links_of_acb_and_says_how_many(self, ext, capsys):
        import run_identity_links

        assert run_identity_links.main(["--ext", str(ext), "--source", "acb"]) == 0
        data = json.loads((ext / "links" / "acb.json").read_text(encoding="utf-8"))
        assert data["source"] == "acb" and [l["status"] for l in data["links"]] == ["linked"] * 5 and "acb: 5 linked, 0 to review" in capsys.readouterr().out

    def test_a_second_run_changes_no_byte(self, ext):
        import run_identity_links

        run_identity_links.main(["--ext", str(ext), "--source", "acb"])
        first = (ext / "links" / "acb.json").read_bytes()
        run_identity_links.main(["--ext", str(ext), "--source", "acb"])
        assert (ext / "links" / "acb.json").read_bytes() == first
