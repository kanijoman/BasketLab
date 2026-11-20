"""The pages of a player of ACB as data (#886, D2f of epic #872): his bio (``temporada``) and his shots with their court coordinates (``zonas-de-tiro``), read from the REAL pages of Amine Noua in ``tests/fixtures/acb``.

The shots of a player do not say their play: they carry the game, the type of the shot, where it was taken and whether it went in. They are joined to the plays of the game by their order (the n-th shot of the
player in the game is his n-th shot play), and only when the two lists say the same thing (the same number, the same types in the same order): a game where they differ gets no coordinates rather than wrong ones.
"""
import gzip
from pathlib import Path

import pytest

from src.external.acb_page import AcbPageError, CutPage, parse_player, parse_plays, parse_shots, shots_of_game

FIX = Path(__file__).parent / "fixtures" / "acb"
NOUA = 30001137


def flight(name: str) -> str:
    return gzip.decompress((FIX / f"{name}.flight.gz").read_bytes()).decode("utf-8")


BIO, SHOTS, PLAYS = flight("player.temporada"), flight("player.zonas-de-tiro"), flight("105383.jugadas")


class TestTheBio:
    def test_it_reads_the_birth_the_height_the_position_and_the_nationality(self):
        player = parse_player(BIO)
        assert (player["id"], player["name"], player["first_name"], player["last_name"]) == (NOUA, "Amine Noua", "Amine", "Noua")
        assert player["birth"] == "1997-02-07" and player["birth_place"] == "Lyon" and player["nationality"] == "Francia"
        assert player["height_cm"] == 202 and player["position"] == "Ala-pívot" and player["number"] == "17"

    def test_the_bio_is_normalised_as_the_bio_of_the_other_sources(self):
        from src.market.bio import canonical_position, normalize_height, position_group

        player = parse_player(BIO)
        assert canonical_position(player["position"]) == "Ala-Pívot" and position_group(player["position"]) == "F" and normalize_height(player["height_cm"]) == 202

    @pytest.mark.parametrize("raw, birth", [("07-02-1997", "1997-02-07"), ("1-1-2001", "2001-01-01"), ("31-12-1999", "1999-12-31"), ("1997-02-07", None), ("32-01-1990", None), ("", None), (None, None), ("sin dato", None)])
    def test_a_birth_is_day_month_year_and_what_is_not_a_date_is_none_never_guessed(self, raw, birth):
        from src.external.acb_page import _birth

        assert _birth(raw) == birth

    @pytest.mark.parametrize("raw, cm", [("2,02", 202), ("1,85", 185), ("1.98", 198), ("2,2", 220), ("0", None), ("", None), (None, None), ("3,50", None), ("1,00", None), ("alto", None)])
    def test_a_height_is_metres_with_a_comma_and_what_is_not_plausible_is_none(self, raw, cm):
        from src.external.acb_page import _height_cm

        assert _height_cm(raw) == cm

    def test_a_page_with_no_bio_is_cut_or_in_another_format(self):
        with pytest.raises(CutPage):
            parse_player("{}")
        with pytest.raises(AcbPageError, match="format"):
            parse_player('{"player":{"unexpected":1},"birthDate":"01-01-2000"}')


class TestTheShots:
    def test_it_reads_every_shot_with_its_coordinates_its_zone_and_the_game(self):
        shots = parse_shots(SHOTS)
        assert len(shots["shots"]) == 68 and shots["attempts"] == 68 and shots["made"] == 38 and shots["without_coordinates"] == 0
        first = shots["shots"][0]
        assert (first["match_id"], first["x"], first["y"], first["play_type"], first["made"], first["points"], first["zone"]) == (105383, 0, -615, 93, True, 2, "restricted_area")
        assert sum(1 for s in shots["shots"] if s["made"]) == 38 and {s["points"] for s in shots["shots"]} == {2, 3}

    def test_a_page_without_shots_is_cut_and_one_in_another_format_is_a_format_error(self):
        with pytest.raises(CutPage):
            parse_shots("{}")
        with pytest.raises(AcbPageError, match="format"):
            parse_shots('"seasonShots":{"shots":[{"unexpected":1}]}')


class TestTheShotsOfAGame:
    def test_each_shot_play_of_the_player_gets_its_coordinates_in_the_order_of_the_game(self):
        plays, shots = parse_plays(PLAYS), parse_shots(SHOTS)["shots"]
        placed = shots_of_game(plays, shots, NOUA, 105383)
        mine = [p for p in plays if p["player_id"] == NOUA and p["type"] in (93, 94, 97, 98, 100, 533)]
        assert len(placed) == len(mine) == 11 and set(placed) == {p["order"] for p in mine}
        assert all(placed[p["order"]]["play_type"] == p["type"] for p in mine)
        assert (placed[mine[0]["order"]]["x"], placed[mine[0]["order"]]["y"]) == (0, -615)                      # his first shot of the game, under the basket

    def test_the_made_shots_are_the_made_plays(self):
        plays, shots = parse_plays(PLAYS), parse_shots(SHOTS)["shots"]
        placed = shots_of_game(plays, shots, NOUA, 105383)
        for p in plays:
            if p["order"] in placed:
                assert placed[p["order"]]["made"] == (p["type"] in (93, 94, 100))

    def test_a_game_where_the_two_lists_differ_gets_no_coordinates(self):
        plays, shots = parse_plays(PLAYS), parse_shots(SHOTS)["shots"]
        mine = [s for s in shots if s["match_id"] == 105383]
        assert shots_of_game(plays, [s for s in shots if s is not mine[0]], NOUA, 105383) == {}                                  # one shot missing
        wrong = [dict(s, play_type=97 if s is mine[0] else s["play_type"]) for s in shots]
        assert shots_of_game(plays, wrong, NOUA, 105383) == {}                                                                 # one of another type
        assert shots_of_game(plays, shots, NOUA, 999) == {}                                                                    # a game the player did not play
