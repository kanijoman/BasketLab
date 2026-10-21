"""FBCYL games in the shape of FEB's (issue #445, epic #435): ``{uuid, moves, stats}`` -> ``HEADER`` / ``BOXSCORE`` / ``PLAYBYPLAY.LINES``.

Everything the live engine, the package builder, the rule evaluator and the demo generator read is the FEB document; FBCYL has its own feed
(moves with the clock REMAINING in the period, ``teamIdIntern`` per game and ``teamIdExtern`` stable, no shot chart). The adapter is what lets
them work on it. Checked on a real game of 1ª División Femenina (Universidad de Burgos - Cañadío Santander, 55-75).
"""
import copy
import gzip
import json
from collections import Counter
from pathlib import Path

import pytest

from src.live_core.engine import LiveEngine
from src.live_prep.fbcyl_adapter import to_feb_document

FIXTURE = Path(__file__).parent / "fixtures" / "fbcyl_game_ok.json.gz"
HOME, AWAY = "39675", "40288"      # teamIdExtern (stable), home first


@pytest.fixture(scope="module")
def raw():
    return json.loads(gzip.open(FIXTURE).read())


@pytest.fixture
def game(raw):
    return to_feb_document(copy.deepcopy(raw))


class TestHeader:
    def test_teams_are_home_first_with_the_stable_id_and_the_final_score(self, game):
        assert [(t["id"], t["pts"]) for t in game["HEADER"]["TEAM"]] == [(HOME, "55"), (AWAY, "75")]
        assert game["HEADER"]["TEAM"][0]["name"].startswith("UNIVERSIDAD DE BURGOS")

    def test_it_is_a_finished_game_with_its_kick_off_in_the_feb_format(self, game):
        assert str(game["HEADER"]["status"]) == "3"
        assert game["HEADER"]["starttime"] == "04-10-2026 - 14:30"

    def test_the_match_code_is_the_public_match_id_and_the_uuid_is_kept(self, raw, game):
        assert game["_id"] == str(raw["stats"]["idMatchExtern"]) == "264330"
        assert game["HEADER"]["game_code"] == "264330" and game["HEADER"]["uuid"] == raw["uuid"]

    def test_the_competition_data_of_the_collection_is_kept(self, raw, game):
        assert game["_season"] == raw["_season"] and game["HEADER"]["competition"] == raw["_competition"]

    def test_the_game_is_marked_as_experimental_play_by_play(self, game):
        assert game["HEADER"]["source"] == "fbcyl"      # FBCYL's moves are annotated by the clubs (errors the feed does not fix)


class TestRoster:
    def test_both_teams_have_their_players_with_the_id_the_moves_use(self, raw, game):
        ids_in_moves = {str(m["actorId"]) for m in raw["moves"] if m["actorId"]}
        roster = {p["id"] for team in game["BOXSCORE"]["TEAM"] for p in team["PLAYER"]}
        assert ids_in_moves <= roster and [t["id"] for t in game["BOXSCORE"]["TEAM"]] == [HOME, AWAY]

    def test_a_player_has_her_number_and_name(self, game):
        player = game["BOXSCORE"]["TEAM"][0]["PLAYER"][0]
        assert player["no"] and player["name"] and "id" in player


class TestLines:
    def test_one_line_per_move_but_the_fouls_received_which_feb_does_not_have(self, raw, game):
        moves = Counter(m["move"] for m in raw["moves"])
        received = sum(v for k, v in moves.items() if k.startswith("Falta recibida"))
        periods = len({m["period"] for m in raw["moves"]})
        assert len(game["PLAYBYPLAY"]["LINES"]) == len(raw["moves"]) - received + periods      # + one "Comienzo del Cuarto" per period

    def test_lines_are_numbered_in_game_order_and_use_the_clock_remaining(self, game):
        lines = game["PLAYBYPLAY"]["LINES"]
        assert [int(l["num"]) for l in lines] == list(range(1, len(lines) + 1))
        assert lines[0]["action"] == "period" and lines[0]["time"] == "10:00" and lines[0]["quarter"] == "1"

    def test_the_teams_of_the_lines_are_the_stable_ids(self, game):
        assert {l["idTeam"] for l in game["PLAYBYPLAY"]["LINES"]} <= {HOME, AWAY, None}

    def test_every_action_is_one_the_engine_knows(self, game):
        assert {l["action"] for l in game["PLAYBYPLAY"]["LINES"]} <= {"shoot", "fthrow", "rebound", "lose", "recovery", "assist", "blockshot", "subst", "foul", "timeout", "period"}

    def test_the_engine_parses_every_line_into_its_kind(self, game):
        from src.live_core.events import parse_line

        kinds = Counter(parse_line(l).kind for l in game["PLAYBYPLAY"]["LINES"])
        assert kinds["other"] == 0
        assert kinds["fg2"] > 0 and kinds["fg3"] > 0 and kinds["ft"] > 0 and kinds["rebound"] > 0 and kinds["foul"] > 0 and kinds["sub_in"] > 0

    def test_made_and_missed_shots_keep_their_value(self, raw, game):
        from src.live_core.events import parse_line

        events = [parse_line(l) for l in game["PLAYBYPLAY"]["LINES"]]
        made = Counter(e.kind for e in events if e.made)
        assert made["fg2"] == sum(1 for m in raw["moves"] if m["move"] in ("Canasta de 2", "Mate"))
        assert made["fg3"] == sum(1 for m in raw["moves"] if m["move"] == "Canasta de 3")
        assert made["ft"] == sum(1 for m in raw["moves"] if m["move"] == "Canasta de 1")

    def test_the_fouls_carry_the_count_of_the_player(self, raw, game):
        from src.live_core.events import parse_line

        counts = [parse_line(l).pf_count for l in game["PLAYBYPLAY"]["LINES"] if l["action"] == "foul"]
        assert counts and all(c is not None and c >= 1 for c in counts)
        assert max(counts) == max(int(m["move"].split(",")[1].split("a")[0]) for m in raw["moves"] if m["move"].startswith("Falta, "))

    def test_made_shots_carry_the_score_of_the_moment(self, game):
        scored = [l for l in game["PLAYBYPLAY"]["LINES"] if l["scoreA"]]
        assert scored and (int(scored[-1]["scoreA"]), int(scored[-1]["scoreB"])) == (55, 75)

    def test_a_move_that_is_not_known_is_kept_as_other_not_lost(self, raw):
        odd = copy.deepcopy(raw)
        odd["moves"].insert(5, {**odd["moves"][5], "move": "Algo nuevo", "actorId": 0, "teamAction": True})
        lines = to_feb_document(odd)["PLAYBYPLAY"]["LINES"]
        assert any(l["text"].endswith("Algo nuevo") and l["action"] == "other" for l in lines)

    def test_a_game_without_moves_has_no_lines_and_does_not_fail(self, raw):
        empty = copy.deepcopy(raw)
        empty["moves"] = []
        assert to_feb_document(empty)["PLAYBYPLAY"]["LINES"] == []

    def test_the_other_foul_types_are_told_apart(self, raw):
        doc = copy.deepcopy(raw)
        base = next(m for m in doc["moves"] if m["move"].startswith("Falta, "))
        doc["moves"] += [{**base, "move": t} for t in ("Falta antideportiva", "Falta técnica", "Falta en ataque")]
        from src.live_core.events import parse_line

        types = [parse_line(l).foul_type for l in to_feb_document(doc)["PLAYBYPLAY"]["LINES"][-3:]]
        assert types == ["unsportsmanlike", "technical", "other"]


class TestShotChartAndInput:
    def test_the_shot_chart_is_empty_so_the_zone_rules_stay_off(self, game):
        assert game["SHOTCHART"]["SHOTS"] == []

    def test_the_source_document_is_not_modified(self, raw):
        before = json.dumps(raw, sort_keys=True)
        to_feb_document(raw)
        assert json.dumps(raw, sort_keys=True) == before


class TestEngine:
    def test_the_engine_replays_the_whole_game_to_the_final_score(self, game):
        snap = LiveEngine().update(game)
        assert snap["score"] == {HOME: 55, AWAY: 75}
        assert snap["elapsed"] == 2400

    def test_the_engine_finds_the_players_and_their_minutes(self, game):
        snap = LiveEngine().update(game)
        played = [p for p in snap["players"].values() if p["minutes"] > 0]
        assert len(played) >= 10 and sum(1 for p in played if p["team_id"] == HOME) >= 5

    def test_the_points_of_the_players_add_up_to_the_score(self, game):
        snap = LiveEngine().update(game)
        for team, points in ((HOME, 55), (AWAY, 75)):
            assert sum(p["pts"] for p in snap["players"].values() if p["team_id"] == team) == points
