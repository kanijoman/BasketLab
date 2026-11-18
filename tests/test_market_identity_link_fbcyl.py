"""The link of the players of FBCYL to the person of FEB (#978, sub-issue of #885): FBCYL has no date of birth, so the name key (initial + surnames, in their order) finds the candidates and something else corroborates.

Measured on the whole archive (docs/evaluaciones/2026-11-18_enlace-fiba-feb.md): a player of FBCYL is its ``uuid`` (the ``actorId`` is a new one in every game: 11,614 of them for 2,253 persons), the
candidates of the other sex or too old for the category of the player are not the same person, and a candidate is linked only when its club corroborates it or when its full name (the FEB rosters have it,
with the date of birth) is the same and its birth fits the category. Everything else with a candidate goes to ``review``.

The FBCYL side is the REAL game of the fixture (Primera Nacional Femenina, 2026/27); the FEB side is the real sample game of FEB with the players written the way FEB writes them (``X. SURNAME1 SURNAME2``) and
the roster rows the way the roster sweep writes them; gender and category come from the real catalogue.
"""
import copy
import gzip
import json
from pathlib import Path

import pytest

from market_helpers import unwrap

from src.market.identity_link import club_words, fbcyl_age_groups, fbcyl_players, feb_genders, feb_persons, link_fbcyl, name_key
from src.services.competition_catalogue import DEFAULT_CATALOGUE

ROOT = Path(__file__).resolve().parents[1]
CATALOGUE = json.loads((ROOT / DEFAULT_CATALOGUE).read_text(encoding="utf-8"))["competitions"]
AGES = fbcyl_age_groups(CATALOGUE)
GENDERS = feb_genders(CATALOGUE)
CADETE = next(e["fbcyl"]["competition_id"] for e in CATALOGUE if e.get("league") == "fbcyl" and e.get("age_group") == "U16")


@pytest.fixture(scope="module")
def doc():
    return unwrap(json.loads(gzip.decompress((ROOT / "tests" / "fixtures" / "fbcyl_game_ok.json.gz").read_bytes())))


@pytest.fixture(scope="module")
def players(doc):
    return fbcyl_players([doc], AGES)


@pytest.fixture(scope="module")
def sample():
    return unwrap(json.loads((ROOT / "src" / "JSON_samples" / "feb_game.json").read_text(encoding="utf-8")))


def feb_game(sample, rows, competition="LF ENDESA"):
    """The real FEB sample game whose first team's players are ``rows`` = ``[(idPlayer, "X. SURNAMES", club)]``, in a competition of the catalogue (its gender)."""
    game = copy.deepcopy(sample)
    team = game["BOXSCORE"]["TEAM"][0]
    team["PLAYER"] = [{**team["PLAYER"][0], "id": pid, "name": name} for pid, name, _club in rows]
    game["HEADER"]["TEAM"][0].update({"name": rows[0][2], "id": team["id"]})
    game["_competition"] = competition
    return game


def feb_name(player):
    first, *surnames = player["name"].split()
    return f"{first[0]}. {' '.join(surnames)}"


def roster(pid, name, birth):
    return {"person_id": f"feb:{pid}", "name": name, "birth": birth, "season": "2026", "team_id": "1", "nationality": "ESPAÑA"}


def cadete(doc):
    """The players of the same real game as if it were a cadete (U16) one of the catalogue, those written with their full name first (the rosters of FEB have the full name)."""
    young = copy.deepcopy(doc)
    young["_competition"] = CADETE
    return full_form(fbcyl_players([young], AGES))


def full_form(players):
    return sorted(players, key=lambda p: (len(p["name"].split()[0]) == 1, p["id"]))


def link_of(persons, player):
    links = link_fbcyl(persons, [player])
    return links[0] if links else None


class TestFbcylPersons:
    def test_a_player_is_its_uuid_not_the_actor_id_of_each_game(self, doc, players):
        """Real data: FBCYL gives the same person a new ``actorId`` in every game; the ``uuid`` stays."""
        other = copy.deepcopy(doc)
        for team in other["stats"]["teams"]:
            for player in team["players"]:
                player["actorId"] += 100000
        both = fbcyl_players([doc, other], AGES)
        assert len(both) == len(players) >= 18 and all(p["id"] == f"fbcyl:{p['uuid']}" for p in both)

    def test_the_clubs_of_every_game_are_kept(self, doc):
        other = copy.deepcopy(doc)
        other["stats"]["teams"][0]["name"] = "OTRO CLUB DE LA MISMA JUGADORA"
        uuid = doc["stats"]["teams"][0]["players"][0]["uuid"]
        person = next(p for p in fbcyl_players([doc, other], AGES) if p["uuid"] == uuid)
        assert person["clubs"] == sorted({doc["stats"]["teams"][0]["name"], "OTRO CLUB DE LA MISMA JUGADORA"})

    def test_sex_category_and_season_come_from_the_game_and_the_catalogue(self, players):
        assert {(tuple(p["genders"]), tuple(p["age_groups"]), tuple(p["seasons"])) for p in players} == {(("F",), ("senior",), (2026,))}   # Primera Nacional Femenina

    def test_a_player_without_uuid_is_left_out(self, doc, players):
        bare = copy.deepcopy(doc)
        bare["stats"]["teams"][0]["players"][0]["uuid"] = None
        assert len(fbcyl_players([bare], AGES)) == len(players) - 1


class TestNameKey:
    @pytest.mark.parametrize("a,b", [("V. IBAÑEZ BARREIRO", "VIRGINIA IBAÑEZ BARREIRO"), ("G MURCIANO SAMPERIO", "G. Murciano Samperio"), ("M. DE LA TORRE PEREZ", "MARIA DE LA TORRE PEREZ")])
    def test_the_initial_form_and_the_full_form_of_the_same_player_have_the_same_key(self, a, b):
        assert name_key(a) == name_key(b)

    def test_another_initial_other_surnames_or_the_surnames_the_other_way_round_is_another_key(self):
        """Real case: ``ALBA LÓPEZ HERNÁNDEZ`` (FBCYL) is not ``A. HERNANDEZ LOPEZ`` (FEB): both leagues write the surnames in the same order."""
        assert len({name_key("V. IBAÑEZ BARREIRO"), name_key("B. IBAÑEZ BARREIRO"), name_key("V. IBAÑEZ MARTINEZ"), name_key("V. BARREIRO IBAÑEZ")}) == 4

    def test_a_name_with_a_single_word_has_no_key(self):
        assert name_key("PAULA") is None and name_key("") is None

    @pytest.mark.parametrize("marked", ["(REF) NOA GARRIDO RODRÍGUEZ", "(Re) NOA GARRIDO RODRÍGUEZ", "(JUN) NOA GARRIDO RODRÍGUEZ"])
    def test_the_marks_of_fbcyl_before_the_name_are_not_part_of_it(self, marked):
        """Real data: FBCYL writes ``(REF)`` (a player who reinforces the team) or ``(JUN)`` before the name of 109 player-games; with the mark the key was ``(``."""
        assert name_key(marked) == name_key("N. GARRIDO RODRIGUEZ")


class TestClub:
    def test_club_words_ignore_particles_initials_and_the_words_every_club_has(self):
        assert club_words("C.D.ART-CHIVO OVIEDO SAT LOGISTICA") == {"ART", "CHIVO", "OVIEDO", "SAT", "LOGISTICA"} and club_words("CB DE LA VILLA") == {"VILLA"}
        assert club_words("BALONCESTO LA FLECHA") == {"FLECHA"} and club_words("CLUB BALONCESTO ESCUELA") == set()
        assert club_words('C.B. PUMARIN "A"') == {"PUMARIN"}                    # real FBCYL team: the quotes and the letter of the team are not the club

    def test_the_same_key_in_a_club_with_the_same_words_is_linked(self, sample, players):
        player = players[0]
        link = link_of(feb_persons([feb_game(sample, [(100, feb_name(player), player["clubs"][0])])], genders=GENDERS), player)
        assert (link["status"], link["feb"], link["method"]) == ("linked", "feb:100", "name+club") and len(link["shared"]) >= 2

    def test_the_same_short_club_name_corroborates(self, sample, players):
        """Real case: ``BALONCESTO LA FLECHA`` in both leagues has a single word that is not generic, and it is the same club."""
        player = {**players[0], "clubs": ["BALONCESTO LA FLECHA"]}
        link = link_of(feb_persons([feb_game(sample, [(100, feb_name(player), "BALONCESTO LA FLECHA")])], genders=GENDERS), player)
        assert link["status"] == "linked" and link["shared"] == ["FLECHA"]

    def test_two_clubs_that_share_only_generic_words_do_not_corroborate(self, sample, players):
        player = {**players[0], "clubs": ["BALONCESTO LA FLECHA"]}
        assert link_of(feb_persons([feb_game(sample, [(100, feb_name(player), "CLUB BALONCESTO OTRO")])], genders=GENDERS), player)["status"] == "review"

    def test_a_person_in_two_clubs_is_corroborated_by_either(self, sample, players):
        player = players[0]
        games = [feb_game(sample, [(100, feb_name(player), "OTRO CLUB DISTINTO")]), feb_game(sample, [(100, feb_name(player), player["clubs"][0])])]
        assert link_of(feb_persons(games, genders=GENDERS), player)["status"] == "linked"


class TestWhoCanBeTheSamePerson:
    def test_a_candidate_of_the_other_sex_is_not_a_candidate(self, sample, players):
        """Real case: ``ALVARO MARTIN PEREZ`` (FBCYL, men) and ``A. MARTÍN PÉREZ`` (FEB, women's leagues). Not even a review."""
        player = players[0]                                                  # a woman (Primera Nacional Femenina)
        persons = feb_persons([feb_game(sample, [(100, feb_name(player), player["clubs"][0])], competition="PRIMERA FEB")], genders=GENDERS)
        assert link_of(persons, player) is None

    def test_a_candidate_too_old_for_the_category_is_not_a_candidate(self, doc, sample):
        """Real case: ``ANGELA PEREZ ALONSO`` (FBCYL cadete) and ``A. PEREZ ALONSO`` born in 1993."""
        player = cadete(doc)[0]
        persons = feb_persons([feb_game(sample, [(100, feb_name(player), player["clubs"][0])])], rosters=[roster(100, player["name"], "1993-05-01")], genders=GENDERS)
        assert link_of(persons, player) is None

    def test_two_sisters_of_the_same_club_are_told_apart_by_the_birth(self, doc, sample):
        """The risk of the club rule: two sisters with the same initial in the same club. Only the one whose birth fits a cadete of 2026/27 can be her."""
        player = cadete(doc)[0]
        game = feb_game(sample, [(100, feb_name(player), player["clubs"][0]), (101, feb_name(player), player["clubs"][0])])
        persons = feb_persons([game], rosters=[roster(100, player["name"] + " MAYOR", "2006-02-01"), roster(101, player["name"], "2011-09-09")], genders=GENDERS)
        assert (link_of(persons, player)["status"], link_of(persons, player)["feb"]) == ("linked", "feb:101")

    def test_without_a_known_category_or_birth_the_age_does_not_exclude_anybody(self, doc, sample):
        unknown = copy.deepcopy(doc)
        unknown["_competition"] = "no-esta-en-el-catalogo"
        player = fbcyl_players([unknown], AGES)[0]
        persons = feb_persons([feb_game(sample, [(100, feb_name(player), player["clubs"][0])])], rosters=[roster(100, player["name"], "1993-05-01")], genders=GENDERS)
        assert link_of(persons, player)["status"] == "linked"


class TestTheFullNameAndTheBirth:
    def test_the_full_name_with_a_birth_that_fits_corroborates_when_the_club_does_not(self, doc, sample):
        player = cadete(doc)[0]
        persons = feb_persons([feb_game(sample, [(100, feb_name(player), "CLUB DISTINTO DEL TODO")])], rosters=[roster(100, player["name"], "2011-09-09")], genders=GENDERS)
        link = link_of(persons, player)
        assert (link["status"], link["feb"], link["method"]) == ("linked", "feb:100", "name+birth")

    def test_a_person_known_only_by_the_roster_can_be_linked_by_the_full_name(self, doc):
        player = cadete(doc)[0]
        assert link_of(feb_persons([], rosters=[roster(100, player["name"], "2011-09-09")], genders=GENDERS), player)["status"] == "linked"

    def test_the_full_name_is_no_evidence_when_feb_has_another_person_with_it(self, doc, sample):
        """Real case: two ``MARIA GARCIA RODRIGUEZ`` born in 2008 in the FEB rosters. If FEB itself repeats the full name, it identifies nobody."""
        player = cadete(doc)[0]
        rosters = [roster(100, player["name"], "2011-09-09"), roster(200, player["name"], "1990-01-01")]
        persons = feb_persons([feb_game(sample, [(100, feb_name(player), "CLUB DISTINTO DEL TODO")])], rosters=rosters, genders=GENDERS)
        assert link_of(persons, player)["status"] == "review"

    def test_the_same_key_with_another_club_and_no_birth_goes_to_review(self, sample, players):
        player = players[0]
        link = link_of(feb_persons([feb_game(sample, [(100, feb_name(player), "CLUB DISTINTO DEL TODO")])], genders=GENDERS), player)
        assert link["status"] == "review" and link["feb"] is None and [c["feb"] for c in link["candidates"]] == ["feb:100"]

    def test_a_compound_given_name_finds_the_initial_form_of_feb(self, doc, sample):
        """FBCYL ``MARIA JOSE GARCIA LOPEZ`` is FEB's ``M. GARCIA LOPEZ``: the surnames are the last words."""
        compound = copy.deepcopy(doc)
        first = compound["stats"]["teams"][0]["players"][0]
        given, *surnames = first["name"].split()
        first["name"] = " ".join([given, "JOSE", *surnames])
        player = next(p for p in fbcyl_players([compound], AGES) if p["uuid"] == first["uuid"])
        persons = feb_persons([feb_game(sample, [(100, f"{given[0]}. {' '.join(surnames)}", player["clubs"][0])])], genders=GENDERS)
        assert link_of(persons, player)["status"] == "linked"


class TestTheAnswer:
    def test_two_persons_of_feb_that_fit_go_to_review(self, sample, players):
        player = players[0]
        game = feb_game(sample, [(100, feb_name(player), player["clubs"][0]), (101, feb_name(player), "OTRO CLUB DISTINTO")])
        link = link_of(feb_persons([game], genders=GENDERS), player)
        assert link["status"] == "review" and sorted(c["feb"] for c in link["candidates"]) == ["feb:100", "feb:101"]

    def test_a_key_that_is_not_in_feb_has_no_link(self, sample, players):
        persons = feb_persons([feb_game(sample, [(100, feb_name(players[0]), players[0]["clubs"][0])])], genders=GENDERS)
        assert link_fbcyl(persons, players[5:6]) == []

    def test_the_answer_does_not_depend_on_the_order_of_the_inputs(self, sample, players):
        persons = feb_persons([feb_game(sample, [(100 + i, feb_name(p), p["clubs"][0]) for i, p in enumerate(players[:6])])], genders=GENDERS)
        assert link_fbcyl(persons, players) == link_fbcyl(persons, list(reversed(players)))


class TestTheCommand:
    """``--source fbcyl --archive DIR --ext DIR``: the FBCYL and FEB games of the archive, the FEB rosters of the external archive and the catalogue give ``links/fbcyl.json``."""

    @pytest.fixture()
    def folders(self, tmp_path, doc, players, sample):
        from src.market.roster_store import write_season

        archive, ext = tmp_path / "archive", tmp_path / "ext"
        archive.mkdir()
        with gzip.open(archive / "FBCYL_test.jsonl.gz", "wt", encoding="utf-8") as handle:
            handle.write(json.dumps(doc) + "\n")
        with gzip.open(archive / "LF_test.jsonl.gz", "wt", encoding="utf-8") as handle:
            handle.write(json.dumps(feb_game(sample, [(100 + i, feb_name(p), p["clubs"][0]) for i, p in enumerate(full_form(players)[:2])])) + "\n")
        write_season(ext / "rosters", "2026", [roster(300, full_form(players)[2]["name"], "2000-01-01")], teams=["1"])
        return archive, ext

    @pytest.fixture()
    def cli(self):
        import sys

        sys.path.insert(0, str(ROOT))
        import run_identity_links
        return run_identity_links

    def test_it_links_and_a_second_run_changes_no_byte(self, cli, folders, capsys):
        archive, ext = folders
        args = ["--source", "fbcyl", "--archive", str(archive), "--ext", str(ext)]
        assert cli.main(args) == 0 and "3 linked, 0 to review" in capsys.readouterr().out          # two by the club, one by the full name in the roster (senior: any adult birth fits)
        first = (ext / "links" / "fbcyl.json").read_bytes()
        cli.main(args)
        assert (ext / "links" / "fbcyl.json").read_bytes() == first

    def test_without_the_archive_it_is_an_error(self, cli, tmp_path):
        assert cli.main(["--source", "fbcyl", "--ext", str(tmp_path)]) == 1
