"""The bio of FIBA for the Talent rows (#979): a FIBA player LINKED to a FEB person (``links/fiba.json``, #885) lends what FEB leaves empty (birth, height, nationality), field by field.

Only ``linked`` links count (``review`` waits for the staff, #980); FEB always wins; the answer does not depend on the order of the games or of the links."""
import gzip
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.market.external_bio import external_bio, linked_persons  # noqa: E402
from src.market.season_rows import attach_bio  # noqa: E402


def _game(*players):
    return {"BOXSCORE": {"TEAM": [{"PLAYER": [dict({"min": "600", "birth": "2008-05-05", "height": "190", "nationality": "ESP"}, **p) for p in players]}]}}


def _links(*items):
    return {"format": 1, "source": "fiba", "links": list(items)}


def _link(external, feb, status="linked"):
    return {"external": external, "status": status, "feb": feb if status == "linked" else None, "method": "birth+name", "birth": "2008-05-05", "shared": []}


def _row(person="feb:1"):
    return {"person_id": person, "team_id": "10", "league": "feb", "name": "A. B C"}


def _roster(**over):
    return {"person_id": "feb:1", "season": "2025", "team_id": "10", "name": "ANA BEATRIZ CASTRO", "birth": None, "height": None, "position": None, "nationality": None, **over}


class TestWhoIsLinked:
    def test_only_linked_links_count_and_a_review_waits_for_the_staff(self):
        data = _links(_link("fiba:1", "feb:1"), _link("fiba:2", None, status="review"))
        assert linked_persons(data) == {"fiba:1": "feb:1"}

    def test_no_links_is_an_empty_answer(self):
        assert linked_persons(None) == {} and linked_persons(_links()) == {}


class TestCandidates:
    def test_a_linked_player_gives_its_bio_to_the_feb_person(self):
        found = external_bio([_game({"id": "fiba:1", "name": "ANA"})], {"fiba:1": "feb:1"})
        assert found == {"feb:1": [{"source": "fiba", "season": None, "birth": "2008-05-05", "height": "190", "nationality": "ESP"}]}

    def test_a_player_that_is_not_linked_gives_nothing(self):
        assert external_bio([_game({"id": "fiba:2", "name": "BEA"})], {"fiba:1": "feb:1"}) == {}

    def test_the_value_does_not_depend_on_the_order_of_the_games(self):
        games = [_game({"id": "fiba:1", "height": h}) for h in ("188", "190", "190", "192")]
        for _ in range(5):
            random.shuffle(games)
            assert external_bio(games, {"fiba:1": "feb:1"})["feb:1"][0]["height"] == "190"          # the most said, a tie goes to the smallest

    def test_a_field_one_game_leaves_empty_is_taken_from_another(self):
        games = [_game({"id": "fiba:1", "height": None, "nationality": None}), _game({"id": "fiba:1", "height": "191", "nationality": "ESP"})]
        assert external_bio(games, {"fiba:1": "feb:1"})["feb:1"][0]["height"] == "191"


class TestAttach:
    def test_fiba_fills_what_feb_leaves_empty_and_says_so(self):
        ext = {"feb:1": [{"source": "fiba", "birth": "2008-05-05", "height": "190", "nationality": "ESP"}]}
        (row,) = attach_bio([_row()], [_roster()], "2025", external=ext)
        assert (row["birth"], row["height"], row["nationality"]) == ("2008-05-05", 190, "ESPAÑA")
        assert row["bio_from"] == {"birth": "fiba", "height": "fiba", "nationality": "fiba"}

    def test_feb_wins_over_fiba_where_it_says_a_field(self):
        ext = {"feb:1": [{"source": "fiba", "birth": "2008-05-05", "height": "190", "nationality": "ESP"}]}
        (row,) = attach_bio([_row()], [_roster(height=185, birth="2008-05-06")], "2025", external=ext)
        assert (row["birth"], row["height"], row["nationality"]) == ("2008-05-06", 185, "ESPAÑA") and row["bio_from"] == {"nationality": "fiba"}

    def test_a_person_with_no_roster_at_all_gets_the_bio_of_fiba(self):
        ext = {"feb:1": [{"source": "fiba", "birth": "2008-05-05", "height": "190", "nationality": "ESP"}]}
        (row,) = attach_bio([_row()], [], "2025", external=ext)
        assert (row["birth"], row["height"]) == ("2008-05-05", 190) and row["position"] is None

    def test_without_external_nothing_changes(self):
        assert attach_bio([_row()], [_roster()], "2025") == attach_bio([_row()], [_roster()], "2025", external={})

    def test_a_height_out_of_range_is_not_taken(self):
        (row,) = attach_bio([_row()], [_roster()], "2025", external={"feb:1": [{"source": "fiba", "height": "19"}]})
        assert row["height"] is None and "height" not in row["bio_from"]


class TestTheCommand:
    def test_run_talent_data_reads_links_and_games_of_the_external_archive(self, tmp_path):
        import run_talent_data

        (tmp_path / "links").mkdir()
        (tmp_path / "links" / "fiba.json").write_text(json.dumps(_links(_link("fiba:1", "feb:1"))), encoding="utf-8")
        (tmp_path / "fiba").mkdir()
        with gzip.open(tmp_path / "fiba" / "FIBA_x_.jsonl.gz", "wt", encoding="utf-8") as handle:
            handle.write(json.dumps(_game({"id": "fiba:1", "name": "ANA"})) + "\n")
        assert run_talent_data.read_external_bio(tmp_path)["feb:1"][0]["height"] == "190"
        assert run_talent_data.read_external_bio(tmp_path / "nowhere") == {}


class TestAcbAndItsPosition:
    """ACB (#886) says the position of a player in its box (FEB leaves it empty for ~90 % of the players), so the position is a field an external source lends too; and two sources lend to the same person."""

    def test_the_position_of_a_linked_player_is_a_field_of_the_bio(self):
        found = external_bio([_game({"id": "acb:1", "name": "ANA", "position": "Ala-pívot"})], {"acb:1": "feb:1"}, "acb")
        assert found["feb:1"][0]["position"] == "Ala-pívot" and found["feb:1"][0]["source"] == "acb"

    def test_a_player_whose_source_has_no_position_has_none_in_the_bio(self):
        found = external_bio([_game({"id": "fiba:1", "name": "ANA"})], {"fiba:1": "feb:1"})
        assert "position" not in found["feb:1"][0]

    def test_acb_fills_the_position_feb_leaves_empty_and_feb_wins_where_it_says_one(self):
        ext = {"feb:1": [{"source": "acb", "birth": "1997-02-07", "height": "202", "nationality": "Francia", "position": "Ala-pívot"}]}
        (row,) = attach_bio([_row()], [_roster()], "2025", external=ext)
        assert row["position"] == "Ala-Pívot" and row["bio_from"]["position"] == "acb"
        (row,) = attach_bio([_row()], [_roster(position="Base")], "2025", external=ext)
        assert row["position"] == "Base" and "position" not in row["bio_from"]

    def test_the_archive_gives_the_bio_of_every_source_that_has_links_and_games(self, tmp_path):
        import run_talent_data

        (tmp_path / "links").mkdir()
        for source, ext_id, height in (("fiba", "fiba:1", "190"), ("acb", "acb:7", "202")):
            (tmp_path / "links" / f"{source}.json").write_text(json.dumps({"format": 1, "source": source, "links": [_link(ext_id, "feb:1")]}), encoding="utf-8")
            (tmp_path / source).mkdir()
            with gzip.open(tmp_path / source / f"{source.upper()}_x_.jsonl.gz", "wt", encoding="utf-8") as handle:
                handle.write(json.dumps({**_game({"id": ext_id, "name": "ANA", "height": height}), "_season": "2025"}) + "\n")
        bio = run_talent_data.read_external_bio(tmp_path)
        assert [(c["source"], c["height"]) for c in bio["feb:1"]] == [("acb", "202"), ("fiba", "190")]                    # both, in the order of the sources' names

    def test_a_source_that_has_nothing_yet_is_not_an_error_and_the_other_one_still_gives_its_bio(self, tmp_path):
        import run_talent_data

        (tmp_path / "links").mkdir()
        (tmp_path / "links" / "acb.json").write_text(json.dumps({"format": 1, "source": "acb", "links": [_link("acb:7", "feb:1")]}), encoding="utf-8")
        (tmp_path / "acb").mkdir()
        with gzip.open(tmp_path / "acb" / "ACB_x_.jsonl.gz", "wt", encoding="utf-8") as handle:
            handle.write(json.dumps(_game({"id": "acb:7", "name": "ANA"})) + "\n")
        assert [c["source"] for c in run_talent_data.read_external_bio(tmp_path)["feb:1"]] == ["acb"]
