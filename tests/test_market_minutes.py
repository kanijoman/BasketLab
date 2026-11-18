"""The minutes of the official box counted from the play-by-play (#963): the starting five of the box and the substitutions of the lines give each player's seconds on court.

The REAL FIBA games of ``tests/fixtures/fiba`` (an overtime one and two women's among them) are the base: on every player-game the count and the box agree within the tolerance. A minute that does not agree is
reported but never discards a game (as the information statistics), and a game whose lineup cannot be known (no starters in the box) has no minute check, which the report says.
"""
import copy
import gzip
from pathlib import Path

import pytest

from src.external.fiba_canonical import to_canonical
from src.external.fiba_page import parse_game
from src.market.box_reconciliation import reconcile_game, summarize
from src.market.minutes_reconciliation import MINUTES_TOLERANCE, minutes_checks

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "fiba"
GAMES = ["125809", "125803", "125812", "125859", "123004", "123043", "125835", "125814"]
OVERTIME = "123043"


@pytest.fixture(scope="module")
def docs():
    return {n: to_canonical(parse_game(gzip.decompress((FIXTURES / f"{n}.flight.gz").read_bytes()).decode("utf-8"))) for n in GAMES}


class TestOnRealGames:
    @pytest.mark.parametrize("name", GAMES)
    def test_every_player_game_agrees_with_the_official_minutes(self, docs, name):
        checks = minutes_checks(docs[name])
        assert len(checks) >= 16 and [c for c in checks if not c.ok] == []
        assert all(abs(c.pbp - c.official) <= MINUTES_TOLERANCE for c in checks)

    def test_the_overtime_game_counts_five_minutes_for_its_extra_period(self, docs):
        total = sum(c.pbp for c in minutes_checks(docs[OVERTIME]))
        assert total == 2 * 5 * (4 * 600 + 300)                              # five on court for each team during the whole game

    def test_a_player_who_did_not_play_has_no_check(self, docs):
        ids = {c.player_id for c in minutes_checks(docs["125809"])}
        assert "fiba:344984" not in ids                                       # the first of the box: 0 minutes, never on court

    def test_the_order_of_the_lines_does_not_change_the_count(self, docs):
        shuffled = copy.deepcopy(docs["125809"])
        shuffled["PLAYBYPLAY"]["LINES"].reverse()
        assert minutes_checks(shuffled) == minutes_checks(docs["125809"])


class TestWhatDoesNotAgree:
    def test_a_substitution_a_minute_late_is_reported_for_the_players_it_moves_and_the_game_stays_reliable(self, docs):
        doc = copy.deepcopy(docs["125809"])
        line = next(l for l in doc["PLAYBYPLAY"]["LINES"] if l["action"] == "subst" and l["text"].endswith("ENTRA A PISTA") and l["quarter"] == "2")
        minutes, seconds = line["time"].split(":")
        line["time"] = f"{max(int(minutes) - 1, 0):02d}:{seconds}"                         # a minute earlier on the clock
        bad = [c for c in minutes_checks(doc) if not c.ok]
        assert bad and line["idPlayer"] in {c.player_id for c in bad}
        assert reconcile_game(doc).reliable == reconcile_game(docs["125809"]).reliable        # minutes never discard a game

    def test_a_game_without_starters_in_its_box_has_no_minute_check(self, docs):
        doc = copy.deepcopy(docs["125809"])
        for team in doc["BOXSCORE"]["TEAM"]:
            for player in team["PLAYER"]:
                player["sta"] = None
        assert minutes_checks(doc) == ()


class TestInTheReport:
    def test_the_report_says_how_many_player_games_agree(self, docs):
        report = summarize([reconcile_game(docs[n]) for n in GAMES[:2]])
        minutes = report["minutes"]
        assert minutes["checked"] == minutes["match"] > 30 and minutes["mismatches"] == [] and "MIN" not in report["unchecked"]

    def test_a_game_with_no_minute_check_leaves_minutes_unchecked_in_the_report(self, docs):
        blind = copy.deepcopy(docs["125809"])
        for team in blind["BOXSCORE"]["TEAM"]:
            for player in team["PLAYER"]:
                player["sta"] = None
        assert summarize([reconcile_game(blind)])["unchecked"] == ["MIN"]

    def test_the_mismatches_of_the_report_name_the_game_and_the_player(self, docs):
        doc = copy.deepcopy(docs["125809"])
        victim = next(p for t in doc["BOXSCORE"]["TEAM"] for p in t["PLAYER"] if int(p["min"]) > 600)
        victim["min"] = str(int(victim["min"]) + 120)
        mismatch = summarize([reconcile_game(doc)])["minutes"]["mismatches"]
        assert [(m["game"], m["player"]) for m in mismatch] == [(doc["_id"], victim["id"])] and mismatch[0]["official"] - mismatch[0]["pbp"] == 120
