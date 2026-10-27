"""Jersey numbers inferred from the shot chart (issue #599).

The play-by-play does not carry the jersey number of a player (its lines have his ids), but every field goal of the SHOTCHART does: ``player`` is the NUMBER, ``team`` is 0/1,
and the shot has its quarter and clock. Joining each field goal of the play-by-play with its shot by (quarter, clock, team, made) says «this player wears this number».
On 60 matches of 2026/27 the join gave 1,174 pairs, all of them the number of the official box score, for 94 % of the players who play (the rest never shot).
It matters because the box score of the LIVE feed of 2ª and 3ª FEB has no ``no``: without it the zones per player of the shot chart could not be kept either.
"""
import copy
import json
from pathlib import Path

import pytest

from src.live_core.engine import LiveEngine
from src.live_core.jerseys import infer_numbers
from src.live_core.recorded_feed import RecordedFeed
from src.live_core.shots import ShotTracker
from tests.builders import OWN, RIVAL, Match

ROOT = Path(__file__).parent
TEAMS = [OWN, RIVAL]


def shot(quarter, clock, team, number, made, x="50", y="25"):
    return {"quarter": str(quarter), "t": clock, "team": str(team), "player": str(number), "m": "1" if made else "0", "x": x, "y": y}


def played():
    """p1 and p2 of the own team and r1 of the rival score and miss, through the real state machine."""
    m = Match().lineup(OWN, ["p1", "p2"], at=0).lineup(RIVAL, ["r1"], at=0)
    m.score(OWN, 3, at=60, player="p1").miss(OWN, at=120, kind="fg2", player="p2").score(RIVAL, 2, at=180, player="r1")
    return m


class TestTheJoin:
    def test_a_field_goal_and_its_shot_say_the_number_of_the_player(self):
        game = played().game
        shots = [shot(1, "09:00", 0, 7, True), shot(1, "08:00", 0, "12", False), shot(1, "07:00", 1, 5, True)]
        assert infer_numbers(game.log, shots, TEAMS) == {"p1": "7", "p2": "12", "r1": "5"}

    def test_the_team_is_part_of_the_key(self):
        game = played().game
        assert infer_numbers(game.log, [shot(1, "09:00", 1, 7, True)], TEAMS) == {}        # the shot of the other team at that second is not his

    def test_made_or_missed_is_part_of_the_key(self):
        game = played().game
        assert infer_numbers(game.log, [shot(1, "09:00", 0, 7, False)], TEAMS) == {}

    def test_two_field_goals_of_a_team_in_the_same_second_are_not_told_apart(self):
        """A tip-in right after a put-back: two lines and two shots with the same key; with two different players nothing can be said."""
        m = Match().lineup(OWN, ["p1", "p2"], at=0).score(OWN, 2, at=60, player="p1").score(OWN, 2, at=60, player="p2")
        shots = [shot(1, "09:00", 0, 7, True), shot(1, "09:00", 0, 9, True)]
        assert infer_numbers(m.game.log, shots, TEAMS) == {}

    def test_the_same_player_twice_in_the_same_second_is_still_one_number(self):
        m = Match().lineup(OWN, ["p1"], at=0).miss(OWN, at=60, player="p1").score(OWN, 2, at=60, player="p1")
        assert infer_numbers(m.game.log, [shot(1, "09:00", 0, 7, False), shot(1, "09:00", 0, 7, True)], TEAMS) == {"p1": "7"}

    def test_a_shot_without_a_line_or_a_line_without_a_shot_says_nothing(self):
        game = played().game
        assert infer_numbers(game.log, [shot(1, "04:00", 0, 7, True)], TEAMS) == {}
        assert infer_numbers(game.log, [], TEAMS) == {}

    def test_the_number_most_voted_wins_and_a_tie_says_nothing(self):
        m = Match().lineup(OWN, ["p1"], at=0)
        for at in (60, 120, 180):
            m.score(OWN, 2, at=at, player="p1")
        shots = [shot(1, "09:00", 0, 7, True), shot(1, "08:00", 0, 7, True), shot(1, "07:00", 0, 8, True)]
        assert infer_numbers(m.game.log, shots, TEAMS) == {"p1": "7"}
        assert infer_numbers(m.game.log, shots[:1] + shots[2:], TEAMS) == {}

    def test_free_throws_and_the_other_lines_of_the_log_are_not_shots(self):
        m = Match().lineup(OWN, ["p1"], at=0).score(OWN, 1, at=60, player="p1").turnover(OWN, at=70, player="p1")
        assert infer_numbers(m.game.log, [shot(1, "09:00", 0, 7, True)], TEAMS) == {}

    def test_a_line_without_a_player_gives_nobody_a_number(self):
        m = Match().lineup(OWN, ["p1"], at=0)
        m.game.log.append([60, OWN, "fg2", 1, None])
        assert infer_numbers(m.game.log, [shot(1, "09:00", 0, 7, True)], TEAMS) == {}

    def test_it_works_in_every_period_and_in_overtime(self):
        m = Match().lineup(OWN, ["p1"], at=0).score(OWN, 2, at=1500, player="p1").score(OWN, 2, at=2450, player="p1")
        shots = [shot(3, "05:00", 0, 7, True), shot(5, "04:10", 0, 7, True)]
        assert infer_numbers(m.game.log, shots, TEAMS) == {"p1": "7"}

    def test_it_is_deterministic_whatever_the_order_of_the_shots(self):
        game = played().game
        shots = [shot(1, "09:00", 0, 7, True), shot(1, "08:00", 0, 12, False), shot(1, "07:00", 1, 5, True)]
        assert infer_numbers(game.log, shots, TEAMS) == infer_numbers(game.log, list(reversed(shots)), TEAMS)

    @pytest.mark.parametrize("junk", [{}, {"team": "x"}, {"team": "9", "quarter": "1", "t": "09:00", "player": "7", "m": "1"}, {"team": "0", "quarter": "1", "t": "FINAL", "player": "7", "m": "1"}])
    def test_malformed_shots_are_ignored(self, junk):
        assert infer_numbers(played().game.log, [junk], TEAMS) == {}


class TestInTheEngine:
    """Replayed as the feed served them: the live box score of 2ª FEB has no numbers, the one of the LF Challenge has them."""

    @staticmethod
    def replay(code):
        feed, engine, snap, doc = RecordedFeed.load(ROOT / "recordings" / f"{code}.rec.json.gz"), LiveEngine(), None, None
        for frame in feed.frames:
            doc = feed.document_at(frame["t"])
            snap = engine.update(doc)
        return engine, snap, doc

    @pytest.mark.parametrize("code", ["2536311", "2536133", "2536851"])
    def test_in_2a_and_3a_feb_the_players_who_shot_get_the_number_of_the_roster_of_the_package(self, code):
        _, snap, doc = self.replay(code)
        assert not any(p.get("no") for team in doc["BOXSCORE"]["TEAM"] for p in team["PLAYER"])            # the live box score has no numbers
        roster = json.loads((ROOT / "recordings" / f"{code}.package.json").read_text(encoding="utf-8"))["package"]["tables"]["roster"]
        said = {pid: str(r["dorsal"]) for pid, r in roster.items() if r.get("dorsal") is not None}
        inferred = {pid: p["no"] for pid, p in snap["players"].items() if p["no"] is not None}
        assert len(inferred) >= 14
        assert all(said[pid] == no for pid, no in inferred.items() if pid in said), {p: (no, said.get(p)) for p, no in inferred.items() if said.get(p) != no}

    def test_what_the_box_score_says_wins_over_what_the_shots_say(self):
        engine, snap, doc = self.replay("2524470")                       # the box score of the LF Challenge has the numbers
        assert all(p["no"] == str(box["no"]).strip() for team in doc["BOXSCORE"]["TEAM"] for box in team["PLAYER"] for p in [snap["players"][box["id"]]] if box.get("no") not in (None, ""))

    def test_the_inferred_numbers_agree_with_the_box_score_where_both_exist(self):
        engine, _, doc = self.replay("2524470")
        inferred = infer_numbers(engine._game.log, engine._shots.raw_shots(), [tid for tid, _ in [(str(t["id"]), 0) for t in doc["HEADER"]["TEAM"]]])
        boxed = {p["id"]: str(int(str(p["no"]))) for team in doc["BOXSCORE"]["TEAM"] for p in team["PLAYER"] if str(p.get("no", "")).strip().isdigit()}
        assert len(inferred) >= 12 and all(str(int(no)) == boxed[pid] for pid, no in inferred.items() if pid in boxed)

    def test_the_zones_of_each_player_are_now_kept_where_the_live_box_score_has_no_numbers_regression(self):
        """Bug: in 2ª FEB the live box score has no ``no``, so no shot was ever attributed to a player (0 players with zones in both teams of 2536311) and the rule of the zone of a
        rival player could not act."""
        _, snap, _ = self.replay("2536311")
        zones = snap["zone_players"]
        assert all(len(players) >= 4 for players in zones.values())

    def test_the_shot_chart_arriving_after_the_play_by_play_gives_the_numbers_when_it_arrives(self):
        feed = RecordedFeed.load(ROOT / "recordings" / "2536311.rec.json.gz")
        doc = copy.deepcopy(feed.document_at(feed.frames[-1]["t"]))
        full_shots = doc["SHOTCHART"]["SHOTS"]
        engine = LiveEngine()
        doc["SHOTCHART"]["SHOTS"] = []
        assert all(p["no"] is None for p in engine.update(doc)["players"].values())
        doc["SHOTCHART"]["SHOTS"] = full_shots
        later = engine.update(doc)
        assert sum(1 for p in later["players"].values() if p["no"] is not None) >= 14
        assert later["players"] == LiveEngine().update(doc)["players"]                     # the same as a fresh engine: nothing depends on the order of the polls

    def test_without_a_shot_chart_nothing_is_inferred_and_nothing_fails(self):
        from src.live_prep.fbcyl_adapter import to_feb_document
        import gzip
        raw = json.loads(gzip.open(ROOT / "fixtures" / "fbcyl_game_ok.json.gz").read())
        snap = LiveEngine().update(to_feb_document(raw))
        assert all(p["no"] for p in snap["players"].values() if p["minutes"] > 0)         # FBCYL numbers come from its box score

    def test_polling_twice_gives_the_same_state(self):
        feed = RecordedFeed.load(ROOT / "recordings" / "2536311.rec.json.gz")
        doc = feed.document_at(feed.frames[-1]["t"])
        engine = LiveEngine()
        assert engine.update(doc) == engine.update(doc)


class TestTheTrackerFollowsTheMapping:
    def test_the_zones_of_a_player_include_the_shots_seen_before_his_number_was_known(self):
        tracker = ShotTracker(TEAMS)
        tracker.update({"SHOTS": [shot(1, "09:00", 0, 7, True, x="94", y="25"), shot(1, "08:00", 0, 7, False, x="80", y="10")]})
        assert tracker.player_snapshot()[OWN] == {}
        tracker.set_dorsals({OWN: {"7": "p1"}})
        zones = tracker.player_snapshot()[OWN]["p1"]
        assert sum(cell["a"] for cell in zones.values()) == 2 and sum(cell["m"] for cell in zones.values()) == 1
        assert sum(cell["a"] for cell in tracker.snapshot()[OWN].values()) == 2           # the zones of the team did not change
