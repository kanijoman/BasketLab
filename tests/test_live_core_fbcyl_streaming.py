"""A FBCYL match followed LIVE through the web's streaming service becomes the FEB document the engine reads (issue #446, GO of #444).

Real readings of Universidad de Salamanca – UNILEON (7/11/2026, 81-75) taken every few minutes by the recorder (``tests/fixtures/fbcyl_streaming_20261107.json.gz``), plus the
moves of ``msstats`` once the match ended. What the streaming does differently from ``msstats`` and the adapter must resolve so that the app treats both leagues the same:

* its moves are written in CATALAN («Cistella de 2», «Surt del camp»); ``idMove`` is the same number in both, so it decides what a move is;
* the match is in progress: the header is not FINAL, it carries the period and the clock REMAINING (``matchTime``);
* the shots carry their coordinates in the players' stats: they feed the same shot zones as FEB's SHOTCHART (FBCYL folds both teams into one half court).
"""
import gzip
import json
from collections import Counter
from pathlib import Path

import pytest

from src.live_core.engine import LiveEngine
from src.live_core.fbcyl_adapter import from_streaming, to_feb_document
from src.live_core.zones import classify_fiba, feb_to_fiba

FIXTURE = Path(__file__).parent / "fixtures" / "fbcyl_streaming_20261107.json.gz"
HOME, AWAY = "39731", "39609"            # teamIdExtern: Salamanca (home), UNILEON


@pytest.fixture(scope="module")
def recording():
    return json.loads(gzip.open(FIXTURE).read())


@pytest.fixture(scope="module")
def readings(recording):
    return recording["readings"]


def _lines(doc):
    return doc["PLAYBYPLAY"]["LINES"]


class TestTheMovesInCatalan:
    def test_they_are_the_same_lines_as_the_ones_of_msstats_in_castilian_regression(self, recording, readings):
        """The streaming said «Cistella de 2» and the adapter, written for «Canasta de 2», left every move as «other»: no points, no rebounds, nothing."""
        live = _lines(from_streaming(readings[-1]))
        after = _lines(to_feb_document({"uuid": "u", "moves": recording["msstats_moves"], "stats": readings[-1]}))
        kinds = lambda lines: Counter(l["action"] for l in lines)          # noqa: E731
        assert kinds(live)["shoot"] > 100                                  # shots were recognised (they were all «other» before)
        assert (kinds(after) - kinds(live)).total() <= 2 and not kinds(live) - kinds(after)     # the same kinds, but for the 2 moves msstats has and the last reading did not

    def test_a_foul_without_its_count_is_still_a_foul(self):
        doc = from_streaming({"idMatchExtern": 1, "localId": 1, "visitId": 2, "period": 1, "matchTime": {"minute": 9, "second": 0}, "periodDurationList": [10],
                              "moves": [{"idTeam": 1, "actorId": 7, "actorName": "A B", "idMove": 531, "move": "Falta", "period": 1, "min": 9, "sec": 30, "score": "0-0"}],
                              "teams": [{"teamIdIntern": 1, "teamIdExtern": 10, "name": "A", "players": [], "data": {}}, {"teamIdIntern": 2, "teamIdExtern": 20, "name": "B", "players": [], "data": {}}]})
        assert [l["action"] for l in _lines(doc) if l["action"] != "period"] == ["foul"]

    def test_the_score_of_the_lines_is_kept_for_the_baskets(self, readings):
        made = [l for l in _lines(from_streaming(readings[-1])) if l["scoreA"] is not None]
        assert made and (made[-1]["scoreA"], made[-1]["scoreB"]) == ("81", "75")


class TestTheHeaderOfAMatchInProgress:
    def test_it_is_not_final_and_has_the_period_and_the_clock_remaining(self, readings):
        header = from_streaming(readings[4])["HEADER"]                    # 3rd quarter, 8:14 left
        assert (header["status"], header["quarter"], header["time"]) == ("2", "3", "08:14")
        assert [t["pts"] for t in header["TEAM"]] == ["40", "33"] and header["source"] == "fbcyl"

    def test_when_the_match_is_over_it_is_final(self, readings):
        header = from_streaming(readings[-1], finished=True)["HEADER"]
        assert (header["status"], header["time"]) == ("3", "FINAL")

    def test_the_teams_are_the_stable_ids_with_the_home_team_first(self, readings):
        assert [t["id"] for t in from_streaming(readings[0])["HEADER"]["TEAM"]] == [HOME, AWAY]


class TestTheEngineOnTheStream:
    def test_followed_reading_by_reading_it_ends_with_the_final_score_and_never_goes_back(self, readings):
        engine, last = LiveEngine(), -1
        for body in readings:
            snap = engine.update(from_streaming(body))
            assert snap["elapsed"] >= last
            last = snap["elapsed"]
        assert snap["score"] == {HOME: 81, AWAY: 75}
        assert snap["period"] == 4

    def test_a_reading_repeated_changes_nothing(self, readings):
        engine = LiveEngine()
        first = engine.update(from_streaming(readings[5]))
        again = engine.update(from_streaming(readings[5]))
        assert (first["score"], first["elapsed"], first["zones"]) == (again["score"], again["elapsed"], again["zones"])

    def test_the_players_have_their_numbers_and_their_minutes(self, readings):
        snap = LiveEngine().update(from_streaming(readings[-1]))
        played = [p for p in snap["players"].values() if p["minutes"] > 0]
        assert len(played) >= 14 and all(p.get("no") for p in played)


class TestTheShotZones:
    @staticmethod
    def _points(body):
        for team in body["teams"]:
            for player in team["players"]:
                for key, points in player["data"].items():
                    if isinstance(points, list) and points and isinstance(points[0], dict) and "xnormalize" in points[0]:
                        for p in points:
                            yield team["teamIdExtern"], key, p

    def test_every_shot_with_coordinates_is_in_a_zone_of_its_team(self, readings):
        body = readings[-1]
        snap = LiveEngine().update(from_streaming(body))
        expected = Counter()
        for team, _key, p in self._points(body):
            expected[str(team)] += 1
        got = {tid: sum(cell["a"] for cell in zones.values()) for tid, zones in snap["zones"].items()}
        assert got == dict(expected) and sum(got.values()) == 147

    def test_the_zone_is_the_one_of_a_half_court_as_the_rest_of_fbcyl_regression(self, readings):
        """FBCYL folds every team into one half court: the zones are those of ``feb_to_fiba(x, y, 0)`` for both teams (a shot of the second team was mirrored, wrongly, before)."""
        body = readings[-1]
        snap = LiveEngine().update(from_streaming(body))
        expected = Counter()
        for team, _key, p in self._points(body):
            x, y = feb_to_fiba(float(p["xnormalize"]), float(p["ynormalize"]), 0)
            expected[(str(team), classify_fiba(x, y)["zone"])] += 1
        got = Counter({(tid, zone): cell["a"] for tid, zones in snap["zones"].items() for zone, cell in zones.items()})
        assert got == expected

    def test_made_and_missed_are_told_apart(self, readings):
        body = readings[-1]
        snap = LiveEngine().update(from_streaming(body))
        made = sum(1 for _t, key, _p in self._points(body) if "Successful" in key)
        assert sum(cell["m"] for zones in snap["zones"].values() for cell in zones.values()) == made

    def test_a_shot_of_a_player_is_in_the_zones_of_that_player(self, readings):
        snap = LiveEngine().update(from_streaming(readings[-1]))
        with_zones = [pid for table in snap["zone_players"].values() for pid, zones in table.items() if zones]
        assert len(with_zones) >= 12 and sum(c["a"] for t in snap["zone_players"].values() for z in t.values() for c in z.values()) == 147
