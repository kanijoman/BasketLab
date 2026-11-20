"""A game of ACB as the canonical document of an external source (#886, D2e of epic #872): the REAL pages of ``tests/fixtures/acb`` and the real calendar answer, converted to the FEB document with ``_league: acb`` and
every id prefixed.

The conversion has to satisfy, on every real game, what the epic asks of an external source: ``validate_game`` finds nothing wrong, ``reconcile_game`` finds the play-by-play and the official box in agreement on
the core statistics, and the lines are written as the engine reads the FEB ones. ACB writes its plays as numeric codes with no table: the ones this converter knows are the ones whose meaning the real games
prove (a made two changes the score by 2 and the twoPointers of the player...), and the rest are kept as ``other`` lines so that nothing of the page is lost.
"""
import copy
import gzip
import json
from collections import Counter
from pathlib import Path

import pytest

from src.external.acb_canonical import KNOWN_CODES, UNKNOWN_CODES, to_canonical
from src.external.acb_page import parse_game
from src.live_core.events import parse_line
from src.market.box_reconciliation import CORE_STATS, reconcile_game
from src.market.canonical import validate_game
from src.pbp.game_events import game_events

FIX = Path(__file__).resolve().parent / "fixtures" / "acb"
ENTRY = {"competition": "Liga Endesa", "season_value": "2026", "season_label": "2026/2027", "league": "acb", "gender": "M", "acb": {"competition_id": 1, "edition_id": 91}}


def flight(name):
    return gzip.decompress((FIX / f"{name}.flight.gz").read_bytes()).decode("utf-8")


@pytest.fixture(scope="module")
def parsed():
    return parse_game(flight("105383.estadisticas"), flight("105383.jugadas"))


@pytest.fixture(scope="module")
def match():
    calendar = json.loads((FIX / "team-matches.json").read_text(encoding="utf-8"))["matches"]
    return next(m for m in calendar if m["id"] == 105383)


@pytest.fixture(scope="module")
def doc(parsed, match):
    return to_canonical(parsed, match, ENTRY)


class TestTheHeader:
    def test_the_game_says_where_it_comes_from_and_what_it_is(self, doc):
        assert (doc["_id"], doc["_league"], doc["_season"]) == ("acb:105383", "acb", "2026")
        header = doc["HEADER"]
        assert (header["competition"], header["CompID"], header["game_code"], header["status"]) == ("Liga Endesa", "1", "105383", "3")
        assert header["place"] == "Movistar Arena" and header["round"] == "Jornada 1"

    def test_the_kick_off_is_the_local_time_in_madrid(self, doc):
        assert doc["HEADER"]["starttime"] == "27-09-2026 - 19:00"                      # the calendar says 17:00Z and Madrid is on summer time

    def test_the_teams_have_their_score_and_the_points_of_each_quarter(self, doc):
        teams = doc["HEADER"]["TEAM"]
        assert [(t["id"], t["name"], t["pts"]) for t in teams] == [("acb:4476", "Real Madrid", "89"), ("acb:4477", "Unicaja", "87")]
        quarters = doc["HEADER"]["QUARTERS"]["QUARTER"]
        assert len(quarters) == 4 and sum(int(q["scoreA"]) for q in quarters) == 89 and sum(int(q["scoreB"]) for q in quarters) == 87

    def test_it_is_valid_for_the_canonical_contract(self, doc):
        assert validate_game(doc, "M") == []


class TestTheBox:
    def test_the_players_are_the_official_ones_with_their_minutes_in_seconds_and_prefixed_ids(self, doc):
        home = doc["BOXSCORE"]["TEAM"][0]
        assert home["id"] == "acb:4476" and home["win_lose"] == "W" and doc["BOXSCORE"]["TEAM"][1]["win_lose"] == "L"
        luwawu = next(p for p in home["PLAYER"] if p["id"] == "acb:30003351")
        assert (luwawu["pts"], luwawu["p2m"], luwawu["p3a"], luwawu["min"], luwawu["sta"], luwawu["no"]) == ("14", "4", "6", str(23 * 60 + 56), "*", "3")
        assert sum(1 for p in home["PLAYER"] if p["sta"] == "*") == 5

    def test_the_total_is_the_players_and_what_the_team_did_itself_is_apart(self, doc, parsed):
        for side, box in (("home", doc["BOXSCORE"]["TEAM"][0]), ("away", doc["BOXSCORE"]["TEAM"][1])):
            players = parsed[side]["players"]
            assert int(box["TOTAL"]["ro"]) == sum(p["totals"]["offRebounds"] for p in players)
            assert int(box["TOTAL"]["ro"]) + int(box["TEAMACTIONS"]["ro"]) == parsed[side]["totals"]["offRebounds"]
            assert int(box["TOTAL"]["pts"]) == parsed[side]["totals"]["points"]

    def test_the_shots_made_and_attempted_add_up(self, doc):
        for team in doc["BOXSCORE"]["TEAM"]:
            total = team["TOTAL"]
            assert int(total["fgm"]) == int(total["p2m"]) + int(total["p3m"]) and int(total["fga"]) == int(total["p2a"]) + int(total["p3a"])
            assert int(total["pts"]) == 2 * int(total["p2m"]) + 3 * int(total["p3m"]) + int(total["p1m"])


class TestThePlayByPlay:
    def test_every_play_is_a_line_with_the_clock_the_score_and_a_unique_number(self, doc, parsed):
        lines = doc["PLAYBYPLAY"]["LINES"]
        drawn = sum(1 for p in parsed["plays"] if p["type"] == 110)                       # a foul drawn goes with its foul, not as a line of its own
        assert len(lines) == len(parsed["plays"]) - drawn and [l["num"] for l in lines] == [str(i) for i in range(1, len(lines) + 1)]
        assert all(l["quarter"] in ("1", "2", "3", "4") and len(l["time"]) == 5 and l["scoreA"].isdigit() and l["scoreB"].isdigit() for l in lines)
        assert (lines[-1]["scoreA"], lines[-1]["scoreB"]) == ("89", "87")

    def test_the_actions_are_the_ones_the_engine_reads_and_the_text_has_its_keywords(self, doc):
        lines = doc["PLAYBYPLAY"]["LINES"]
        by_action = Counter(l["action"] for l in lines)
        assert {"shoot", "fthrow", "rebound", "assist", "recovery", "lose", "blockshot", "foul", "subst", "period"} <= set(by_action)
        texts = [l["text"] for l in lines]
        assert any("TIRO DE 3 FALLADO" in t for t in texts) and any("TIRO DE 2 ANOTADO" in t for t in texts) and any("MATE ANOTADO" in t for t in texts)
        assert any("REBOTE DE EQUIPO" in t for t in texts) and any("ENTRA A PISTA" in t for t in texts) and any("SALE DE PISTA" in t for t in texts)

    def test_a_player_line_has_the_prefixed_ids_and_the_team_and_the_name(self, doc):
        line = next(l for l in doc["PLAYBYPLAY"]["LINES"] if "Amine Noua" in l["text"] and "TIRO DE 3 FALLADO" in l["text"])
        assert line["idPlayer"] == line["idLicense"] == "acb:30001137" and line["idTeam"] == "acb:4477" and line["text"].startswith("(Unicaja) Amine Noua: ")

    def test_the_fouls_are_counted_per_player_and_each_foul_drawn_goes_with_its_foul(self, doc, parsed):
        lines = doc["PLAYBYPLAY"]["LINES"]
        counted = Counter(l["idPlayer"] for l in lines if l["action"] == "foul")
        for side in ("home", "away"):
            for p in parsed[side]["players"]:
                assert counted.get(f"acb:{p['id']}", 0) == p["totals"].get("personalFouls", 0), p["name"]
        assert any(l.get("logParam4") for l in lines if l["action"] == "foul")

    def test_a_substitution_is_a_pair_of_lines_the_one_who_leaves_and_the_one_who_enters(self, doc):
        subst = [l for l in doc["PLAYBYPLAY"]["LINES"] if l["action"] == "subst"]
        assert len(subst) == 104 * 2 and Counter("SALE" in l["text"] for l in subst) == Counter({True: 104, False: 104})

    def test_the_engine_reads_every_line(self, doc):
        for line in doc["PLAYBYPLAY"]["LINES"]:
            assert parse_line(line) is not None, line

    def test_the_codes_that_are_not_known_are_kept_as_other_lines_and_listed_not_dropped(self, doc, parsed):
        others = [l for l in doc["PLAYBYPLAY"]["LINES"] if l["action"] == "other"]
        assert others and all("ACB" in l["text"] or "RECIBIDA" in l["text"] or "BLOQUEO" in l["text"] or "QUINTETO" in l["text"] for l in others)
        seen = {p["type"] for p in parsed["plays"]}
        assert seen <= KNOWN_CODES | UNKNOWN_CODES and not (KNOWN_CODES & UNKNOWN_CODES)          # every code of the real game is either proved or listed as not known

    def test_the_game_of_2019_20_has_no_code_that_nobody_has_seen(self):
        from src.external.acb_page import parse_plays

        assert {p["type"] for p in parse_plays(flight("18665.jugadas"))} <= KNOWN_CODES | UNKNOWN_CODES


class TestWhatTheEpicAsks:
    def test_the_play_by_play_and_the_official_box_agree_on_the_core_statistics(self, doc):
        result = reconcile_game(doc)
        assert [c for c in result.mismatches(CORE_STATS)] == [] and result.reliable

    def test_the_engine_reads_every_shot_of_the_official_box(self, doc):
        events = [e for e in game_events(doc, False) if not e.deleted]
        attempts = sum(int(t["TOTAL"][k]) for t in doc["BOXSCORE"]["TEAM"] for k in ("p1a", "p2a", "p3a"))
        assert sum(1 for e in events if e.kind in ("fg2", "fg3", "ft")) == attempts
        assert Counter(e.kind for e in events)["timeout"] == 7 and Counter(e.kind for e in events)["period_start"] == 4

    def test_converting_changes_nothing_of_the_game_read_and_is_the_same_twice(self, parsed, match):
        before = copy.deepcopy(parsed)
        first = to_canonical(parsed, match, ENTRY)
        assert parsed == before and to_canonical(parsed, match, ENTRY) == first


def test_a_game_that_is_not_finished_or_a_calendar_of_another_game_is_refused(parsed, match):
    with pytest.raises(ValueError, match="finished"):
        to_canonical({**parsed, "finished": False}, match, ENTRY)
    with pytest.raises(ValueError, match="same game"):
        to_canonical(parsed, {**match, "id": 1}, ENTRY)
