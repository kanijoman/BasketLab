"""The link of the players of an external source (FIBA) to the person of FEB (#885, D1; D3c of #887): same date of birth AND at least two words of the name in common, and a single candidate.

Measured on the real data (docs/evaluaciones/2026-11-18_enlace-fiba-feb.md): the date of birth alone corroborates nothing (80 % of the foreigners share one with somebody in FEB by chance), the two together link
68 of 71 Spanish players and 34 foreigners with no ambiguous case. Decided 18/11/2026: ``linked`` needs both and a single candidate; one word in common or several candidates go to ``review``; a date alone never links.
The players are the REAL ones of the FIBA fixtures; the FEB rows are written the way FEB writes a roster (``NAME SURNAME1 SURNAME2``, upper case, the ``feb:<idPlayer>`` of the person) from them.
"""
import copy
import gzip
import json
from pathlib import Path

import pytest

from src.external.fiba_canonical import to_canonical
from src.external.fiba_page import parse_game
from src.market.identity_link import external_players, link_players

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "fiba"


@pytest.fixture(scope="module")
def doc():
    return to_canonical(parse_game(gzip.decompress((FIXTURES / "125809.flight.gz").read_bytes()).decode("utf-8")))


@pytest.fixture(scope="module")
def players(doc):
    return external_players([doc])


def feb_row(player, person_id, name=None, birth=None):
    """The roster row FEB would have for this player: the same person written the FEB way, with a second surname."""
    return {"person_id": f"feb:{person_id}", "name": name or f"{player['name'].upper()} SEGUNDO", "birth": birth or player["birth"], "season": "2025", "team_id": "1", "nationality": "ESPAÑA"}


def only(links, external):
    return [link for link in links if link["external"] == external]


class TestPlayersOfTheDocuments:
    def test_every_player_with_minutes_is_listed_once_with_the_bio_of_the_page(self, doc, players):
        ids = [p["id"] for p in players]
        assert len(ids) == len(set(ids)) and all(p["birth"] and p["name"] for p in players) and "fiba:344984" not in ids       # 344984 never played

    def test_the_same_player_in_two_games_is_one_player(self, doc):
        assert len(external_players([doc, copy.deepcopy(doc)])) == len(external_players([doc]))


class TestTheRule:
    def test_the_same_birth_and_the_name_with_a_second_surname_link(self, players):
        player = players[0]
        links = link_players([feb_row(player, 1001)], players)
        link = only(links, player["id"])[0]
        assert (link["status"], link["feb"], link["method"]) == ("linked", "feb:1001", "birth+name") and len(link["shared"]) >= 2

    def test_accents_case_and_hyphens_do_not_matter(self, players):
        player = {**players[0], "name": "José-María Ñúñez"}
        row = feb_row(player, 1002, name="JOSE MARIA NUNEZ PEREZ")
        assert only(link_players([row], [player]), player["id"])[0]["status"] == "linked"

    def test_the_same_birth_with_an_unrelated_name_never_links(self, players):
        player = players[0]
        assert only(link_players([feb_row(player, 1003, name="NOA MONTERO NAVARRO")], players), player["id"]) == []

    def test_the_same_name_with_another_birth_never_links(self, players):
        player = players[0]
        assert only(link_players([feb_row(player, 1004, birth="1999-01-01")], players), player["id"]) == []

    def test_particles_do_not_make_two_people_the_same(self):
        """``de la`` is in both names and so is the birth: two words in common, but no name in common."""
        player = {"id": "fiba:1", "name": "Maria de la Cruz", "birth": "2008-05-05"}
        row = {"person_id": "feb:9", "name": "ANA DE LA TORRE", "birth": "2008-05-05"}
        assert link_players([row], [player]) == []

    def test_one_word_in_common_goes_to_review_with_its_candidate(self, players):
        player = players[0]
        first = player["name"].upper().split()[0]
        link = only(link_players([feb_row(player, 1005, name=f"{first} OTRO APELLIDO")], players), player["id"])[0]
        assert link["status"] == "review" and link["feb"] is None and [c["feb"] for c in link["candidates"]] == ["feb:1005"]

    def test_two_people_of_feb_that_fit_go_to_review_not_to_a_coin_toss(self, players):
        player = players[0]
        links = link_players([feb_row(player, 1006), feb_row(player, 1007, name=f"{player['name'].upper()} TERCERO")], players)
        link = only(links, player["id"])[0]
        assert link["status"] == "review" and sorted(c["feb"] for c in link["candidates"]) == ["feb:1006", "feb:1007"]

    def test_a_person_in_several_rosters_is_one_candidate_not_several(self, players):
        """FEB rewrites the roster of every season: the same ``person_id`` in two seasons is one person."""
        player = players[0]
        rows = [feb_row(player, 1008), {**feb_row(player, 1008), "season": "2024", "team_id": "2"}]
        assert only(link_players(rows, players), player["id"])[0]["status"] == "linked"

    def test_a_row_without_birth_cannot_link(self, players):
        player = players[0]
        assert link_players([{**feb_row(player, 1009), "birth": None}], players) == []


class TestTheResult:
    def test_the_answer_is_the_same_whatever_the_order_of_the_inputs(self, players):
        rows = [feb_row(p, 2000 + i) for i, p in enumerate(players[:6])]
        assert link_players(rows, players) == link_players(list(reversed(rows)), list(reversed(players)))

    def test_every_link_names_the_two_sides_and_the_words_that_corroborate_it(self, players):
        rows = [feb_row(p, 3000 + i) for i, p in enumerate(players[:4])]
        links = link_players(rows, players)
        assert len(links) == 4 and all({"external", "feb", "status", "method", "birth", "shared"} <= set(link) for link in links)
        assert [link["external"] for link in links] == sorted(link["external"] for link in links)

    def test_nothing_to_link_is_an_empty_answer_not_an_error(self, players):
        assert link_players([], players) == [] and link_players([feb_row(players[0], 1)], []) == []


class TestTheCommand:
    """``run_identity_links.py``: reads the archive of the external sources and the FEB rosters and writes ``links/<source>.json`` without a timestamp, so a second run changes no byte."""

    @pytest.fixture()
    def ext(self, tmp_path, doc, players):
        from src.market.roster_store import write_season

        (tmp_path / "fiba").mkdir()
        with gzip.open(tmp_path / "fiba" / "FIBA_test_.jsonl.gz", "wt", encoding="utf-8") as handle:
            handle.write(json.dumps(doc) + "\n")
        write_season(tmp_path / "rosters", "2025", [feb_row(p, 500 + i) for i, p in enumerate(players[:5])], teams=["1"])
        return tmp_path

    @pytest.fixture()
    def cli(self):
        import sys

        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        import run_identity_links
        return run_identity_links

    def test_it_writes_the_links_of_the_source_and_says_how_many(self, cli, ext, capsys):
        assert cli.main(["--ext", str(ext)]) == 0
        data = json.loads((ext / "links" / "fiba.json").read_text(encoding="utf-8"))
        assert data["source"] == "fiba" and [l["status"] for l in data["links"]] == ["linked"] * 5 and "5 linked, 0 to review" in capsys.readouterr().out

    def test_a_second_run_changes_no_byte(self, cli, ext):
        cli.main(["--ext", str(ext)])
        first = (ext / "links" / "fiba.json").read_bytes()
        cli.main(["--ext", str(ext)])
        assert (ext / "links" / "fiba.json").read_bytes() == first

    def test_a_source_without_an_archive_is_an_error_not_an_empty_file(self, cli, ext, capsys):
        assert cli.main(["--ext", str(ext), "--source", "acb"]) == 1 and not (ext / "links" / "acb.json").exists()


# FBCYL <-> FEB (#978): FBCYL carries no date of birth, so the link is by name key (initial + surnames) and the club the player is in; the FEB side is the persons of the FEB boxes (``X. SURNAME1 SURNAME2``).
from market_helpers import unwrap  # noqa: E402

from src.market.identity_link import club_words, fbcyl_players, feb_persons, link_fbcyl, name_key  # noqa: E402


@pytest.fixture(scope="module")
def fbcyl_doc():
    return json.loads(gzip.decompress((Path(__file__).resolve().parent / "fixtures" / "fbcyl_game_ok.json.gz").read_bytes()))


@pytest.fixture(scope="module")
def fb_players(fbcyl_doc):
    return fbcyl_players([unwrap(fbcyl_doc)])


@pytest.fixture(scope="module")
def feb_sample():
    return unwrap(json.loads((Path(__file__).resolve().parents[1] / "src" / "JSON_samples" / "feb_game.json").read_text(encoding="utf-8")))


def feb_game(sample, rows):
    """A real FEB game (the sample) whose first team's players are ``rows`` = ``[(idPlayer, "X. SURNAMES")]`` and whose team has the club name of the row set: how FEB would have written those players."""
    game = copy.deepcopy(sample)
    team = game["BOXSCORE"]["TEAM"][0]
    team["PLAYER"] = [{**team["PLAYER"][0], "id": pid, "name": name} for pid, name, _club in rows]
    game["HEADER"]["TEAM"][0]["name"] = rows[0][2]
    game["HEADER"]["TEAM"][0]["id"] = team["id"]
    return game


def feb_name(player):
    first, *surnames = player["name"].split()
    return f"{first[0]}. {' '.join(surnames)}"


class TestFbcylPlayers:
    def test_the_players_of_the_two_teams_come_with_their_club_once_each(self, fb_players):
        assert len({p["id"] for p in fb_players}) == len(fb_players) >= 18 and all(p["id"].startswith("fbcyl:") and p["team"] for p in fb_players)

    def test_the_same_player_in_two_games_is_one_player(self, fbcyl_doc, fb_players):
        assert len(fbcyl_players([unwrap(fbcyl_doc), unwrap(copy.deepcopy(fbcyl_doc))])) == len(fb_players)


class TestNameKey:
    @pytest.mark.parametrize("a,b", [("V. IBAÑEZ BARREIRO", "VIRGINIA IBAÑEZ BARREIRO"), ("G MURCIANO SAMPERIO", "G. Murciano Samperio"), ("M. DE LA TORRE PEREZ", "MARIA DE LA TORRE PEREZ")])
    def test_the_initial_form_and_the_full_form_of_the_same_player_have_the_same_key(self, a, b):
        assert name_key(a) == name_key(b)

    def test_another_initial_or_other_surnames_is_another_key(self):
        assert name_key("V. IBAÑEZ BARREIRO") != name_key("B. IBAÑEZ BARREIRO") and name_key("V. IBAÑEZ BARREIRO") != name_key("V. IBAÑEZ MARTINEZ")

    def test_a_name_with_a_single_word_has_no_key(self):
        assert name_key("PAULA") is None and name_key("") is None


class TestFbcylToFeb:
    def _persons(self, sample, fb_players, extra_club=None, take=3):
        rows = [(100 + i, feb_name(p), extra_club or p["team"] + " B") for i, p in enumerate(fb_players[:take])]
        return feb_persons([feb_game(sample, [(pid, nm, club) for pid, nm, club in rows])]), rows

    def test_the_same_key_in_a_club_with_the_same_words_is_linked(self, feb_sample, fb_players):
        persons, rows = self._persons(feb_sample, fb_players, extra_club=fb_players[0]["team"])
        link = next(l for l in link_fbcyl(persons, fb_players[:1]))
        assert (link["status"], link["feb"], link["method"]) == ("linked", "feb:100", "name+club") and len(link["shared"]) >= 2

    def test_the_same_key_in_an_unrelated_club_goes_to_review_not_to_a_link(self, feb_sample, fb_players):
        persons, _ = self._persons(feb_sample, fb_players, extra_club="CLUB DISTINTO DEL TODO")
        link = link_fbcyl(persons, fb_players[:1])[0]
        assert link["status"] == "review" and link["feb"] is None and [c["feb"] for c in link["candidates"]] == ["feb:100"]

    def test_two_persons_of_feb_with_the_same_key_go_to_review_even_if_one_has_the_club(self, feb_sample, fb_players):
        player = fb_players[0]
        game = feb_game(feb_sample, [(100, feb_name(player), player["team"]), (101, feb_name(player), "OTRO CLUB DISTINTO")])
        link = link_fbcyl(feb_persons([game]), [player])[0]
        assert link["status"] == "review" and sorted(c["feb"] for c in link["candidates"]) == ["feb:100", "feb:101"]

    def test_a_key_that_is_not_in_feb_has_no_link(self, feb_sample, fb_players):
        persons, _ = self._persons(feb_sample, fb_players[:2])
        assert link_fbcyl(persons, fb_players[5:6]) == []

    def test_a_person_in_two_clubs_keeps_both_for_the_club_check(self, feb_sample, fb_players):
        player = fb_players[0]
        persons = feb_persons([feb_game(feb_sample, [(100, feb_name(player), "OTRO CLUB DISTINTO")]), feb_game(feb_sample, [(100, feb_name(player), player["team"])])])
        assert link_fbcyl(persons, [player])[0]["status"] == "linked"

    def test_club_words_ignore_particles_initials_and_the_words_every_club_has(self):
        assert club_words("C.D.ART-CHIVO OVIEDO SAT LOGISTICA") == {"ART", "CHIVO", "OVIEDO", "SAT", "LOGISTICA"} and club_words("CB DE LA VILLA") == {"VILLA"}
        assert club_words("BALONCESTO LA FLECHA") == {"FLECHA"} and club_words("CLUB BALONCESTO ESCUELA") == set()

    def test_two_clubs_that_share_only_generic_words_do_not_corroborate(self, feb_sample, fb_players):
        """``BALONCESTO`` or ``CLUB`` are in half of the clubs: the corroboration is the words that identify one."""
        player = {**fb_players[0], "team": "BALONCESTO LA FLECHA"}
        persons = feb_persons([feb_game(feb_sample, [(100, feb_name(player), "CLUB BALONCESTO OTRO")])])
        assert link_fbcyl(persons, [player])[0]["status"] == "review"

    def test_the_answer_does_not_depend_on_the_order_of_the_inputs(self, feb_sample, fb_players):
        persons, _ = self._persons(feb_sample, fb_players, extra_club=fb_players[0]["team"], take=6)
        assert link_fbcyl(persons, fb_players) == link_fbcyl(persons, list(reversed(fb_players)))


class TestTheCommandForFbcyl:
    """``--source fbcyl --archive DIR``: the FBCYL games and the FEB ones of the archive give ``links/fbcyl.json``."""

    @pytest.fixture()
    def folders(self, tmp_path, fbcyl_doc, fb_players, feb_sample):
        archive, ext = tmp_path / "archive", tmp_path / "ext"
        archive.mkdir()
        with gzip.open(archive / "FBCYL_test.jsonl.gz", "wt", encoding="utf-8") as handle:
            handle.write(json.dumps(fbcyl_doc) + "\n")
        rows = [(100 + i, feb_name(p), p["team"]) for i, p in enumerate(fb_players[:2])]
        with gzip.open(archive / "LF_test.jsonl.gz", "wt", encoding="utf-8") as handle:
            handle.write(json.dumps(feb_game(feb_sample, rows)) + "\n")
        return archive, ext

    def test_it_links_by_name_and_club_and_a_second_run_changes_no_byte(self, folders, capsys):
        import sys

        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        import run_identity_links

        archive, ext = folders
        args = ["--source", "fbcyl", "--archive", str(archive), "--ext", str(ext)]
        assert run_identity_links.main(args) == 0 and "2 linked, 0 to review" in capsys.readouterr().out
        first = (ext / "links" / "fbcyl.json").read_bytes()
        run_identity_links.main(args)
        assert (ext / "links" / "fbcyl.json").read_bytes() == first

    def test_without_the_archive_it_is_an_error(self, tmp_path):
        import sys

        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        import run_identity_links
        assert run_identity_links.main(["--source", "fbcyl", "--ext", str(tmp_path)]) == 1
