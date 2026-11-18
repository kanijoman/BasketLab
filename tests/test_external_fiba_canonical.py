"""A FIBA game as the canonical document of an external source (#887, D3a): the REAL pages of ``tests/fixtures/fiba`` converted to the FEB document, with ``_league: fiba`` and every id prefixed.

The conversion has to satisfy, on every real game, the three things the epic asks of an external source: ``validate_game`` finds nothing wrong, ``reconcile_game`` finds the play-by-play and the official box of the page
in agreement on EVERY statistic (the nine core ones and the information ones), and the pipelines of ``web-data`` publish its rows. The play-by-play lines are written as the engine reads the FEB ones (the same way
``fbcyl_adapter`` does for FBCYL), so nothing of the engine forks.
"""
import copy
import gzip
from collections import Counter
from pathlib import Path

import pytest

from db_helpers import new_mock_db

from src.external.fiba_canonical import gender_of, to_canonical
from src.external.fiba_page import parse_game
from src.live_core.events import parse_line
from src.local_data.export import export_collection
from src.market.box_reconciliation import CORE_STATS, reconcile_game
from src.market.canonical import validate_game
from src.pbp.game_events import game_events

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "fiba"
GAMES = ["125809", "125803", "125812", "125859", "123004", "123043", "125835", "125814"]
OVERTIME = "123043"
WOMEN = {"125859", "123043"}


def page(name: str) -> dict:
    return parse_game(gzip.decompress((FIXTURES / f"{name}.flight.gz").read_bytes()).decode("utf-8"))


@pytest.fixture(scope="module")
def pages():
    return {name: page(name) for name in GAMES}


@pytest.fixture(scope="module")
def docs(pages):
    return {name: to_canonical(game) for name, game in pages.items()}


@pytest.mark.parametrize("name", GAMES)
class TestEveryRealGame:
    def test_it_is_a_valid_canonical_document_of_its_source(self, docs, name):
        assert validate_game(docs[name], "F" if name in WOMEN else "M") == []

    def test_the_play_by_play_and_the_official_box_agree_on_every_statistic(self, docs, name):
        result = reconcile_game(docs[name])
        assert result.reliable and result.mismatches() == [], [(c.team_id, c.stat, c.pbp, c.official) for c in result.mismatches()]

    def test_the_engine_reads_every_line_as_what_it_is(self, pages, docs, name):
        kinds = Counter(e.kind for e in game_events(docs[name], False))
        codes = Counter(e["code"] for e in pages[name]["events"])
        assert kinds["fg2"] == codes["P2"] and kinds["fg3"] == codes["P3"] and kinds["ft"] == codes["FT"]
        assert kinds["rebound"] == codes["REB"] + codes["TREB"] and kinds["assist"] == codes["ASS"] and kinds["steal"] == codes["ST"] and kinds["block"] == codes["BS"]
        assert kinds["turnover"] == codes["TO"] + codes["TTO"] and kinds["foul"] == codes["FOUL"]
        assert kinds["period_start"] == codes["STARTP"] and kinds["timeout"] == codes["TIMO"]
        subs = [e for e in pages[name]["events"] if e["code"] == "SUBST"]
        paired = sum(1 for e in subs if e["player2"] is not None)               # a substitution that names who comes in AND who goes out is two lines, as FEB writes it
        assert kinds["sub_in"] == sum(1 for e in subs if e["in"] == "IN") and kinds["sub_out"] == sum(1 for e in subs if e["in"] == "OUT") + paired

    def test_the_pipelines_of_web_data_publish_its_rows(self, docs, name):
        collection = f"FIBA_Test_{name}_"
        db = new_mock_db("BASKETBALL")
        db[collection].insert_one(copy.deepcopy(docs[name]))
        payload = export_collection(db[collection], collection)
        assert payload["league"] == "fiba" and payload["games"] == 1
        official = {t["id"]: int(t["pts"]) for t in docs[name]["HEADER"]["TEAM"]}
        assert {r["team_id"]: r["points"] for r in payload["team_rows"]} == official


class TestTheDocument:
    def test_the_header_says_the_game_the_competition_and_the_teams(self, docs):
        header = docs["125809"]["HEADER"]
        assert (docs["125809"]["_id"], docs["125809"]["_league"], docs["125809"]["_season"]) == ("fiba:125809", "fiba", "2025")
        assert (header["competition"], header["round"], header["place"], header["starttime"], header["status"], header["time"]) == ("FIBA U18 EuroBasket", "Group Phase", "Belgrade Arena", "28-07-2025 - 21:00", "3", "FINAL")
        assert [(t["id"], t["name"], t["pts"]) for t in header["TEAM"]] == [("fiba:59", "France", "95"), ("fiba:17", "Austria", "56")]
        assert [(q["n"], q["scoreA"], q["scoreB"]) for q in header["QUARTERS"]["QUARTER"]] == [("1", "24", "18"), ("2", "25", "14"), ("3", "24", "10"), ("4", "22", "14")]

    def test_the_box_of_a_player_is_the_official_one_with_prefixed_ids_and_minutes_in_seconds(self, docs):
        team = docs["125809"]["BOXSCORE"]["TEAM"][0]
        yimga = next(p for p in team["PLAYER"] if p["id"] == "fiba:344991")
        assert (yimga["name"], yimga["no"], yimga["pts"], yimga["rt"], yimga["ro"], yimga["rd"], yimga["assist"], yimga["p2m"], yimga["p2a"], yimga["p1m"], yimga["p1a"]) == ("Hugo Yimga", "1", "13", "10", "2", "8", "2", "6", "9", "1", "2")
        assert yimga["min"] == str(18 * 60 + 45) and team["win_lose"] == "W" and docs["125809"]["BOXSCORE"]["TEAM"][1]["win_lose"] == "L"

    def test_the_team_totals_are_the_official_ones_and_the_team_actions_are_apart(self, docs):
        team = docs["125809"]["BOXSCORE"]["TEAM"][0]
        assert (team["TOTAL"]["assist"], team["TOTAL"]["rt"], team["TOTAL"]["ro"], team["TOTAL"]["rd"]) == ("25", "41", "11", "30")          # its players' rebounds: 44 of FIBA's total minus the 3 of the team itself
        assert (team["TEAMACTIONS"]["rt"], team["TEAMACTIONS"]["to"]) == ("3", "1")
        assert int(team["TOTAL"]["rt"]) + int(team["TEAMACTIONS"]["rt"]) == 44                                                               # and together they are FIBA's official figure

    def test_a_foul_drawn_is_kept_on_the_foul_it_belongs_to_not_as_a_line_of_its_own(self, pages, docs):
        lines = docs["125809"]["PLAYBYPLAY"]["LINES"]
        drawn = Counter(e["code"] for e in pages["125809"]["events"])["RFOUL"]
        fouls = [l for l in lines if l["action"] == "foul"]
        assert sum(1 for l in fouls if l.get("logParam4")) == drawn and all(l["idPlayer"].startswith("fiba:") for l in fouls)

    def test_a_personal_foul_carries_the_fouls_of_its_player_so_far_as_the_engine_reads_them(self, docs):
        counts = {}
        for line in docs["125809"]["PLAYBYPLAY"]["LINES"]:
            if line["action"] == "foul":
                counts[line["idPlayer"]] = counts.get(line["idPlayer"], 0) + 1          # every foul counts, a technical one too, as the official box does
                if "PERSONAL" in line["text"]:
                    assert parse_line(line).pf_count == counts[line["idPlayer"]]

    def test_the_lines_are_numbered_in_order_and_carry_the_period_and_the_remaining_clock(self, docs):
        lines = docs["125809"]["PLAYBYPLAY"]["LINES"]
        assert [l["num"] for l in lines] == [str(i) for i in range(1, len(lines) + 1)]
        assert lines[0]["quarter"] == "1" and lines[-1]["quarter"] == "4" and all(len(l["time"]) == 5 and l["time"][2] == ":" for l in lines)

    def test_a_dunk_is_read_as_a_two_point_shot_the_way_feb_writes_it(self, pages, docs):
        dunks = [e for e in pages["123004"]["events"] if e["code"] == "P2" and "dunk" in (e["text"] or "").lower()]
        if dunks:
            assert sum("MATE" in l["text"] for l in docs["123004"]["PLAYBYPLAY"]["LINES"]) == len(dunks)


class TestBiography:
    """The page of a game carries the roster with each player's bio (date of birth, height, nationality, club): it is archived with the game, nothing is discarded (#887, D3b-2). A player the page says nothing
    about has the field empty, never guessed."""

    def _player(self, doc, person_id):
        return next(p for t in doc["BOXSCORE"]["TEAM"] for p in t["PLAYER"] if p["id"] == f"fiba:{person_id}")

    def test_a_player_carries_the_bio_of_the_roster_of_the_page(self, docs):
        atamna = self._player(docs["125809"], 344984)
        assert (atamna["birth"], atamna["height"], atamna["nationality"], atamna["club"]) == ("2007-12-06", "195", "FRA", "LDLC ASVEL")

    @pytest.mark.parametrize("name", GAMES)
    def test_every_player_of_every_real_game_has_a_birth_date_and_a_nationality(self, docs, name):
        players = [p for t in docs[name]["BOXSCORE"]["TEAM"] for p in t["PLAYER"]]
        assert len(players) >= 20 and all(p["birth"] and p["nationality"] for p in players)

    def test_a_player_without_height_has_it_empty_not_zero(self, docs):
        heights = [p["height"] for t in docs["125859"]["BOXSCORE"]["TEAM"] for p in t["PLAYER"]]
        assert None in heights and "0" not in heights and all(h is None or 120 <= int(h) <= 240 for h in heights)

    def test_a_page_without_the_bio_block_still_converts_with_the_fields_empty(self, pages):
        bare = copy.deepcopy(pages["125809"])
        for team in bare["teams"]:
            for player in team["players"]:
                for key in ("birth", "height_cm", "nationality", "club"):
                    player.pop(key, None)
        doc = to_canonical(bare)
        assert doc["BOXSCORE"]["TEAM"][0]["PLAYER"][0]["birth"] is None and validate_game(doc, "M") == []


class TestGamesWhoseEventsAreNotInTheOrderOfTheirClock:
    """Found on the first real load of the source (18/11/2026): 7 of the 56 games of the U18 EuroBasket 2025 did not reconcile, and only on rebounds. FIBA writes some events late: 104 events of 13 games have a clock
    that goes back (by a second or two, a few by up to 23), and in 125835 a missed shot entered late shares its second with the rebound that follows it and comes AFTER it in the sequence. Inferring offensive or
    defensive from the last miss put those rebounds in the wrong place; the page says which each one is (``offensive rebound``), and its official box counts by that."""

    def test_a_missed_shot_entered_late_does_not_change_whose_rebound_it_is(self, pages, docs):
        result = reconcile_game(docs["125835"])
        assert result.reliable and result.mismatches() == [], [(c.team_id, c.stat, c.pbp, c.official) for c in result.mismatches()]
        late = [e for e in pages["125835"]["events"] if e["code"] == "REB"]
        assert late                                                                    # the game has rebounds the tracker rule used to misplace

    def test_a_game_with_the_clock_of_several_events_going_back_reconciles_too(self, docs):
        assert reconcile_game(docs["125814"]).reliable

    def test_the_label_of_the_page_is_what_the_lines_say(self, docs):
        texts = [l["text"] for l in docs["125835"]["PLAYBYPLAY"]["LINES"] if l["action"] == "rebound" and l["idPlayer"]]
        assert texts and all("REBOTE OFENSIVO" in t or "REBOTE DEFENSIVO" in t for t in texts)

    def test_the_label_does_not_depend_on_how_the_page_capitalises_it(self, pages, docs):
        """The senior men's game writes ``Offensive rebound`` where the U18 ones write ``offensive rebound``; reading only one of them labelled every rebound of the other as defensive."""
        for name in ("123004", "125809"):
            offensive = sum(1 for e in pages[name]["events"] if e["code"] == "REB" and "offensive" in e["text"].lower())
            assert offensive > 0 and sum("REBOTE OFENSIVO" in l["text"] for l in docs[name]["PLAYBYPLAY"]["LINES"] if l["idPlayer"]) == offensive

    def test_a_rebound_whose_text_says_neither_is_left_without_a_label_for_the_tracker_to_decide(self, pages):
        odd = copy.deepcopy(pages["125809"])
        victim = next(e for e in odd["events"] if e["code"] == "REB")
        victim["text"] = "rebound"
        line = next(l for l in to_canonical(odd)["PLAYBYPLAY"]["LINES"] if l["action"] == "rebound" and l["idPlayer"] == f"fiba:{victim['player']}" and l["time"] == victim["clock"].rjust(5, "0"))
        assert "OFENSIVO" not in line["text"] and "DEFENSIVO" not in line["text"] and line["text"].endswith("REBOTE")

    def test_the_lines_keep_the_clock_the_page_wrote_they_are_not_corrected_to_fit(self, pages, docs):
        """Inventing times to make the sequence monotone would be inventing data: the clock of each line is the page's."""
        by_order = {(e["period"], e["id"]): e["clock"] for e in pages["125814"]["events"] if e["code"] in ("P2", "P3", "FT")}
        lines = [l for l in docs["125814"]["PLAYBYPLAY"]["LINES"] if l["action"] in ("shoot", "fthrow")]
        assert sorted(l["time"] for l in lines) == sorted(f"{int(c.split(':')[0]):02d}:{c.split(':')[1]}" for c in by_order.values())


class TestSubstitutions:
    def test_a_substitution_that_names_who_comes_in_and_who_goes_out_is_two_lines_one_for_each(self, pages, docs):
        """The senior men's game writes each substitution as one event (``pId`` enters, ``p2Id`` leaves); the U18 ones as two."""
        paired = [e for e in pages["123004"]["events"] if e["code"] == "SUBST" and e["player2"] is not None]
        assert paired and all(e["in"] == "IN" for e in paired)
        lines = docs["123004"]["PLAYBYPLAY"]["LINES"]
        entered, left = [l for l in lines if "ENTRA A PISTA" in l["text"]], [l for l in lines if "SALE DE PISTA" in l["text"]]
        assert len(entered) == len(left) == len(paired)
        sample = paired[0]
        assert (sample["player"], sample["player2"]) and any(l["idPlayer"] == f"fiba:{sample['player2']}" and "SALE DE PISTA" in l["text"] for l in left)

    def test_the_two_lines_of_a_substitution_have_the_same_clock_and_the_one_who_leaves_comes_first(self, pages, docs):
        lines = docs["123004"]["PLAYBYPLAY"]["LINES"]
        for i, line in enumerate(lines):
            if "ENTRA A PISTA" in line["text"] and i > 0 and "SALE DE PISTA" in lines[i - 1]["text"]:
                assert (lines[i - 1]["quarter"], lines[i - 1]["time"]) == (line["quarter"], line["time"])
                return
        pytest.fail("no substitution of two lines found")


class TestOvertime:
    def test_an_overtime_is_a_fifth_period_with_its_own_score_and_clock(self, docs):
        doc = docs[OVERTIME]
        assert doc["HEADER"]["quarter"] == 5 and len(doc["HEADER"]["QUARTERS"]["QUARTER"]) == 5
        assert max(int(l["quarter"]) for l in doc["PLAYBYPLAY"]["LINES"]) == 5
        assert max(e.elapsed for e in game_events(doc, False)) > 40 * 60

    def test_its_quarters_add_up_to_the_final_score(self, docs):
        doc = docs[OVERTIME]
        quarters = doc["HEADER"]["QUARTERS"]["QUARTER"]
        assert [sum(int(q[s]) for q in quarters) for s in ("scoreA", "scoreB")] == [int(t["pts"]) for t in doc["HEADER"]["TEAM"]]


class TestWhatABrokenSourceLooksLike:
    def test_a_made_shot_that_is_missing_from_the_play_by_play_makes_the_game_unreliable(self, pages):
        broken = copy.deepcopy(pages["125809"])
        victim = next(e for e in broken["events"] if e["code"] == "P3" and e["made"])
        broken["events"].remove(victim)
        result = reconcile_game(to_canonical(broken))
        assert not result.reliable
        assert {(c.stat) for c in result.mismatches(CORE_STATS)} >= {"PTS", "FGM", "FGA", "3PM", "3PA"}

    def test_a_code_the_converter_does_not_know_is_kept_as_a_line_that_says_nothing_to_the_engine(self, pages):
        odd = copy.deepcopy(pages["125809"])
        odd["events"].insert(5, {**odd["events"][5], "id": "9999", "code": "XYZ", "text": "something new", "player": None, "team": None})
        doc = to_canonical(odd)
        line = next(l for l in doc["PLAYBYPLAY"]["LINES"] if "something new" in l["text"])
        assert line["action"] == "other" and parse_line(line).kind == "other"

    def test_a_page_with_no_play_by_play_converts_and_is_unreliable_it_does_not_fail(self, pages):
        empty = {**copy.deepcopy(pages["125809"]), "events": []}
        doc = to_canonical(empty)
        assert doc["PLAYBYPLAY"]["LINES"] == [] and validate_game(doc, "M") == []
        assert not reconcile_game(doc).reliable

    def test_the_events_of_the_page_are_not_changed_by_converting_them(self, pages):
        before = copy.deepcopy(pages["125809"])
        to_canonical(pages["125809"])
        assert pages["125809"] == before

    def test_converting_twice_gives_the_same_document(self, pages):
        assert to_canonical(pages["123043"]) == to_canonical(pages["123043"])


class TestTheGender:
    @pytest.mark.parametrize("competition, gender", [({"gender": "Men"}, "M"), ({"gender": "Women"}, "F")])
    def test_it_comes_from_the_competition_of_the_page(self, competition, gender):
        assert gender_of(competition) == gender

    @pytest.mark.parametrize("competition", [{}, {"gender": ""}, {"gender": "Mixed"}, {"gender": None}])
    def test_a_competition_that_does_not_say_it_is_refused_not_guessed(self, competition):
        with pytest.raises(ValueError):
            gender_of(competition)
