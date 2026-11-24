"""A game of the Euroleague as the canonical document of an external source (#1038, D6a of epic #872): the REAL answers of ``tests/fixtures/euroleague`` (a EuroLeague game, one with an overtime, a EuroCup one and a
U18 tournament one) converted to the FEB document with ``_league: euroleague`` and every id prefixed.

The conversion has to satisfy, on every real game, what the epic asks of an external source: ``validate_game`` finds nothing wrong, ``reconcile_game`` finds the play by play and the official box in agreement
(the nine core statistics AND the informative ones: the spike measured 72 of 72 games), and the lines are written as the engine reads the FEB ones.
"""
import copy

import pytest

from euroleague_helpers import read_game

from src.external.euroleague_canonical import KNOWN_CODES, to_canonical
from src.live_core.events import parse_line
from src.market.box_reconciliation import CORE_STATS, reconcile_game
from src.market.canonical import validate_game
from src.pbp.game_events import game_events

ENTRY = {"competition": "EuroLeague", "season_value": "2025", "season_label": "2025/2026", "league": "euroleague", "gender": "M", "euroleague": {"competition": "E"}}
GAMES = {"E2025_1": ("E2025_1", "games_E2025", 1), "E2025_397": ("E2025_397", "games_E2025", 397), "U2025_195": ("U2025_195", "games_U2025", 195), "JTA25_9": ("JTA25_9", "games_JTA25", 9)}


@pytest.fixture(scope="module", params=sorted(GAMES))
def any_doc(request):
    return to_canonical(read_game(*GAMES[request.param]), ENTRY)


@pytest.fixture(scope="module")
def parsed():
    return read_game(*GAMES["E2025_1"])


@pytest.fixture(scope="module")
def doc(parsed):
    return to_canonical(parsed, ENTRY)


class TestTheHeader:
    def test_the_game_says_where_it_comes_from_and_what_it_is(self, doc):
        assert (doc["_id"], doc["_league"], doc["_season"]) == ("euroleague:E2025_1", "euroleague", "2025")
        header = doc["HEADER"]
        assert (header["competition"], header["round"], header["status"], header["game_code"]) == ("EuroLeague", "Round 1", "3", "1")
        assert [t["id"] for t in header["TEAM"]] == ["euroleague:IST", "euroleague:TEL"] and [t["pts"] for t in header["TEAM"]] == ["85", "78"]

    def test_the_kick_off_is_in_the_time_of_madrid_like_the_other_sources_of_a_spanish_staff(self, doc):
        assert doc["HEADER"]["starttime"] == "30-09-2025 - 19:45"            # 17:45 UTC, summer time

    def test_the_points_of_each_quarter_are_the_ones_of_the_calendar_and_an_overtime_is_a_fifth(self, doc):
        assert [(q["scoreA"], q["scoreB"]) for q in doc["HEADER"]["QUARTERS"]["QUARTER"]] == [("21", "19"), ("19", "25"), ("20", "15"), ("25", "19")]
        overtime = to_canonical(read_game(*GAMES["E2025_397"]), ENTRY)
        assert len(overtime["HEADER"]["QUARTERS"]["QUARTER"]) == 5 and overtime["PLAYBYPLAY"]["hasExtension"] is True and doc["PLAYBYPLAY"]["hasExtension"] is False


class TestTheBox:
    def test_the_box_is_the_official_one_with_the_minutes_in_seconds_and_the_bio_of_each_player(self, doc):
        home = doc["BOXSCORE"]["TEAM"][0]
        assert (home["id"], home["win_lose"], home["teamCode"]) == ("euroleague:IST", "W", "IST")
        player = next(p for p in home["PLAYER"] if p["id"] == "euroleague:009549")
        assert (player["name"], player["min"], player["sta"], player["no"]) == ("CORDINIER, ISAIA", "1850", "*", "10")
        assert (player["birth"], player["height"], player["nationality"]) == ("1996-11-28", "196", "France")

    def test_the_total_is_the_sum_of_the_players_and_the_team_own_apart_and_together_they_are_the_official_total(self, doc):
        for team in doc["BOXSCORE"]["TEAM"]:
            for stat in ("pts", "p2m", "p2a", "p3m", "p3a", "p1m", "p1a", "assist", "st", "pf"):
                assert int(team["TOTAL"][stat]) == sum(int(p[stat]) for p in team["PLAYER"])
            assert int(team["TOTAL"]["to"]) == sum(int(p["to"]) for p in team["PLAYER"]) + int(team["TEAMACTIONS"]["to"])          # the official total of turnovers has the team's own
        home = doc["BOXSCORE"]["TEAM"][0]
        assert int(home["TOTAL"]["rt"]) + int(home["TEAMACTIONS"]["rt"]) == 40 and home["TEAMACTIONS"]["rt"] == "4"

    def test_the_turnovers_of_the_team_itself_are_in_the_official_total_of_an_overtime_game(self):
        """The game of Zalgiris: 7 turnovers of its players and 3 of the team, 10 in the official total, as many as the play by play counts."""
        zalgiris = next(t for t in to_canonical(read_game(*GAMES["E2025_397"]), ENTRY)["BOXSCORE"]["TEAM"] if t["teamCode"] == "ZAL")
        assert (zalgiris["TOTAL"]["to"], zalgiris["TEAMACTIONS"]["to"]) == ("10", "3")

    def test_a_player_who_did_not_play_has_no_minutes_but_is_in_the_box(self, doc):
        beaubois = next(p for p in doc["BOXSCORE"]["TEAM"][0]["PLAYER"] if p["id"] == "euroleague:006590")
        assert beaubois["min"] == "0" and beaubois["sta"] is None


class TestThePlayByPlay:
    def test_the_lines_are_numbered_in_order_and_carry_the_prefixed_ids(self, doc):
        lines = doc["PLAYBYPLAY"]["LINES"]
        assert [l["num"] for l in lines] == [str(i) for i in range(1, len(lines) + 1)]
        shot = next(l for l in lines if l["action"] == "shoot")
        assert (shot["idTeam"], shot["idPlayer"], shot["quarter"], shot["time"]) == ("euroleague:IST", "euroleague:014102", "1", "09:39") and "TIRO DE 2 ANOTADO" in shot["text"]

    def test_a_rebound_of_the_team_has_no_player_and_says_whose(self, doc):
        rebound = next(l for l in doc["PLAYBYPLAY"]["LINES"] if l["action"] == "rebound" and not l["idPlayer"])
        assert "REBOTE DE EQUIPO" in rebound["text"] and rebound["idTeam"] == "euroleague:TEL"

    def test_the_engine_reads_every_line_of_every_real_game(self, any_doc):
        assert game_events(any_doc, False)
        assert all(parse_line(line) is not None for line in any_doc["PLAYBYPLAY"]["LINES"])

    def test_the_codes_of_the_real_games_are_all_known_or_listed_as_not_understood(self):
        seen = set()
        for args in GAMES.values():
            seen |= {p["type"] for p in read_game(*args)["plays"]}
        assert seen <= KNOWN_CODES, sorted(seen - KNOWN_CODES)


class TestAgainstTheOfficialBox:
    def test_every_real_game_is_valid_and_reliable_with_the_core_statistics_exact(self, any_doc):
        assert validate_game(any_doc, "M") == []
        result = reconcile_game(any_doc)
        assert result.reliable, result.mismatches(CORE_STATS)

    def test_the_informative_statistics_agree_too(self, any_doc):
        result = reconcile_game(any_doc)
        assert result.mismatches() == []

    def test_a_corrupted_play_by_play_makes_the_game_not_reliable_it_is_never_corrected(self, parsed):
        broken = copy.deepcopy(parsed)
        made = next(p for p in broken["plays"] if p["type"] == "2FGM")
        made["type"] = "2FGA"
        assert not reconcile_game(to_canonical(broken, ENTRY)).reliable


class TestTheShotChart:
    def test_every_field_goal_has_its_shot_in_percentages_of_the_whole_court(self, doc):
        chart = doc["SHOTCHART"]
        assert len(chart["SHOTS"]) == 131 and chart["TEAM"]
        assert all(0 <= float(s["x"]) <= 100 and 0 <= float(s["y"]) <= 100 for s in chart["SHOTS"])
        assert {s["team"] for s in chart["SHOTS"]} == {"0", "1"} and chart["SHOTS"][0]["player"] == "88"

    def test_a_game_with_a_field_goal_missing_its_shot_has_no_chart_at_all(self, parsed):
        broken = copy.deepcopy(parsed)
        broken["shots"].pop()
        chart = to_canonical(broken, ENTRY)["SHOTCHART"]
        assert chart["SHOTS"] == [] and chart["TEAM"] == []

    def test_the_two_point_shots_fall_inside_the_arc_and_the_threes_outside_it(self, parsed):
        """The coordinates are centimetres from the hoop: the hoop is at 0,0 and the line of three is 6.75 m (a corner three is 6.60 m)."""
        for shot in parsed["shots"]:
            distance = (shot["x"] ** 2 + shot["y"] ** 2) ** 0.5
            assert (distance >= 650) if shot["points"] == 3 else (distance <= 780), shot

    def test_an_entry_with_a_gender_that_is_not_m_or_f_is_refused(self, parsed):
        with pytest.raises(ValueError):
            to_canonical(parsed, {**ENTRY, "gender": "X"})
